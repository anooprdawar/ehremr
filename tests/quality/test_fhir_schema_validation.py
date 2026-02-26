"""Real FHIR R4 schema validation tests.

These tests go beyond checking dict keys. They use the FHIRValidationError
raised by validate_r4_schema() to confirm every R4 constraint is enforced:
required fields, valid status codes, LOINC system URI, reference patterns,
date format, and base64 integrity.

All tests are offline — no network required.
"""

from __future__ import annotations

import base64
import copy
import pytest

from ehr_integration.transcription.models import Utterance
from ehr_integration.fhir.document_reference import (
    DocumentReferenceBuilder,
    FHIRValidationError,
    _LOINC_SYSTEM,
)

pytestmark = pytest.mark.quality


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def valid_doc() -> dict:
    """A known-good DocumentReference that passes all validation rules."""
    return DocumentReferenceBuilder.from_transcript(
        utterances=[
            Utterance(speaker=0, transcript="Assessment: stable angina.", start=0.0, end=3.5, confidence=0.99),
            Utterance(speaker=1, transcript="I feel much better today.", start=4.0, end=6.2, confidence=0.97),
        ],
        patient_id="patient-schema-001",
        encounter_id="encounter-schema-001",
        doc_type_code="progress_note",
        author_practitioner_id="practitioner-npi-001",
    )


# ---------------------------------------------------------------------------
# Happy path — the builder produces a valid resource
# ---------------------------------------------------------------------------

class TestBuilderProducesValidResource:
    def test_valid_doc_passes_schema(self, valid_doc: dict) -> None:
        # must not raise
        DocumentReferenceBuilder.validate_r4_schema(valid_doc)

    def test_resource_type(self, valid_doc: dict) -> None:
        assert valid_doc["resourceType"] == "DocumentReference"

    def test_status_is_current(self, valid_doc: dict) -> None:
        assert valid_doc["status"] == "current"

    def test_doc_status_is_final(self, valid_doc: dict) -> None:
        assert valid_doc["docStatus"] == "final"

    def test_loinc_system_uri(self, valid_doc: dict) -> None:
        system = valid_doc["type"]["coding"][0]["system"]
        assert system == "http://loinc.org"

    def test_content_type_text_plain(self, valid_doc: dict) -> None:
        ct = valid_doc["content"][0]["attachment"]["contentType"]
        assert ct == "text/plain"

    def test_date_is_fhir_instant(self, valid_doc: dict) -> None:
        import re
        pattern = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(Z|[+-]\d{2}:\d{2})$")
        assert pattern.match(valid_doc["date"]), f"date {valid_doc['date']!r} is not a FHIR instant"

    def test_subject_reference_pattern(self, valid_doc: dict) -> None:
        ref = valid_doc["subject"]["reference"]
        assert ref.startswith("Patient/")
        assert len(ref) > len("Patient/")

    def test_encounter_reference_pattern(self, valid_doc: dict) -> None:
        ref = valid_doc["context"]["encounter"][0]["reference"]
        assert ref.startswith("Encounter/")

    def test_author_reference_pattern(self, valid_doc: dict) -> None:
        ref = valid_doc["author"][0]["reference"]
        assert ref.startswith("Practitioner/")

    def test_base64_data_is_valid(self, valid_doc: dict) -> None:
        raw = valid_doc["content"][0]["attachment"]["data"]
        decoded = base64.b64decode(raw, validate=True)
        assert len(decoded) > 0

    def test_transcript_roundtrips_through_base64(self, valid_doc: dict) -> None:
        decoded = DocumentReferenceBuilder.decode_content(valid_doc)
        assert "stable angina" in decoded
        assert "Speaker 0" in decoded
        assert "Speaker 1" in decoded


# ---------------------------------------------------------------------------
# Required-field enforcement
# ---------------------------------------------------------------------------

class TestRequiredFields:
    def test_missing_resource_type_raises(self, valid_doc: dict) -> None:
        doc = copy.deepcopy(valid_doc)
        del doc["resourceType"]
        with pytest.raises(FHIRValidationError, match="resourceType"):
            DocumentReferenceBuilder.validate_r4_schema(doc)

    def test_missing_status_raises(self, valid_doc: dict) -> None:
        doc = copy.deepcopy(valid_doc)
        del doc["status"]
        with pytest.raises(FHIRValidationError, match="status"):
            DocumentReferenceBuilder.validate_r4_schema(doc)

    def test_missing_subject_raises(self, valid_doc: dict) -> None:
        doc = copy.deepcopy(valid_doc)
        del doc["subject"]
        with pytest.raises(FHIRValidationError, match="subject"):
            DocumentReferenceBuilder.validate_r4_schema(doc)

    def test_missing_content_raises(self, valid_doc: dict) -> None:
        doc = copy.deepcopy(valid_doc)
        del doc["content"]
        with pytest.raises(FHIRValidationError, match="content"):
            DocumentReferenceBuilder.validate_r4_schema(doc)

    def test_empty_content_list_raises(self, valid_doc: dict) -> None:
        doc = copy.deepcopy(valid_doc)
        doc["content"] = []
        with pytest.raises(FHIRValidationError, match="content"):
            DocumentReferenceBuilder.validate_r4_schema(doc)


# ---------------------------------------------------------------------------
# Status code validation
# ---------------------------------------------------------------------------

class TestStatusCodes:
    @pytest.mark.parametrize("status", ["current", "superseded", "entered-in-error"])
    def test_valid_statuses_accepted(self, valid_doc: dict, status: str) -> None:
        doc = copy.deepcopy(valid_doc)
        doc["status"] = status
        DocumentReferenceBuilder.validate_r4_schema(doc)  # must not raise

    @pytest.mark.parametrize("bad_status", [
        "active", "inactive", "CURRENT", "Current", "draft", "unknown", "",
    ])
    def test_invalid_status_rejected(self, valid_doc: dict, bad_status: str) -> None:
        doc = copy.deepcopy(valid_doc)
        doc["status"] = bad_status
        with pytest.raises(FHIRValidationError, match="status"):
            DocumentReferenceBuilder.validate_r4_schema(doc)

    @pytest.mark.parametrize("doc_status", ["preliminary", "final", "amended", "entered-in-error"])
    def test_valid_doc_statuses_accepted(self, valid_doc: dict, doc_status: str) -> None:
        doc = copy.deepcopy(valid_doc)
        doc["docStatus"] = doc_status
        DocumentReferenceBuilder.validate_r4_schema(doc)

    @pytest.mark.parametrize("bad", ["complete", "approved", "FINAL"])
    def test_invalid_doc_status_rejected(self, valid_doc: dict, bad: str) -> None:
        doc = copy.deepcopy(valid_doc)
        doc["docStatus"] = bad
        with pytest.raises(FHIRValidationError, match="docStatus"):
            DocumentReferenceBuilder.validate_r4_schema(doc)


# ---------------------------------------------------------------------------
# LOINC system URI enforcement
# ---------------------------------------------------------------------------

class TestLOINCSystemValidation:
    def test_wrong_loinc_system_uri_rejected(self, valid_doc: dict) -> None:
        doc = copy.deepcopy(valid_doc)
        doc["type"]["coding"][0]["system"] = "http://snomed.info/sct"
        with pytest.raises(FHIRValidationError, match="system"):
            DocumentReferenceBuilder.validate_r4_schema(doc)

    def test_missing_coding_raises(self, valid_doc: dict) -> None:
        doc = copy.deepcopy(valid_doc)
        doc["type"]["coding"] = []
        with pytest.raises(FHIRValidationError, match="coding"):
            DocumentReferenceBuilder.validate_r4_schema(doc)

    def test_missing_code_in_coding_raises(self, valid_doc: dict) -> None:
        doc = copy.deepcopy(valid_doc)
        del doc["type"]["coding"][0]["code"]
        with pytest.raises(FHIRValidationError, match="code"):
            DocumentReferenceBuilder.validate_r4_schema(doc)

    @pytest.mark.parametrize("loinc_code,expected_display", [
        ("11506-3", "Progress note"),
        ("11488-4", "Consult note"),
        ("18842-5", "Discharge summary"),
        ("34109-9", "Note"),
    ])
    def test_all_loinc_codes_produce_correct_display(
        self, loinc_code: str, expected_display: str
    ) -> None:
        doc = DocumentReferenceBuilder.from_transcript([], "p", "e")
        doc["type"]["coding"][0]["code"] = loinc_code
        doc["type"]["coding"][0]["display"] = expected_display
        DocumentReferenceBuilder.validate_r4_schema(doc)
        assert doc["type"]["coding"][0]["display"] == expected_display


# ---------------------------------------------------------------------------
# Reference pattern validation
# ---------------------------------------------------------------------------

class TestReferencePatterns:
    @pytest.mark.parametrize("bad_ref", [
        "patient-123",          # missing resource type prefix
        "patient/123",          # lowercase resource type
        "/patient-123",         # leading slash
        "",                     # empty string
    ])
    def test_bad_subject_reference_rejected(self, valid_doc: dict, bad_ref: str) -> None:
        doc = copy.deepcopy(valid_doc)
        doc["subject"]["reference"] = bad_ref
        with pytest.raises(FHIRValidationError, match="subject.reference"):
            DocumentReferenceBuilder.validate_r4_schema(doc)

    @pytest.mark.parametrize("good_ref", [
        "Patient/abc123",
        "Patient/MRN-001",
        "Patient/some-uuid-here",
    ])
    def test_valid_subject_references_accepted(self, valid_doc: dict, good_ref: str) -> None:
        doc = copy.deepcopy(valid_doc)
        doc["subject"]["reference"] = good_ref
        DocumentReferenceBuilder.validate_r4_schema(doc)

    def test_bad_encounter_reference_rejected(self, valid_doc: dict) -> None:
        doc = copy.deepcopy(valid_doc)
        doc["context"]["encounter"][0]["reference"] = "encounter-no-slash"
        with pytest.raises(FHIRValidationError, match="context.encounter"):
            DocumentReferenceBuilder.validate_r4_schema(doc)

    def test_bad_author_reference_rejected(self, valid_doc: dict) -> None:
        doc = copy.deepcopy(valid_doc)
        doc["author"] = [{"reference": "npi-only-no-prefix"}]
        with pytest.raises(FHIRValidationError, match="author"):
            DocumentReferenceBuilder.validate_r4_schema(doc)


# ---------------------------------------------------------------------------
# Base64 integrity
# ---------------------------------------------------------------------------

class TestBase64Integrity:
    def test_invalid_base64_rejected(self, valid_doc: dict) -> None:
        doc = copy.deepcopy(valid_doc)
        doc["content"][0]["attachment"]["data"] = "this is not base64!@#$"
        with pytest.raises(FHIRValidationError, match="base64"):
            DocumentReferenceBuilder.validate_r4_schema(doc)

    def test_valid_base64_accepted(self, valid_doc: dict) -> None:
        doc = copy.deepcopy(valid_doc)
        doc["content"][0]["attachment"]["data"] = base64.b64encode(b"valid content").decode()
        DocumentReferenceBuilder.validate_r4_schema(doc)

    def test_multiple_errors_reported_together(self, valid_doc: dict) -> None:
        """validate_r4_schema should collect all errors, not stop at the first."""
        doc = copy.deepcopy(valid_doc)
        doc["status"] = "INVALID"
        doc["subject"]["reference"] = "no-slash-here"
        doc["content"][0]["attachment"]["data"] = "!!!notbase64!!!"

        with pytest.raises(FHIRValidationError) as exc_info:
            DocumentReferenceBuilder.validate_r4_schema(doc)

        msg = str(exc_info.value)
        assert "3 error" in msg
        assert "status" in msg
        assert "subject" in msg
        assert "base64" in msg


# ---------------------------------------------------------------------------
# Input guards on from_transcript
# ---------------------------------------------------------------------------

class TestBuilderInputGuards:
    def test_empty_patient_id_raises(self) -> None:
        with pytest.raises(ValueError, match="patient_id"):
            DocumentReferenceBuilder.from_transcript([], "", "enc-001")

    def test_whitespace_patient_id_raises(self) -> None:
        with pytest.raises(ValueError, match="patient_id"):
            DocumentReferenceBuilder.from_transcript([], "   ", "enc-001")

    def test_empty_encounter_id_raises(self) -> None:
        with pytest.raises(ValueError, match="encounter_id"):
            DocumentReferenceBuilder.from_transcript([], "pat-001", "")
