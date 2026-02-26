"""Integration test: full ambient documentation pipeline.

Flow: mock audio → mock Deepgram streaming → utterance accumulation
      → FHIR DocumentReference → mock Epic POST (201 Created)
"""

from __future__ import annotations

import base64
from unittest.mock import MagicMock, patch

import pytest

from ehr_integration.transcription.models import Utterance
from ehr_integration.ehr.epic_client import EpicFHIRClient
from ehr_integration.use_cases.ambient_documentation import AmbientDocumentationPipeline


MOCK_UTTERANCES = [
    Utterance(speaker=0, transcript="Chief complaint is chest pain.", start=0.5, end=3.0, confidence=0.99),
    Utterance(speaker=1, transcript="It started this morning after breakfast.", start=3.5, end=6.8, confidence=0.97),
    Utterance(speaker=0, transcript="Any radiation to the arm or neck?", start=7.0, end=9.5, confidence=0.98),
    Utterance(speaker=1, transcript="No, but I feel nauseous.", start=10.0, end=12.1, confidence=0.96),
]


@pytest.fixture
def epic_client_with_mock_session() -> EpicFHIRClient:
    """Epic client wired to a session that returns a 201 for DocumentReference POST."""
    session = MagicMock()
    token_resp = MagicMock()
    token_resp.json.return_value = {"access_token": "ambient-test-token"}
    token_resp.raise_for_status = MagicMock()
    fhir_resp = MagicMock()
    fhir_resp.status_code = 201
    fhir_resp.json.return_value = {
        "resourceType": "DocumentReference",
        "id": "ambient-dr-001",
        "status": "current",
    }
    fhir_resp.raise_for_status = MagicMock()
    session.post.side_effect = [token_resp, fhir_resp]
    return EpicFHIRClient(
        base_url="https://fhir.epic.com/api/FHIR/R4",
        token_url="https://fhir.epic.com/oauth2/token",
        session=session,
    )


class TestAmbientDocumentationPipeline:
    def test_full_pipeline_returns_201(self, epic_client_with_mock_session: EpicFHIRClient) -> None:
        # Authenticate
        with patch("ehr_integration.ehr.epic_client.jwt.encode", return_value="signed.jwt"):
            epic_client_with_mock_session.authenticate(
                client_id="test-client", private_key=b"fake-key"
            )

        pipeline = AmbientDocumentationPipeline(epic_client_with_mock_session)

        # Simulate streaming utterances arriving
        for u in MOCK_UTTERANCES:
            pipeline.add_utterance(u)

        result = pipeline.finalize_and_submit(
            patient_id="patient-amb-001",
            encounter_id="encounter-amb-002",
            doc_type_code="progress_note",
        )

        assert result["status_code"] == 201

    def test_fhir_doc_ref_has_correct_patient(self, epic_client_with_mock_session: EpicFHIRClient) -> None:
        with patch("ehr_integration.ehr.epic_client.jwt.encode", return_value="signed.jwt"):
            epic_client_with_mock_session.authenticate(
                client_id="test-client", private_key=b"fake-key"
            )

        pipeline = AmbientDocumentationPipeline(epic_client_with_mock_session)
        for u in MOCK_UTTERANCES:
            pipeline.add_utterance(u)

        result = pipeline.finalize_and_submit(
            patient_id="patient-x",
            encounter_id="encounter-y",
        )
        doc_ref = result["doc_ref"]
        assert doc_ref["subject"]["reference"] == "Patient/patient-x"
        assert doc_ref["context"]["encounter"][0]["reference"] == "Encounter/encounter-y"

    def test_transcript_content_encoded_in_fhir(self, epic_client_with_mock_session: EpicFHIRClient) -> None:
        with patch("ehr_integration.ehr.epic_client.jwt.encode", return_value="signed.jwt"):
            epic_client_with_mock_session.authenticate(
                client_id="test-client", private_key=b"fake-key"
            )

        pipeline = AmbientDocumentationPipeline(epic_client_with_mock_session)
        for u in MOCK_UTTERANCES:
            pipeline.add_utterance(u)

        result = pipeline.finalize_and_submit(patient_id="p", encounter_id="e")
        doc_ref = result["doc_ref"]
        encoded = doc_ref["content"][0]["attachment"]["data"]
        decoded = base64.b64decode(encoded).decode("utf-8")
        assert "chest pain" in decoded
        assert "nauseous" in decoded

    def test_empty_encounter_still_valid(self, epic_client_with_mock_session: EpicFHIRClient) -> None:
        with patch("ehr_integration.ehr.epic_client.jwt.encode", return_value="signed.jwt"):
            epic_client_with_mock_session.authenticate(
                client_id="test-client", private_key=b"fake-key"
            )

        pipeline = AmbientDocumentationPipeline(epic_client_with_mock_session)
        # No utterances added
        result = pipeline.finalize_and_submit(patient_id="p", encounter_id="e")
        assert result["status_code"] == 201
        doc_ref = result["doc_ref"]
        assert doc_ref["resourceType"] == "DocumentReference"
