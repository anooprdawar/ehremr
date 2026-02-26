"""Unit tests for FHIR R4 DocumentReference builder."""

from __future__ import annotations

import base64

import pytest

from ehr_integration.fhir.document_reference import DocumentReferenceBuilder, DOC_TYPE_LOINC
from ehr_integration.transcription.models import Utterance


@pytest.fixture
def utterances() -> list[Utterance]:
    return [
        Utterance(speaker=0, transcript="Patient presents with chest pain.", start=0.0, end=3.5, confidence=0.99),
        Utterance(speaker=1, transcript="Pain started two hours ago.", start=4.0, end=6.2, confidence=0.97),
    ]


class TestDocumentReferenceStructure:
    def test_resource_type(self, utterances: list[Utterance]) -> None:
        doc = DocumentReferenceBuilder.from_transcript(utterances, "p-001", "e-001")
        assert doc["resourceType"] == "DocumentReference"

    def test_status_current(self, utterances: list[Utterance]) -> None:
        doc = DocumentReferenceBuilder.from_transcript(utterances, "p-001", "e-001")
        assert doc["status"] == "current"
        assert doc["docStatus"] == "final"

    def test_subject_reference(self, utterances: list[Utterance]) -> None:
        doc = DocumentReferenceBuilder.from_transcript(utterances, "patient-123", "enc-456")
        assert doc["subject"]["reference"] == "Patient/patient-123"

    def test_encounter_reference(self, utterances: list[Utterance]) -> None:
        doc = DocumentReferenceBuilder.from_transcript(utterances, "patient-123", "enc-456")
        assert doc["context"]["encounter"][0]["reference"] == "Encounter/enc-456"


class TestLOINCCode:
    @pytest.mark.parametrize("doc_type,expected_code", [
        ("progress_note", "11506-3"),
        ("consult_note", "11488-4"),
        ("discharge_summary", "18842-5"),
        ("ambient", "34109-9"),
        ("unknown_type", "11506-3"),  # defaults to progress note
    ])
    def test_loinc_code(self, doc_type: str, expected_code: str, utterances: list[Utterance]) -> None:
        doc = DocumentReferenceBuilder.from_transcript(utterances, "p-001", "e-001", doc_type_code=doc_type)
        coding = doc["type"]["coding"][0]
        assert coding["system"] == "http://loinc.org"
        assert coding["code"] == expected_code


class TestBase64Encoding:
    def test_content_base64_encoded(self, utterances: list[Utterance]) -> None:
        doc = DocumentReferenceBuilder.from_transcript(utterances, "p-001", "e-001")
        encoded = doc["content"][0]["attachment"]["data"]
        # Must be valid base64
        decoded = base64.b64decode(encoded).decode("utf-8")
        assert len(decoded) > 0

    def test_transcript_in_content(self, utterances: list[Utterance]) -> None:
        doc = DocumentReferenceBuilder.from_transcript(utterances, "p-001", "e-001")
        decoded = DocumentReferenceBuilder.decode_content(doc)
        assert "chest pain" in decoded
        assert "Speaker 0" in decoded
        assert "Speaker 1" in decoded

    def test_decode_content_roundtrip(self, utterances: list[Utterance]) -> None:
        doc = DocumentReferenceBuilder.from_transcript(utterances, "p-001", "e-001")
        decoded = DocumentReferenceBuilder.decode_content(doc)
        # Each utterance should be present
        for u in utterances:
            assert u.transcript in decoded

    def test_content_type_text_plain(self, utterances: list[Utterance]) -> None:
        doc = DocumentReferenceBuilder.from_transcript(utterances, "p-001", "e-001")
        assert doc["content"][0]["attachment"]["contentType"] == "text/plain"


class TestAuthorField:
    def test_author_included_when_provided(self, utterances: list[Utterance]) -> None:
        doc = DocumentReferenceBuilder.from_transcript(
            utterances, "p-001", "e-001", author_practitioner_id="pract-999"
        )
        assert "author" in doc
        assert doc["author"][0]["reference"] == "Practitioner/pract-999"

    def test_no_author_when_not_provided(self, utterances: list[Utterance]) -> None:
        doc = DocumentReferenceBuilder.from_transcript(utterances, "p-001", "e-001")
        assert "author" not in doc


class TestEmptyUtterances:
    def test_empty_utterances_still_valid_fhir(self) -> None:
        doc = DocumentReferenceBuilder.from_transcript([], "p-001", "e-001")
        assert doc["resourceType"] == "DocumentReference"
        decoded = DocumentReferenceBuilder.decode_content(doc)
        assert decoded == ""

    def test_decode_content_invalid_raises(self) -> None:
        with pytest.raises(ValueError):
            DocumentReferenceBuilder.decode_content({"content": []})
