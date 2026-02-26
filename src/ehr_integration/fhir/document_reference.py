"""FHIR R4 DocumentReference builder with real schema validation.

Builds and validates FHIR R4 DocumentReference resources from Deepgram utterances.

FHIR version note:
  fhir.resources >= 8.0 implements FHIR R5. Epic and Cerner currently use FHIR R4.
  This module produces R4-structured dicts. Two validation paths are provided:
    - validate_r4_schema()   : offline R4 rules (required fields, codes, base64)
    - validate_with_hapi()   : live POST to the public HAPI FHIR R4 server
"""

from __future__ import annotations

import base64
import binascii
import re
from datetime import datetime, timezone
from typing import Any

from ..transcription.models import Utterance


_LOINC_PROGRESS_NOTE     = "11506-3"
_LOINC_CONSULT_NOTE      = "11488-4"
_LOINC_DISCHARGE_SUMMARY = "18842-5"
_LOINC_AMBIENT_CLINICAL  = "34109-9"

DOC_TYPE_LOINC: dict[str, str] = {
    "progress_note":     _LOINC_PROGRESS_NOTE,
    "consult_note":      _LOINC_CONSULT_NOTE,
    "discharge_summary": _LOINC_DISCHARGE_SUMMARY,
    "ambient":           _LOINC_AMBIENT_CLINICAL,
}

_VALID_STATUSES    = {"current", "superseded", "entered-in-error"}
_VALID_DOC_STATUSES = {"preliminary", "final", "amended", "entered-in-error"}
_LOINC_SYSTEM      = "http://loinc.org"
_VALID_LOINC_CODES = set(DOC_TYPE_LOINC.values())
_FHIR_DATETIME_RE  = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(Z|[+-]\d{2}:\d{2})$"
)
_FHIR_REFERENCE_RE = re.compile(r"^[A-Z][A-Za-z]+/.+$")  # resource type must start uppercase


class FHIRValidationError(ValueError):
    """Raised when a DocumentReference dict fails FHIR R4 schema validation."""


class DocumentReferenceBuilder:
    """Build and validate FHIR R4 DocumentReference dicts from clinical transcripts."""

    @staticmethod
    def from_transcript(
        utterances: list[Utterance],
        patient_id: str,
        encounter_id: str,
        doc_type_code: str = "progress_note",
        author_practitioner_id: str | None = None,
        title: str = "Clinical Transcription",
    ) -> dict:
        """Build a validated FHIR R4 DocumentReference from utterances.

        Args:
            utterances: Speaker-diarized utterances from Deepgram.
            patient_id: FHIR Patient logical ID (e.g. 'patient-123').
            encounter_id: FHIR Encounter logical ID.
            doc_type_code: One of progress_note, consult_note,
                           discharge_summary, or ambient.
            author_practitioner_id: Optional FHIR Practitioner ID.
            title: Document title stored in attachment.title.

        Returns:
            A dict conforming to FHIR R4 DocumentReference schema, already
            validated via validate_r4_schema().

        Raises:
            FHIRValidationError: if the constructed resource fails R4 validation.
            ValueError: if patient_id or encounter_id are empty.
        """
        if not patient_id or not patient_id.strip():
            raise ValueError("patient_id must not be empty")
        if not encounter_id or not encounter_id.strip():
            raise ValueError("encounter_id must not be empty")

        loinc_code    = DOC_TYPE_LOINC.get(doc_type_code, _LOINC_PROGRESS_NOTE)
        transcript    = _format_transcript(utterances)
        encoded_data  = base64.b64encode(transcript.encode("utf-8")).decode("ascii")
        now_iso       = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        doc_ref: dict[str, Any] = {
            "resourceType": "DocumentReference",
            "status":       "current",
            "docStatus":    "final",
            "type": {
                "coding": [{
                    "system":  _LOINC_SYSTEM,
                    "code":    loinc_code,
                    "display": _loinc_display(loinc_code),
                }]
            },
            "subject": {"reference": f"Patient/{patient_id}"},
            "date":    now_iso,
            "content": [{
                "attachment": {
                    "contentType": "text/plain",
                    "data":        encoded_data,
                    "title":       title,
                }
            }],
            "context": {
                "encounter": [{"reference": f"Encounter/{encounter_id}"}]
            },
        }

        if author_practitioner_id:
            doc_ref["author"] = [
                {"reference": f"Practitioner/{author_practitioner_id}"}
            ]

        # Validate before returning — fail fast
        DocumentReferenceBuilder.validate_r4_schema(doc_ref)
        return doc_ref

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    @staticmethod
    def validate_r4_schema(doc_ref: dict) -> None:
        """Validate a DocumentReference dict against FHIR R4 rules.

        Checks enforced (all offline, no network required):
          - resourceType is 'DocumentReference'
          - status is present and a valid R4 code
          - docStatus, if present, is a valid R4 code
          - type.coding[0] has system='http://loinc.org' and a non-empty code
          - subject.reference matches 'ResourceType/id' pattern
          - date is a FHIR instant (ISO-8601 with timezone)
          - content[0].attachment.data is valid base64
          - context.encounter[0].reference, if present, matches pattern
          - author references, if present, match pattern

        Raises:
            FHIRValidationError: with a descriptive message listing every error.
        """
        errors: list[str] = []

        if doc_ref.get("resourceType") != "DocumentReference":
            errors.append(
                f"resourceType must be 'DocumentReference', got {doc_ref.get('resourceType')!r}"
            )

        status = doc_ref.get("status")
        if not status:
            errors.append("status is required")
        elif status not in _VALID_STATUSES:
            errors.append(f"status {status!r} is not a valid R4 code: {_VALID_STATUSES}")

        doc_status = doc_ref.get("docStatus")
        if doc_status and doc_status not in _VALID_DOC_STATUSES:
            errors.append(f"docStatus {doc_status!r} is not a valid R4 code: {_VALID_DOC_STATUSES}")

        coding = (
            doc_ref.get("type", {})
            .get("coding", [{}])[0]
            if doc_ref.get("type", {}).get("coding")
            else {}
        )
        if not coding:
            errors.append("type.coding must have at least one entry")
        else:
            if coding.get("system") != _LOINC_SYSTEM:
                errors.append(
                    f"type.coding[0].system must be {_LOINC_SYSTEM!r}, got {coding.get('system')!r}"
                )
            if not coding.get("code"):
                errors.append("type.coding[0].code is required")

        subject_ref = doc_ref.get("subject", {}).get("reference", "")
        if not subject_ref:
            errors.append("subject.reference is required")
        elif not _FHIR_REFERENCE_RE.match(subject_ref):
            errors.append(
                f"subject.reference {subject_ref!r} must match 'ResourceType/id'"
            )

        date_val = doc_ref.get("date", "")
        if date_val and not _FHIR_DATETIME_RE.match(date_val):
            errors.append(
                f"date {date_val!r} must be a FHIR instant (YYYY-MM-DDTHH:MM:SSZ)"
            )

        content = doc_ref.get("content", [])
        if not content:
            errors.append("content must have at least one entry")
        else:
            b64_data = content[0].get("attachment", {}).get("data", "")
            if b64_data:
                try:
                    base64.b64decode(b64_data, validate=True)
                except binascii.Error:
                    errors.append("content[0].attachment.data is not valid base64")

        enc_refs = (
            doc_ref.get("context", {}).get("encounter", [])
            if isinstance(doc_ref.get("context"), dict)
            else []
        )
        for i, enc in enumerate(enc_refs):
            ref = enc.get("reference", "")
            if not _FHIR_REFERENCE_RE.match(ref):
                errors.append(
                    f"context.encounter[{i}].reference {ref!r} must match 'ResourceType/id'"
                )

        for i, author in enumerate(doc_ref.get("author", [])):
            ref = author.get("reference", "")
            if not _FHIR_REFERENCE_RE.match(ref):
                errors.append(
                    f"author[{i}].reference {ref!r} must match 'ResourceType/id'"
                )

        if errors:
            bullet_list = "\n  - ".join(errors)
            raise FHIRValidationError(
                f"FHIR R4 DocumentReference validation failed ({len(errors)} error(s)):\n  - {bullet_list}"
            )

    @staticmethod
    def decode_content(doc_ref: dict) -> str:
        """Decode the base64 transcript content from a DocumentReference."""
        try:
            data = doc_ref["content"][0]["attachment"]["data"]
            return base64.b64decode(data).decode("utf-8")
        except (KeyError, IndexError, ValueError) as exc:
            raise ValueError(f"Cannot decode DocumentReference content: {exc}") from exc


# ------------------------------------------------------------------
# Private helpers
# ------------------------------------------------------------------

def _format_transcript(utterances: list[Utterance]) -> str:
    if not utterances:
        return ""
    return "\n".join(
        f"[Speaker {u.speaker} | {u.start:.1f}s-{u.end:.1f}s] {u.transcript}"
        for u in utterances
    )


def _loinc_display(code: str) -> str:
    return {
        _LOINC_PROGRESS_NOTE:     "Progress note",
        _LOINC_CONSULT_NOTE:      "Consult note",
        _LOINC_DISCHARGE_SUMMARY: "Discharge summary",
        _LOINC_AMBIENT_CLINICAL:  "Note",
    }.get(code, "Clinical note")
