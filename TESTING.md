# Testing Guide — Start Here

No experience required. Follow each step exactly as written.
If anything looks different from what's described, stop and ask before continuing.

---

## Before anything else — what are we actually testing?

This project connects Deepgram's AI speech-to-text service to hospital
electronic health record (EHR) systems. In plain terms: a doctor speaks,
the software transcribes it, and sends the note to the hospital's system in
the correct medical format.

The tests confirm three things:

1. **The code is correct** — bugs found in the original guide are actually fixed
2. **The medical formats are valid** — the FHIR and HL7 messages we produce meet
   the official healthcare standards that Epic and Cerner require
3. **Edge cases don't crash it** — unusual inputs (short audio, empty transcripts,
   punctuation in clinical notes) all handled gracefully

None of this requires a real hospital system, a real microphone, or a paid API key.
Everything runs on your laptop.

---

## Step 1 — Open Terminal

On a Mac: press **Command + Space**, type **Terminal**, press **Enter**.

A window opens with a blinking cursor. That is where you type commands.

---

## Step 2 — Go to the project folder

Type this and press Enter:

```
cd ~/Desktop/ehremr
```

Confirm you're in the right place:

```
ls
```

You should see these names listed:

```
Makefile        examples        requirements-dev.txt    src
TESTING.md      pyproject.toml  requirements.txt        tests
```

If you don't see those, stop here and ask for help.

---

## Step 3 — Check Python is installed

```
python --version
```

You should see: `Python 3.10.10`

---

## Step 4 — Install the dependencies (do this once)

This downloads everything the project needs to run.

```
python -m pip install -r requirements-dev.txt
```

You will see a long list of packages being downloaded. That is normal. It ends with
something like `Successfully installed ...`. Ignore any warnings about `spacy` or
`thinc` — those are from unrelated software already on your machine.

Then install the project itself:

```
python -m pip install -e .
```

Confirm it worked:

```
python -c "import ehr_integration; print('Ready to test')"
```

You should see: `Ready to test`

---

## Step 5 — Run all the offline tests

This is the main command. Run it every time you want to verify everything works.

```
python -m pytest tests/unit tests/integration tests/quality -v
```

The `-v` flag means "verbose" — show every test individually.

It will run for about 6 seconds. You will see a long list of lines, each ending
in `PASSED` (green) or `FAILED` (red).

**What good looks like:**

```
tests/unit/test_batch_transcription.py::TestBatchTranscriberImport::test_deepgram_client_imported_directly PASSED
tests/unit/test_batch_transcription.py::TestBatchTranscriberMimetypeInSource::test_transcribe_file_passes_mimetype PASSED
...
211 passed in 3.2s
```

The last line must say `211 passed`. Zero failures.

**If you see any FAILED lines:** paste the output and ask for help. Do not continue.

---

## Step 6 — Understand what just ran

211 tests just ran. Here is what each group was checking, in plain English.

---

### Group 1 — Corrected bugs (tests/unit/)

These tests prove the seven errors found in the original Deepgram guide are fixed.
Each test is a direct regression check — if someone accidentally reverted the fix,
the test would immediately fail.

**How to run just this group:**

```
python -m pytest tests/unit -v
```

**What each test file checks:**

`test_batch_transcription.py` — Three bugs fixed here:
- The Deepgram library is imported the correct way
- Audio files are sent with their file type declared (without this, Deepgram silently rejects the request)
- When a conversation produces no speaker data, the code does not crash

`test_streaming.py` — Four bugs fixed here:
- The streaming library imports are correct
- The connection is properly closed when recording ends (without this, Deepgram cuts off the last 12 seconds of every encounter)
- A failed connection attempt raises a clear error instead of silently continuing
- Error and close notification handlers are registered (production safety)

`test_fhir_builder.py` — Checks the medical document structure:
- The correct LOINC codes are used for each note type (Progress Note, Consult Note, Discharge Summary, etc.)
- The clinical transcript is correctly encoded for transmission
- Patient and encounter references are correctly formatted

`test_hl7_mdm_builder.py` — Checks the HL7 message format:
- All required segments are present (MSH, EVN, PID, PV1, TXA, OBX)
- The message can be read by a standard HL7 library without errors

`test_ehr_clients.py` — Checks Epic and Cerner connections:
- Authentication with Epic's system works correctly
- Authentication with Cerner's system works correctly
- Documents are submitted with the correct headers and credentials

---

### Group 2 — End-to-end flows (tests/integration/)

These tests run the complete pipeline from start to finish, with all
hospital systems simulated.

**How to run just this group:**

```
python -m pytest tests/integration -v
```

**What each test checks:**

`test_ambient_documentation_flow.py` — Full ambient documentation pipeline:
Simulates a doctor speaking during a patient visit → transcript built up
utterance by utterance → assembled into a FHIR document → posted to a
simulated Epic system → gets back a 201 Created response.

`test_ehr_submission_flow.py` — Full dictation pipeline via HL7:
Simulates a doctor dictating a note → transcribed → converted to an HL7v2
MDM^T02 message → verified parseable → submitted to a simulated Cerner
system → gets back a 201 Created response.

---

### Group 3 — Deep validation (tests/quality/)

This is where the testing goes beyond "does it run" to "is it actually correct."

**How to run just this group:**

```
python -m pytest tests/quality -v
```

**What each test file checks:**

`test_fhir_schema_validation.py` — Real FHIR R4 rules enforced:

FHIR (Fast Healthcare Interoperability Resources) is the international standard
for exchanging health information. Epic and Cerner both require documents to
follow strict R4 rules. These tests verify every rule is enforced:

- Status codes must be exactly `current`, `superseded`, or `entered-in-error` —
  not `active`, not `CURRENT`, not anything else
- Document status must be exactly `preliminary`, `final`, `amended`, or `entered-in-error`
- The LOINC coding system URI must be exactly `http://loinc.org`
- Resource references must follow the pattern `ResourceType/id` where
  the resource type starts with a capital letter (`Patient/123`, not `patient/123`)
- Dates must follow the FHIR instant format (`2026-02-25T10:00:00Z`)
- The embedded transcript data must be valid base64 encoding
- If multiple rules are violated, all errors are reported at once, not just the first

To see a validation error in action:

```
python -c "
from ehr_integration.fhir.document_reference import DocumentReferenceBuilder, FHIRValidationError
try:
    DocumentReferenceBuilder.validate_r4_schema({
        'resourceType': 'DocumentReference',
        'status': 'INVALID_STATUS',
        'subject': {'reference': 'patient-no-slash'},
        'content': [{'attachment': {'data': '!!!notbase64!!!'}}],
    })
except FHIRValidationError as e:
    print(e)
"
```

You should see three errors reported together — status, reference format, and base64.

`test_hl7_deep_validation.py` — Real HL7 field values checked:

HL7v2 is the older messaging standard still widely used in hospitals for
sending transcribed notes. These tests go beyond checking that the message
parses — they check that specific fields contain the right values:

- MSH segment encoding characters must be exactly `^~\&` (the HL7 standard delimiter set)
- Timestamp fields must be exactly 14 digits (`YYYYMMDDHHMMSS`)
- Processing ID must be `P` for production
- Version must be `2.5.1`
- OBX-2 value type must be `TX` (text)
- OBX-11 result status must be `F` (Final)
- TXA-12 completion status must be a valid HL7 code
- TXA-14 availability status must be a valid HL7 code

`test_property_based.py` — Hundreds of random inputs tested automatically:

Instead of testing specific examples, these tests use a tool called Hypothesis
that generates hundreds of random inputs and checks that invariants always hold.
Think of it as a tireless colleague who keeps trying unusual cases until
something breaks.

Properties that are verified to hold for every random input:
- The FHIR builder never crashes for any valid patient/encounter ID
- Every document the builder produces passes the R4 schema rules
- The transcript is always recoverable after base64 encoding/decoding
- The HL7 message is always parseable regardless of what clinical text it contains
- A transcript with pipe characters (`120|80` for a BP reading) is always handled correctly
- Empty utterance lists never cause crashes

To watch Hypothesis working, run with verbose output:

```
python -m pytest tests/quality/test_property_based.py -v --hypothesis-show-statistics 2>&1 | grep -A3 "Trying"
```

---

## Step 7 — Run the demo scripts

These are standalone scripts that show the full pipeline visually.
No test framework needed — just run them and read the output.

**Demo 1: Transcription**

```
python examples/batch_transcribe.py
```

Shows a formatted clinical conversation with speaker labels and timestamps.

**Demo 2: Live streaming simulation**

```
python examples/live_stream.py
```

Shows audio chunks being sent and confirms the connection was properly closed.

**Demo 3: FHIR document submission**

```
python examples/submit_to_fhir.py
```

Builds a complete FHIR DocumentReference, shows the full JSON, decodes
the embedded transcript, then simulates posting it to Epic and getting back
a 201 Created response.

---

## Step 8 — Validate against the real FHIR standard (optional, needs internet)

The previous steps all ran offline. This step posts your actual FHIR output to
the public HAPI FHIR server — a free, publicly available FHIR R4 reference
implementation maintained by the team that created the standard. No account needed.

```
python -m pytest tests/live/test_hapi_fhir_validator.py -v
```

This takes about 30 seconds. It posts each of your four document types
(Progress Note, Consult Note, Discharge Summary, Ambient Note) to HAPI and
confirms the server returns zero errors on each one.

A passing result looks like:

```
tests/live/test_hapi_fhir_validator.py::TestHAPIFHIRR4Validation::test_progress_note_passes_hapi_validation PASSED
tests/live/test_hapi_fhir_validator.py::TestHAPIFHIRR4Validation::test_all_doc_types_pass_hapi_r4_validation[progress_note] PASSED
tests/live/test_hapi_fhir_validator.py::TestHAPIFHIRR4Validation::test_all_doc_types_pass_hapi_r4_validation[consult_note] PASSED
tests/live/test_hapi_fhir_validator.py::TestHAPIFHIRR4Validation::test_all_doc_types_pass_hapi_r4_validation[discharge_summary] PASSED
tests/live/test_hapi_fhir_validator.py::TestHAPIFHIRR4Validation::test_all_doc_types_pass_hapi_r4_validation[ambient] PASSED
tests/live/test_hapi_fhir_validator.py::TestHAPIFHIRR4Validation::test_deliberately_invalid_doc_is_rejected_by_hapi PASSED
tests/live/test_hapi_fhir_validator.py::TestHAPIFHIRR4Validation::test_hapi_server_is_reachable PASSED
```

This is the closest thing to "a standards body signed off on your output"
that you can get without paying for a certification program.

---

## Step 9 — Save the results

Run this to save a complete record of every test and its result:

```
python -m pytest tests/unit tests/integration tests/quality -v --cov=src --cov-report=term-missing 2>&1 | tee test_report.txt
echo "Saved to test_report.txt"
```

The file `test_report.txt` on your Desktop contains:
- Every test name and whether it passed
- The coverage table showing 99% of the code is tested
- The full output you would show to anyone asking for proof

---

## Quick reference

| What you want to do | Command |
|---------------------|---------|
| Run all offline tests | `python -m pytest tests/unit tests/integration tests/quality -v` |
| Run only the bug-fix tests | `python -m pytest tests/unit -v` |
| Run only end-to-end tests | `python -m pytest tests/integration -v` |
| Run only deep validation | `python -m pytest tests/quality -v` |
| Validate against real FHIR server | `python -m pytest tests/live/test_hapi_fhir_validator.py -v` |
| See coverage numbers | `python -m pytest tests/unit tests/integration tests/quality --cov=src` |
| Save results to a file | Add `2>&1 \| tee test_report.txt` to the end of any command |
| Run all examples | `python examples/batch_transcribe.py` then `python examples/submit_to_fhir.py` |

---

## If something goes wrong

**"command not found: python"** — Try `python3` instead of `python`.

**"No module named 'ehr_integration'"** — Run `python -m pip install -e .` again.
On this machine `pip` and `python` point to different Python versions.
Always use `python -m pip install`, never just `pip install`.

**A test shows FAILED** — Do not try to fix it yourself. Copy the full error message
and ask for help. The error message tells you exactly which file and line is wrong.

**The HAPI test times out** — The HAPI server is occasionally slow or under
maintenance. Wait 10 minutes and try again. All other tests are offline and
unaffected by this.

**Not sure if your output matches what's expected** — Run this to check versions:

```
python -m pip show deepgram-sdk fhir.resources hl7 pydantic PyJWT hypothesis 2>&1 | grep -E "Name:|Version:"
```

Share the output and it will be clear immediately where the mismatch is.
