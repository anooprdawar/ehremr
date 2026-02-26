# EHR/EMR Integration — Deepgram Nova-3 Medical

Connects [Deepgram Nova-3 Medical](https://deepgram.com) speech-to-text to Epic and
Cerner EHR systems using FHIR R4 and HL7v2 standards.

---

## What it does

- **Batch transcription** — transcribe pre-recorded audio files
- **Streaming transcription** — real-time WebSocket transcription during live encounters
- **FHIR R4 DocumentReference** — build, validate, and submit clinical notes
- **HL7v2 messaging** — MDM^T02 (document management) and ORU^R01 (observations)
- **EHR authentication** — Epic JWT backend services and Cerner SMART client credentials
- **Clinical pipelines** — ambient documentation, physician dictation, telehealth, nurse triage

## Documentation

| Document | Audience |
|---|---|
| [`GUIDE.md`](GUIDE.md) | Developers — full technical reference with code |
| [`BUSINESS_OVERVIEW.md`](BUSINESS_OVERVIEW.md) | Decision makers — use cases, value, compatibility |
| [`TESTING.md`](TESTING.md) | QA / contributors — test strategy and markers |
| [`test_report.txt`](test_report.txt) | Reference — latest full test run output |

## Quick start

```bash
# Install
python -m pip install -e ".[dev]"

# Set your Deepgram API key
export DEEPGRAM_API_KEY=your_key_here

# Transcribe a file
python examples/batch_transcribe.py

# Run a live stream demo
python examples/live_stream.py
```

## Project structure

```
src/ehr_integration/
├── transcription/       # BatchTranscriber, StreamingTranscriber, data models
├── fhir/                # DocumentReferenceBuilder, FHIRClient
├── hl7/                 # MDMBuilder (MDM^T02), ORUBuilder (ORU^R01)
├── ehr/                 # EpicFHIRClient, CernerFHIRClient, BaseEHRClient
└── use_cases/           # Ambient documentation, dictation, telehealth, contact center

examples/                # Runnable demo scripts
tests/
├── unit/                # Fast offline unit tests
├── integration/         # Mock-based integration tests
├── quality/             # Schema validation and property-based tests
└── live/                # Optional tests requiring real credentials
```

## Tests

```bash
# Full suite
python -m pytest tests/ -v --cov=src

# Unit tests only
python -m pytest tests/ -m unit -v
```

211 tests, 99% coverage. All tests are mock-based — no real API keys required.

## Requirements

- Python 3.10+
- Deepgram API key
- Epic App Orchard registration (for Epic integration)
- Cerner SMART app registration (for Cerner integration)

See `.env.example` for all required environment variables.
