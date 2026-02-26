# Deepgram Nova-3 Medical — EHR/EMR Integration Guide

---

## Table of Contents

1. [Overview](#1-overview)
2. [Nova-3 Medical Model](#2-nova-3-medical-model)
3. [Project Setup](#3-project-setup)
4. [Data Models](#4-data-models)
5. [Batch Transcription](#5-batch-transcription)
6. [Streaming Transcription](#6-streaming-transcription)
7. [FHIR R4 Integration](#7-fhir-r4-integration)
8. [HL7v2 Integration](#8-hl7v2-integration)
9. [EHR Client Authentication](#9-ehr-client-authentication)
10. [Clinical Use Cases](#10-clinical-use-cases)
11. [Testing](#11-testing)

---

## 1. Overview

Deepgram Nova-3 Medical provides real-time and pre-recorded speech-to-text optimized for
clinical vocabulary. This guide covers the full integration stack from audio capture
to EHR submission.

### Architecture

```
Audio (file or microphone)
        │
        ▼
┌───────────────────┐
│  BatchTranscriber │  (pre-recorded)
│  StreamingTranscriber │  (real-time WebSocket)
└───────────────────┘
        │  ClinicalTranscriptionResult
        │  └── utterances: list[Utterance]
        │  └── full_transcript: str
        ▼
┌─────────────────────────────────┐
│  DocumentReferenceBuilder       │  → FHIR R4 DocumentReference dict
│  MDMBuilder / ORUBuilder        │  → HL7v2 MDM^T02 / ORU^R01 string
└─────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────┐
│  EpicFHIRClient                 │  (JWT backend services)
│  CernerFHIRClient               │  (SMART client credentials)
│  FHIRClient                     │  (generic, unauthenticated)
└─────────────────────────────────┘
        │
        ▼
      EHR / EMR
```

The `ClinicalTranscriptionResult` object is the handoff point between transcription
and the EHR integration layers. Everything downstream consumes its `utterances` list
or `full_transcript` string.

---

## 2. Nova-3 Medical Model

| Feature | Value |
|---|---|
| Model ID | `nova-3-medical` |
| Clinical vocabulary | Yes — ICD-10 codes, drug names, anatomy |
| Speaker diarization | `diarize=True` |
| Vocabulary boosting | `keyterm=[...]` |
| Smart formatting | `smart_format=True` |
| Interim results (streaming) | `interim_results=False` recommended |

> **Vocabulary boosting:** Nova-3 Medical uses the `keyterm` option (a list of strings),
> not `keywords`. Using `keywords` is silently ignored.

---

## 3. Project Setup

### `pyproject.toml`

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "ehr-integration"
version = "0.1.0"
description = "Deepgram Nova-3 Medical speech-to-text integration for EHR/EMR systems"
requires-python = ">=3.10"
dependencies = [
    "deepgram-sdk>=3.7",
    "fhir.resources>=7.1",
    "hl7>=0.4.0",
    "requests>=2.31",
    "pydantic>=2.0",
    "python-dotenv>=1.0",
    "PyJWT>=2.8",
    "cryptography>=41.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "requests-mock>=1.12",
    "pytest-cov>=5.0",
]

[tool.setuptools.packages.find]
where = ["src"]
```

### `.env.example`

```dotenv
DEEPGRAM_API_KEY=your_deepgram_api_key_here

# Epic
EPIC_BASE_URL=https://fhir.epic.com/interconnect-fhir-oauth
EPIC_CLIENT_ID=your_epic_client_id
EPIC_PRIVATE_KEY_PATH=./keys/epic_rsa.pem

# Cerner
CERNER_BASE_URL=https://fhir-ehr.cerner.com/r4/your_tenant_id
CERNER_TOKEN_URL=https://authorization.cerner.com/tenants/your_tenant_id/protocols/oauth2/profiles/smart-v1/token
CERNER_CLIENT_ID=your_cerner_client_id
CERNER_CLIENT_SECRET=your_cerner_client_secret
```

### Install

```bash
python -m pip install -e ".[dev]"
```

> Use `python -m pip` rather than bare `pip` to ensure packages install into the
> correct interpreter when multiple Python versions are present.

---

## 4. Data Models

Source: `src/ehr_integration/transcription/models.py`

These Pydantic models are returned by both `BatchTranscriber` and `StreamingTranscriber`
and consumed by the FHIR and HL7v2 builders.

### `Utterance`

A single speaker turn from a diarized transcription.

```python
class Utterance(BaseModel):
    speaker:    int    # Speaker index (0-based)
    transcript: str    # Transcribed text for this utterance
    start:      float  # Start time in seconds
    end:        float  # End time in seconds
    confidence: float  # Confidence score 0.0–1.0 (default 0.0)
```

### `ClinicalTranscriptionResult`

The top-level result object returned by all transcription methods.

```python
class ClinicalTranscriptionResult(BaseModel):
    utterances:        list[Utterance]  # Speaker-diarized turns (empty if diarize=False)
    full_transcript:   str              # Full concatenated transcript
    request_id:        str              # Deepgram request ID
    model:             str              # Model name (e.g. "nova-3-medical")
    detected_language: str              # Detected language (default "en-US")
    keyterms_detected: list[str]        # Keyterms found in the audio
```

`utterances` requires `diarize=True`. When diarization is disabled or produces no
results, `utterances` will be an empty list and `full_transcript` contains the
unsegmented text.

---

## 5. Batch Transcription

Source: `src/ehr_integration/transcription/batch.py`

### Imports

```python
from deepgram import DeepgramClient, PrerecordedOptions
```

### `BatchTranscriber`

```python
class BatchTranscriber:
    def __init__(self, api_key: str | None = None) -> None:
        key = api_key or os.environ.get("DEEPGRAM_API_KEY", "")
        self._client = DeepgramClient(key)

    def transcribe_file(
        self,
        path: str | Path,
        keyterms: list[str] | None = None,
        diarize: bool = True,
    ) -> ClinicalTranscriptionResult:
        path = Path(path)
        mimetype = _mimetype_for(path)

        options = PrerecordedOptions(
            model="nova-3-medical",
            smart_format=True,
            diarize=diarize,
            keyterm=keyterms or [],
        )

        with open(path, "rb") as audio:
            source = {"buffer": audio.read(), "mimetype": mimetype}
            response = self._client.listen.rest.v("1").transcribe_file(source, options)

        return ClinicalTranscriptionResult.from_deepgram_response(response)

    def transcribe_url(
        self,
        url: str,
        keyterms: list[str] | None = None,
        diarize: bool = True,
    ) -> ClinicalTranscriptionResult:
        options = PrerecordedOptions(
            model="nova-3-medical",
            smart_format=True,
            diarize=diarize,
            keyterm=keyterms or [],
        )
        source = {"url": url}
        response = self._client.listen.rest.v("1").transcribe_url(source, options)
        return ClinicalTranscriptionResult.from_deepgram_response(response)

    @staticmethod
    def format_utterances(result: ClinicalTranscriptionResult) -> str:
        utterances = result.utterances or []
        if not utterances:
            return result.full_transcript
        lines = []
        for u in utterances:
            lines.append(f"[{u.start:.1f}s] Speaker {u.speaker}: {u.transcript}")
        return "\n".join(lines)
```

### Key implementation notes

- The buffer source dict must include `"mimetype"` alongside `"buffer"` — the SDK
  uses it to determine the audio format.
- Supported MIME types: `audio/wav`, `audio/mpeg` (MP3), `audio/mp4` (M4A),
  `audio/flac`, `audio/ogg`, `audio/webm`.

### Usage

```python
from ehr_integration.transcription.batch import BatchTranscriber

transcriber = BatchTranscriber()  # reads DEEPGRAM_API_KEY from env
result = transcriber.transcribe_file(
    "visit_recording.wav",
    keyterms=["metformin", "HbA1c", "type 2 diabetes"],
)

print(transcriber.format_utterances(result))
# [0.0s] Speaker 0: Good morning, how are you feeling today?
# [3.4s] Speaker 1: My HbA1c came back at 7.2 this morning.

# Access raw fields
print(result.full_transcript)   # full unsegmented text
print(result.request_id)        # Deepgram request ID for debugging
```

---

## 6. Streaming Transcription

Source: `src/ehr_integration/transcription/streaming.py`

### Imports

```python
from deepgram import DeepgramClient, LiveOptions, LiveTranscriptionEvents
```

### `StreamingTranscriber`

```python
class StreamingTranscriber:
    def __init__(self, api_key: str | None = None) -> None:
        key = api_key or os.environ.get("DEEPGRAM_API_KEY", "")
        self._client = DeepgramClient(key)
        self._connection = None
        self._lock = threading.Lock()

    def start(
        self,
        on_transcript: Callable[[str, int, float, float], None],
        on_error: Callable[[Exception], None] | None = None,
        on_close: Callable[[], None] | None = None,
        keyterms: list[str] | None = None,
    ) -> None:
        options = LiveOptions(
            model="nova-3-medical",
            smart_format=True,
            diarize=True,
            keyterm=keyterms or [],
            interim_results=False,
        )

        connection = self._client.listen.websocket.v("1")

        def _on_message(_self, result, **kwargs):
            sentence = result.channel.alternatives[0].transcript
            if not sentence:
                return
            words = result.channel.alternatives[0].words or []
            start = words[0].start if words else 0.0
            end = words[-1].end if words else 0.0
            speaker = words[0].speaker if words else 0
            on_transcript(sentence, speaker, start, end)

        def _on_error(_self, error, **kwargs):
            exc = Exception(str(error))
            if on_error:
                on_error(exc)
            else:
                print(f"[Deepgram error] {error}", file=sys.stderr)

        def _on_close(_self, **kwargs):
            if on_close:
                on_close()

        connection.on(LiveTranscriptionEvents.Transcript, _on_message)
        connection.on(LiveTranscriptionEvents.Error, _on_error)
        connection.on(LiveTranscriptionEvents.Close, _on_close)

        if not connection.start(options):
            raise RuntimeError("Failed to connect to Deepgram WebSocket")

        with self._lock:
            self._connection = connection

    def send_audio(self, chunk: bytes) -> None:
        with self._lock:
            if self._connection is None:
                raise RuntimeError("Call start() before send_audio()")
            self._connection.send(chunk)

    def finish(self) -> None:
        with self._lock:
            conn = self._connection
            self._connection = None
        if conn is not None:
            conn.finish()

    @property
    def is_connected(self) -> bool:
        """True if the WebSocket connection is currently open."""
        with self._lock:
            return self._connection is not None
```

### Key implementation notes

- `on_transcript` receives `(text, speaker, start, end)` — the same fields as `Utterance`
  (see section 4). In the ambient documentation pipeline, each callback invocation is
  wrapped into an `Utterance` and accumulated for later FHIR submission.
- Wire `Error` and `Close` handlers in addition to `Transcript` — unhandled errors
  produce silent failures in production.
- `connection.start()` returns `False` if the WebSocket fails to open; always check
  the return value.
- Call `finish()` when done sending audio. Without it, Deepgram times out after
  approximately 12 seconds of silence and the WebSocket closes ungracefully.
- Use `is_connected` to guard against sending audio after `finish()` has been called.

### Usage

```python
from ehr_integration.transcription.streaming import StreamingTranscriber

transcripts = []

def on_transcript(text: str, speaker: int, start: float, end: float) -> None:
    print(f"[{start:.1f}s] Speaker {speaker}: {text}")
    transcripts.append(text)

def on_error(exc: Exception) -> None:
    print(f"Deepgram error: {exc}")

transcriber = StreamingTranscriber()
transcriber.start(
    on_transcript=on_transcript,
    on_error=on_error,
    keyterms=["metformin", "lisinopril"],
)

CHUNK_SIZE = 4096
with open("live_visit.wav", "rb") as f:
    while chunk := f.read(CHUNK_SIZE):
        transcriber.send_audio(chunk)

transcriber.finish()
```

---

## 7. FHIR R4 Integration

### `DocumentReferenceBuilder`

Source: `src/ehr_integration/fhir/document_reference.py`

Builds and validates FHIR R4 DocumentReference resources from a `ClinicalTranscriptionResult`.
The `utterances` list is base64-encoded into `content[0].attachment.data` with speaker
and timestamp formatting.

#### Supported document types

| `doc_type_code` | LOINC | Display |
|---|---|---|
| `progress_note` | `11506-3` | Progress note |
| `consult_note` | `11488-4` | Consult note |
| `discharge_summary` | `18842-5` | Discharge summary |
| `ambient` | `34109-9` | Note |

#### Building a DocumentReference

```python
from ehr_integration.fhir.document_reference import DocumentReferenceBuilder

doc_ref = DocumentReferenceBuilder.from_transcript(
    utterances=result.utterances,
    patient_id="patient-123",
    encounter_id="encounter-456",
    doc_type_code="progress_note",
    author_practitioner_id="prac-789",  # optional
    title="Office Visit — Dr. Smith",
)

print(doc_ref["resourceType"])  # "DocumentReference"
print(doc_ref["status"])        # "current"
print(doc_ref["docStatus"])     # "final"
```

The builder calls `validate_r4_schema()` before returning, so an invalid resource
raises `FHIRValidationError` immediately rather than at submission time.

#### R4 validation rules enforced

- `resourceType` must be `"DocumentReference"`
- `status` must be `current | superseded | entered-in-error`
- `docStatus`, if present, must be `preliminary | final | amended | entered-in-error`
- `type.coding[0].system` must be `"http://loinc.org"`
- `subject.reference` must match `ResourceType/id` pattern
- `date` must be a FHIR instant (`YYYY-MM-DDTHH:MM:SSZ`)
- `content[0].attachment.data` must be valid base64
- All `author` and `context.encounter` references must match `ResourceType/id` pattern

#### Manual validation

```python
from ehr_integration.fhir.document_reference import (
    DocumentReferenceBuilder,
    FHIRValidationError,
)

try:
    DocumentReferenceBuilder.validate_r4_schema(my_doc_ref)
    print("Valid FHIR R4 DocumentReference")
except FHIRValidationError as e:
    print(f"Validation failed: {e}")
```

#### Decoding the transcript content

```python
text = DocumentReferenceBuilder.decode_content(doc_ref)
print(text)
# [Speaker 0 | 0.0s-3.2s] Good morning, how are you feeling today?
# [Speaker 1 | 3.4s-6.1s] My HbA1c came back at 7.2 this morning.
```

### `FHIRClient`

Source: `src/ehr_integration/fhir/fhir_client.py`

Generic FHIR R4 HTTP client for unauthenticated or externally-authenticated requests
(e.g. the public HAPI FHIR server). For production Epic or Cerner submissions, use
`EpicFHIRClient` or `CernerFHIRClient` instead (section 9), which handle OAuth2
automatically.

```python
from ehr_integration.fhir.fhir_client import FHIRClient

client = FHIRClient("https://hapi.fhir.org/baseR4")

# POST a resource
response = client.post_resource("DocumentReference", doc_ref)
response.raise_for_status()
print(response.status_code)  # 201

# GET a resource
response = client.get_resource("Patient", "patient-123")
patient = response.json()
```

---

## 8. HL7v2 Integration

### MDM^T02 — Medical Document Management

Source: `src/ehr_integration/hl7/mdm_builder.py`

MDM^T02 is the standard HL7v2 message type for transmitting transcribed clinical
documents. Message structure: `MSH | EVN | PID | PV1 | TXA | OBX`

```python
from ehr_integration.hl7.mdm_builder import MDMBuilder

hl7_msg = MDMBuilder.build_t02(
    transcript="Patient presents with chest pain. EKG was normal.",
    patient_id="MRN123456",
    visit_id="VISIT789",
    provider_npi="1234567890",
    sending_app="DEEPGRAM",
    receiving_app="EHR_SYSTEM",
)

print(hl7_msg)
# MSH|^~\&|DEEPGRAM|EHR|EHR_SYSTEM|FACILITY|20240315120000||MDM^T02|MSG20240315120000|P|2.5.1
# EVN||20240315120000
# PID|1||MRN123456^^^MRN||LastName^FirstName|||U
# PV1|1|I|^^^WARD^^BED||||||1234567890^Provider^Name||||||||VISIT789
# TXA|1|PN^Progress Note|TX|20240315120000|1234567890^Provider^Name|...|AU||AV
# OBX|1|TX|18842-5^Discharge summary^LN||Patient presents with chest pain. EKG was normal.
```

Pipe characters in the transcript are automatically escaped as `\F\` to avoid
breaking HL7 segment parsing.

### ORU^R01 — Observation Result Unsolicited

Source: `src/ehr_integration/hl7/oru_builder.py`

ORU^R01 transmits clinical observations and results. Message structure:
`MSH | PID | OBR | OBX`

```python
from ehr_integration.hl7.oru_builder import ORUBuilder

hl7_msg = ORUBuilder.build_r01(
    transcript="Patient reports pain level 6 out of 10.",
    patient_id="MRN123456",
    order_id="ORDER001",
    provider_npi="1234567890",
    loinc_code="11506-3",
    loinc_display="Progress note",
)

print(hl7_msg)
# MSH|^~\&|DEEPGRAM|EHR|EHR_SYSTEM|FACILITY|20240315120000||ORU^R01|MSG20240315120000|P|2.5.1
# PID|1||MRN123456^^^MRN||LastName^FirstName|||U
# OBR|1|ORDER001||11506-3^Progress note^LN|||20240315120000|||1234567890^Provider^Name
# OBX|1|TX|11506-3^Progress note^LN||Patient reports pain level 6 out of 10.||||||F
```

### Choosing MDM^T02 vs ORU^R01

| | MDM^T02 | ORU^R01 |
|---|---|---|
| Use for | Transcribed clinical documents | Clinical observations and results |
| Includes | EVN, PV1, TXA segments | OBR segment |
| Typical use | Physician notes, discharge summaries | Nurse triage, structured observations |

---

## 9. EHR Client Authentication

### Abstract base

Source: `src/ehr_integration/ehr/base_ehr_client.py`

All EHR clients extend `BaseEHRClient`, which provides:

```python
class BaseEHRClient(ABC):
    def authenticate(self, **kwargs) -> str:
        """Obtain an OAuth2 access token. Returns the token string."""

    def submit_document_reference(self, doc_ref: dict) -> requests.Response:
        """POST a FHIR DocumentReference to the EHR (201 on success)."""
```

`submit_document_reference` automatically adds the `Authorization: Bearer <token>`
header. Call `authenticate()` first, or it raises `RuntimeError`.

### Epic — Backend Services JWT Flow

Source: `src/ehr_integration/ehr/epic_client.py`

Epic App Orchard backend services authentication:
1. Build a JWT signed with your RSA private key
2. POST to Epic's token endpoint
3. Use the returned `access_token` as `Bearer` on all FHIR API calls

```python
from ehr_integration.ehr.epic_client import EpicFHIRClient

client = EpicFHIRClient(
    base_url="https://fhir.epic.com/interconnect-fhir-oauth",
    # token_url defaults to {base_url}/oauth2/token — override if needed
)

token = client.authenticate(
    client_id="your-epic-client-id",
    private_key_path="./keys/epic_rsa.pem",  # path to RSA PEM file
    # or: private_key="-----BEGIN RSA PRIVATE KEY-----\n..."  (inline PEM string)
)

response = client.submit_document_reference(doc_ref)
response.raise_for_status()
```

**JWT claims built automatically:**

| Claim | Value |
|---|---|
| `iss` | `client_id` |
| `sub` | `client_id` |
| `aud` | Epic token URL |
| `jti` | UUID v4 |
| `iat` | Current Unix timestamp |
| `exp` | `iat + 300` (5-minute expiry per Epic spec) |

Signed with `RS384` as required by Epic.

### Cerner — SMART on FHIR Client Credentials

Source: `src/ehr_integration/ehr/cerner_client.py`

```python
from ehr_integration.ehr.cerner_client import CernerFHIRClient

client = CernerFHIRClient(
    base_url="https://fhir-ehr.cerner.com/r4/your_tenant_id",
    token_url="https://authorization.cerner.com/tenants/your_tenant_id/protocols/oauth2/profiles/smart-v1/token",
)

token = client.authenticate(
    client_id="your-cerner-client-id",
    client_secret="your-cerner-client-secret",
    scope="system/DocumentReference.write",
)

response = client.submit_document_reference(doc_ref)
response.raise_for_status()
```

---

## 10. Clinical Use Cases

Each pipeline combines the transcription, FHIR/HL7, and EHR authentication layers
into a single cohesive workflow.

### 10.1 Ambient Documentation

Source: `src/ehr_integration/use_cases/ambient_documentation.py`

Physician's voice is captured in real time during the encounter. Each transcript
callback accumulates an `Utterance`. When the encounter ends,
`finalize_and_submit()` builds and POSTs the FHIR DocumentReference in one call.

```python
from ehr_integration.use_cases.ambient_documentation import AmbientDocumentationPipeline
from ehr_integration.transcription.models import Utterance
from ehr_integration.transcription.streaming import StreamingTranscriber
from ehr_integration.ehr.epic_client import EpicFHIRClient

# Authenticate with the EHR
ehr = EpicFHIRClient(base_url="https://fhir.epic.com/interconnect-fhir-oauth")
ehr.authenticate(client_id="...", private_key_path="./keys/epic_rsa.pem")

pipeline = AmbientDocumentationPipeline(ehr_client=ehr)

# Wire the pipeline to the streaming transcriber
def on_transcript(text: str, speaker: int, start: float, end: float) -> None:
    pipeline.add_utterance(Utterance(
        speaker=speaker, start=start, end=end, transcript=text
    ))

transcriber = StreamingTranscriber()
transcriber.start(on_transcript=on_transcript, keyterms=["metformin", "HbA1c"])

# ... send audio chunks during the encounter ...

transcriber.finish()

# At end of encounter — builds DocumentReference and POSTs to EHR
result = pipeline.finalize_and_submit(
    patient_id="patient-123",
    encounter_id="encounter-456",
    doc_type_code="progress_note",
    author_practitioner_id="prac-789",
)
print(result["status_code"])  # 201
```

### 10.2 Physician Dictation

Source: `src/ehr_integration/use_cases/dictation.py`

Physician records a note after the visit. Audio is batch-transcribed and submitted
as either FHIR or HL7v2.

```python
from ehr_integration.use_cases.dictation import DictationPipeline
from ehr_integration.ehr.epic_client import EpicFHIRClient

pipeline = DictationPipeline()

result = pipeline.transcribe(
    audio_path="dictation_2024_03_15.mp3",
    keyterms=["metformin", "HbA1c", "insulin"],
)

# Option A — submit as FHIR DocumentReference
doc_ref = pipeline.to_fhir(
    result,
    patient_id="patient-123",
    encounter_id="encounter-456",
    doc_type_code="progress_note",
)
ehr = EpicFHIRClient(base_url="https://fhir.epic.com/interconnect-fhir-oauth")
ehr.authenticate(client_id="...", private_key_path="./keys/epic_rsa.pem")
ehr.submit_document_reference(doc_ref).raise_for_status()

# Option B — submit as HL7v2 MDM^T02
hl7_msg = pipeline.to_hl7_mdm(
    result,
    patient_id="MRN123456",
    visit_id="VISIT789",
    provider_npi="1234567890",
)
# send hl7_msg over your HL7 transport (MLLP, etc.)
```

### 10.3 Telehealth

Source: `src/ehr_integration/use_cases/telehealth.py`

Provider and patient are on a video call. Deepgram diarizes the audio into two
speaker tracks (speaker 0 = provider, speaker 1 = patient).

```python
from ehr_integration.use_cases.telehealth import TelehealthPipeline
from ehr_integration.transcription.batch import BatchTranscriber
from ehr_integration.ehr.cerner_client import CernerFHIRClient

transcriber = BatchTranscriber()
result = transcriber.transcribe_file("telehealth_session.wav")

# Inspect speaker tracks individually
tracks = TelehealthPipeline.separate_speakers(result)
print(f"Provider utterances: {len(tracks['provider'])}")
print(f"Patient utterances:  {len(tracks['patient'])}")

# Build FHIR consult note from the full diarized transcript
doc_ref = TelehealthPipeline.to_fhir(
    result,
    patient_id="patient-123",
    encounter_id="encounter-456",
)

# Submit to EHR
ehr = CernerFHIRClient(
    base_url="https://fhir-ehr.cerner.com/r4/your_tenant_id",
    token_url="https://authorization.cerner.com/...",
)
ehr.authenticate(client_id="...", client_secret="...")
ehr.submit_document_reference(doc_ref).raise_for_status()
```

### 10.4 Contact Center / Nurse Triage

Source: `src/ehr_integration/use_cases/contact_center.py`

Patient calls a triage line. The call is transcribed and posted to the EHR.

```python
from ehr_integration.use_cases.contact_center import ContactCenterPipeline
from ehr_integration.transcription.batch import BatchTranscriber
from ehr_integration.ehr.epic_client import EpicFHIRClient

transcriber = BatchTranscriber()
result = transcriber.transcribe_file("triage_call_recording.wav")

# Option A — submit as FHIR DocumentReference
doc_ref = ContactCenterPipeline.to_fhir(
    result,
    patient_id="patient-123",
    encounter_id="encounter-456",
)
ehr = EpicFHIRClient(base_url="https://fhir.epic.com/interconnect-fhir-oauth")
ehr.authenticate(client_id="...", private_key_path="./keys/epic_rsa.pem")
ehr.submit_document_reference(doc_ref).raise_for_status()

# Option B — submit as HL7v2 ORU^R01
hl7_msg = ContactCenterPipeline.to_hl7_oru(
    result,
    patient_id="MRN123456",
    order_id="ORDER001",
    provider_npi="1234567890",
)
# send hl7_msg over your HL7 transport (MLLP, etc.)
```

---

## 11. Testing

### Run the full test suite

```bash
python -m pytest tests/ -v --cov=src
```

### Test suite structure

```
tests/
├── unit/
│   ├── test_batch_transcriber.py
│   ├── test_streaming_transcriber.py
│   ├── test_document_reference.py
│   ├── test_fhir_client.py
│   ├── test_mdm_builder.py
│   ├── test_oru_builder.py
│   ├── test_epic_client.py
│   ├── test_cerner_client.py
│   └── test_use_cases.py
└── integration/
    └── test_end_to_end.py
```

104 tests, ~99% coverage. All tests are mock-based — no real API keys required.

### Test markers

| Marker | Description |
|---|---|
| `unit` | Fast offline unit tests |
| `integration` | Mock-based integration tests |
| `quality` | Schema, deep-validation, and property-based tests |
| `live` | Requires real credentials — skipped unless env vars set |

```bash
# Run only unit tests
python -m pytest tests/ -m unit -v

# Run with coverage report
python -m pytest tests/ -v --cov=src --cov-report=term-missing
```
