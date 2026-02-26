"""Integration test: batch transcription → HL7v2 MDM^T02 → mock Cerner endpoint.

Flow: dummy audio → mock Deepgram batch → ClinicalTranscriptionResult
      → HL7v2 MDM^T02 string → parseable by python-hl7
      → FHIR DocumentReference → mock Cerner POST (201)
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import hl7

from ehr_integration.transcription.batch import BatchTranscriber
from ehr_integration.transcription.models import Utterance
from ehr_integration.hl7.mdm_builder import MDMBuilder
from ehr_integration.ehr.cerner_client import CernerFHIRClient
from ehr_integration.use_cases.dictation import DictationPipeline
from tests.conftest import make_deepgram_mock_response


SAMPLE_UTTERANCES = [
    Utterance(speaker=0, transcript="History of present illness: Patient is a 65-year-old male.", start=0.0, end=5.0, confidence=0.99),
    Utterance(speaker=0, transcript="He presents with dyspnea on exertion for three weeks.", start=5.5, end=9.8, confidence=0.97),
    Utterance(speaker=1, transcript="I also have ankle swelling since last Tuesday.", start=10.2, end=14.0, confidence=0.96),
]

FULL_TRANSCRIPT = " ".join(u.transcript for u in SAMPLE_UTTERANCES)


class TestHL7SubmissionFlow:
    """Batch transcription → HL7v2 MDM^T02 validation."""

    def test_batch_to_hl7_mdm_parseable(self, dummy_wav_file: Path) -> None:
        mock_response = make_deepgram_mock_response(SAMPLE_UTTERANCES, FULL_TRANSCRIPT)

        with patch("ehr_integration.transcription.batch.DeepgramClient") as mock_cls:
            mock_cls.return_value.listen.rest.v.return_value.transcribe_file.return_value = mock_response
            transcriber = BatchTranscriber(api_key="test-key")
            result = transcriber.transcribe_file(dummy_wav_file)

        mdm_msg = MDMBuilder.build_t02(
            transcript=result.full_transcript,
            patient_id="MRN-65M",
            visit_id="V-2026-001",
            provider_npi="9876543210",
        )

        # Must be parseable with python-hl7
        parsed = hl7.parse(mdm_msg)
        assert parsed is not None

        # Check clinical content in OBX
        obx = next(s for s in mdm_msg.split("\r") if s.startswith("OBX"))
        assert "dyspnea" in obx

    def test_all_required_segments_present(self, dummy_wav_file: Path) -> None:
        mock_response = make_deepgram_mock_response(SAMPLE_UTTERANCES, FULL_TRANSCRIPT)

        with patch("ehr_integration.transcription.batch.DeepgramClient") as mock_cls:
            mock_cls.return_value.listen.rest.v.return_value.transcribe_file.return_value = mock_response
            transcriber = BatchTranscriber(api_key="test-key")
            result = transcriber.transcribe_file(dummy_wav_file)

        mdm_msg = MDMBuilder.build_t02(
            transcript=result.full_transcript,
            patient_id="MRN-65M",
            visit_id="V-2026-001",
            provider_npi="9876543210",
        )

        segs = {s.split("|")[0] for s in mdm_msg.split("\r")}
        for required in ("MSH", "EVN", "PID", "PV1", "TXA", "OBX"):
            assert required in segs, f"Missing required segment: {required}"


class TestCernerFHIRSubmissionFlow:
    """Batch transcription → FHIR DocumentReference → Cerner POST."""

    @pytest.fixture
    def cerner_client(self) -> CernerFHIRClient:
        session = MagicMock()
        token_resp = MagicMock()
        token_resp.json.return_value = {"access_token": "cerner-flow-token"}
        token_resp.raise_for_status = MagicMock()
        fhir_resp = MagicMock()
        fhir_resp.status_code = 201
        fhir_resp.json.return_value = {"resourceType": "DocumentReference", "id": "cdr-001"}
        fhir_resp.raise_for_status = MagicMock()
        session.post.side_effect = [token_resp, fhir_resp]
        return CernerFHIRClient(
            base_url="https://fhir-ehr.cerner.com/r4/tenant",
            token_url="https://authorization.cerner.com/token",
            session=session,
        )

    def test_full_cerner_submission_flow(
        self, dummy_wav_file: Path, cerner_client: CernerFHIRClient
    ) -> None:
        mock_response = make_deepgram_mock_response(SAMPLE_UTTERANCES, FULL_TRANSCRIPT)

        with patch("ehr_integration.transcription.batch.DeepgramClient") as mock_cls:
            mock_cls.return_value.listen.rest.v.return_value.transcribe_file.return_value = mock_response
            pipeline = DictationPipeline(api_key="test-key")
            result = pipeline.transcribe(dummy_wav_file)

        doc_ref = pipeline.to_fhir(result, patient_id="cerner-patient", encounter_id="cerner-enc")

        cerner_client.authenticate(client_id="c-id", client_secret="c-secret")
        response = cerner_client.submit_document_reference(doc_ref)

        assert response.status_code == 201

    def test_dictation_to_hl7_mdm(self, dummy_wav_file: Path) -> None:
        mock_response = make_deepgram_mock_response(SAMPLE_UTTERANCES, FULL_TRANSCRIPT)

        with patch("ehr_integration.transcription.batch.DeepgramClient") as mock_cls:
            mock_cls.return_value.listen.rest.v.return_value.transcribe_file.return_value = mock_response
            pipeline = DictationPipeline(api_key="test-key")
            result = pipeline.transcribe(dummy_wav_file)

        mdm = pipeline.to_hl7_mdm(
            result,
            patient_id="MRN-65M",
            visit_id="V-2026",
            provider_npi="9876543210",
        )

        parsed = hl7.parse(mdm)
        assert parsed is not None
        assert "MDM^T02" in mdm
