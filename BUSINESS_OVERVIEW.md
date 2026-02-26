# Clinical Voice AI for EHR/EMR Systems
## A Business Overview of Deepgram Nova-3 Medical Integration

---

## The Problem: Documentation Is Consuming Clinical Time

Physicians spend an average of two hours on documentation for every hour of direct
patient care. Nurses and care coordinators face a similar burden. This time is taken
from patients, contributes to clinician burnout, and adds operational cost without
improving outcomes.

The root cause is the EHR data entry requirement. Every patient interaction —
office visit, phone triage call, telehealth session, dictated note — ultimately
needs to become a structured record in the EHR. Today that work is done manually:
typing, clicking, and transcribing, often after the clinical encounter has ended.

Voice AI changes that equation. When speech is accurately converted to structured
clinical text in real time, the documentation writes itself.

---

## The Solution: Deepgram Nova-3 Medical

Deepgram Nova-3 Medical is a speech-to-text model purpose-built for clinical
environments. Unlike general-purpose voice assistants, it is trained on medical
language: drug names, anatomical terms, ICD-10 codes, clinical abbreviations, and
the specific cadence of physician speech.

This integration connects Nova-3 Medical to your EHR — whether Epic, Cerner, or
any FHIR R4-compliant system — using the standards your IT and compliance teams
already work with: FHIR R4 DocumentReference and HL7v2 messaging.

### What it delivers

| Capability | What it means in practice |
|---|---|
| Real-time transcription | Words appear as they are spoken, with no perceptible delay |
| Medical vocabulary | Drug names, diagnoses, and procedures are recognized accurately without custom training |
| Speaker identification | In multi-party encounters, the system distinguishes provider speech from patient speech |
| EHR submission | Transcripts are posted directly to the patient record — no copy-paste, no re-entry |
| Standards compliance | Output uses FHIR R4 and HL7v2 — the same formats your EHR already accepts |

---

## Four Use Cases, One Platform

### 1. Ambient Clinical Documentation

**What it is:** The physician speaks normally during the encounter. The system
listens, transcribes in real time, and posts a completed clinical note to the
EHR when the encounter ends — without any physician interaction with a keyboard.

**Who benefits:** Primary care, specialist, and urgent care physicians who
currently spend significant time on post-visit documentation.

**The business case:** Reducing documentation time per encounter by even 10 minutes,
across a panel of 20 patients per day, returns over three hours of clinical capacity
daily per physician. At scale across a practice or health system, this represents
significant revenue recovery or capacity expansion without adding headcount.

---

### 2. Physician Dictation

**What it is:** The physician records a note verbally — after the visit, between
patients, or from a mobile device. The system transcribes the recording and routes
it to the EHR as a structured clinical document.

**Who benefits:** Physicians who prefer dictation over keyboard entry, and those
in specialties (radiology, pathology, surgery) where dictation is already the
established workflow.

**The business case:** Replaces costly transcription services and eliminates the
24–48 hour lag between dictation and note availability. Notes are in the EHR
within seconds of the recording ending.

---

### 3. Telehealth Visit Documentation

**What it is:** During a video visit, the audio stream is transcribed and
attributed separately to provider and patient. The resulting diarized transcript
is structured as a FHIR consult note and posted to the EHR.

**Who benefits:** Telehealth programs, virtual care teams, and any service line
where video visits have created a documentation gap relative to in-person care.

**The business case:** Telehealth volume has grown substantially and is not
receding. Documentation workflows built for in-person care do not translate
well to virtual encounters. This closes that gap without requiring clinicians
to change how they conduct video visits.

---

### 4. Contact Center and Nurse Triage

**What it is:** Patient calls to a triage line or nurse advice line are transcribed
in real time. The call record is posted to the EHR as a clinical note and, where
required, as an HL7v2 observation result for downstream clinical systems.

**Who benefits:** Contact centers, after-hours triage services, and nurse advice
lines that currently create manual call summaries or have no structured call record
at all.

**The business case:** Unstructured or missing call documentation creates clinical
risk and audit exposure. Automated transcription provides a complete, timestamped
record of every triage interaction at a fraction of the cost of manual documentation.

---

## EHR Compatibility

The integration is built on open standards that are already part of your EHR's
certified capabilities.

### Epic

Authentication uses Epic's App Orchard backend services flow — the same mechanism
used by other certified third-party applications in your Epic environment. No
special network configuration is required beyond what you already have in place
for other App Orchard integrations.

### Cerner (Oracle Health)

Authentication uses the SMART on FHIR client credentials flow supported natively
by Cerner Ignite. Integration follows the same patterns as other SMART applications
in your Cerner environment.

### Other FHIR R4 Systems

Any EHR or health information system that accepts FHIR R4 DocumentReference
resources or HL7v2 MDM^T02 / ORU^R01 messages can receive output from this
integration without customization.

---

## Standards and Compliance Posture

### Data formats
All clinical documents are structured using established healthcare interoperability
standards — not proprietary formats. FHIR R4 DocumentReference with LOINC-coded
document types means the output is portable, auditable, and compatible with
downstream systems including HIEs and analytics platforms.

### Document types supported
| Document type | LOINC code | Typical use |
|---|---|---|
| Progress note | 11506-3 | Office visits, follow-ups |
| Consult note | 11488-4 | Specialist and telehealth encounters |
| Discharge summary | 18842-5 | Inpatient discharge documentation |
| Ambient clinical note | 34109-9 | Real-time ambient documentation |

### What this integration does not do
- It does not make clinical decisions or generate diagnostic suggestions
- It does not access or store patient data beyond the current session
- It does not replace physician review — the clinician reviews and signs the
  note in the EHR using their existing workflow
- It does not require changes to EHR configuration or clinical workflows beyond
  the integration setup

---

## What Is Required to Deploy

| Requirement | Details |
|---|---|
| Deepgram API key | Obtained from Deepgram; usage-based pricing |
| EHR API access | Epic App Orchard registration or Cerner SMART app registration |
| RSA key pair (Epic) | Generated during App Orchard onboarding; stored securely on your infrastructure |
| Python 3.10+ runtime | For the integration service; deployable on any cloud or on-premises server |
| Audio source | Microphone input, telephony recording, or video platform audio stream |

The integration runs as a service in your environment. Audio does not need to
transit through any intermediary — it goes directly from your audio source to
Deepgram's API and the resulting text goes directly from the integration to your EHR.

---

## Summary

| | Before | After |
|---|---|---|
| Documentation method | Manual keyboard entry or manual transcription | Automatic from speech |
| Time to note availability | Hours to days (dictation) or minutes (live typing) | Seconds after encounter ends |
| Physician time per note | 10–20 minutes average | Review and sign only |
| Call record completeness | Manual summary or none | Full timestamped transcript |
| EHR format | Structured (entered manually) | Structured (entered automatically) |
| Integration standards | N/A | FHIR R4, HL7v2, Epic, Cerner |

Voice AI for clinical documentation is no longer an emerging technology — it is
a proven operational tool. The question for health systems is not whether to adopt
it, but how quickly the workflow and integration can be put in place.

This integration provides that foundation.
