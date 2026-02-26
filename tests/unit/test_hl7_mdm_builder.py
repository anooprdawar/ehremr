"""Unit tests for HL7v2 MDM^T02 and ORU^R01 message builders."""

from __future__ import annotations

import pytest
import hl7

from ehr_integration.hl7.mdm_builder import MDMBuilder
from ehr_integration.hl7.oru_builder import ORUBuilder


SAMPLE_TRANSCRIPT = "Patient presents with chest pain and shortness of breath."
PATIENT_ID = "MRN-001"
VISIT_ID = "VISIT-123"
PROVIDER_NPI = "1234567890"
ORDER_ID = "ORD-456"


class TestMDMBuilderStructure:
    @pytest.fixture
    def mdm_message(self) -> str:
        return MDMBuilder.build_t02(
            transcript=SAMPLE_TRANSCRIPT,
            patient_id=PATIENT_ID,
            visit_id=VISIT_ID,
            provider_npi=PROVIDER_NPI,
        )

    def test_returns_string(self, mdm_message: str) -> None:
        assert isinstance(mdm_message, str)

    def test_msh_segment_present(self, mdm_message: str) -> None:
        segments = mdm_message.split("\r")
        assert segments[0].startswith("MSH|")

    def test_evn_segment_present(self, mdm_message: str) -> None:
        assert any(s.startswith("EVN") for s in mdm_message.split("\r"))

    def test_pid_segment_present(self, mdm_message: str) -> None:
        assert any(s.startswith("PID") for s in mdm_message.split("\r"))

    def test_pv1_segment_present(self, mdm_message: str) -> None:
        assert any(s.startswith("PV1") for s in mdm_message.split("\r"))

    def test_txa_segment_present(self, mdm_message: str) -> None:
        assert any(s.startswith("TXA") for s in mdm_message.split("\r"))

    def test_obx_segment_present(self, mdm_message: str) -> None:
        assert any(s.startswith("OBX") for s in mdm_message.split("\r"))

    def test_message_type_mdm_t02(self, mdm_message: str) -> None:
        msh = mdm_message.split("\r")[0]
        assert "MDM^T02" in msh

    def test_patient_id_in_pid(self, mdm_message: str) -> None:
        pid = next(s for s in mdm_message.split("\r") if s.startswith("PID"))
        assert PATIENT_ID in pid

    def test_provider_npi_in_pv1(self, mdm_message: str) -> None:
        pv1 = next(s for s in mdm_message.split("\r") if s.startswith("PV1"))
        assert PROVIDER_NPI in pv1

    def test_transcript_in_obx(self, mdm_message: str) -> None:
        obx = next(s for s in mdm_message.split("\r") if s.startswith("OBX"))
        assert "chest pain" in obx

    def test_hl7_parseable(self, mdm_message: str) -> None:
        """Message must be parseable by the python-hl7 library."""
        parsed = hl7.parse(mdm_message)
        assert parsed is not None


class TestMDMBuilderPipeEscaping:
    def test_pipe_in_transcript_escaped(self) -> None:
        transcript_with_pipe = "BP: 120|80 mmHg"
        msg = MDMBuilder.build_t02(
            transcript=transcript_with_pipe,
            patient_id=PATIENT_ID,
            visit_id=VISIT_ID,
            provider_npi=PROVIDER_NPI,
        )
        obx = next(s for s in msg.split("\r") if s.startswith("OBX"))
        assert "120|80" not in obx  # raw pipe escaped
        assert "\\F\\" in obx or "120" in obx  # escaped form present


class TestMDMBuilderCustomDocumentId:
    def test_custom_document_id_used(self) -> None:
        msg = MDMBuilder.build_t02(
            transcript=SAMPLE_TRANSCRIPT,
            patient_id=PATIENT_ID,
            visit_id=VISIT_ID,
            provider_npi=PROVIDER_NPI,
            document_id="CUSTOM-DOC-001",
        )
        txa = next(s for s in msg.split("\r") if s.startswith("TXA"))
        assert "CUSTOM-DOC-001" in txa


class TestORUBuilderStructure:
    @pytest.fixture
    def oru_message(self) -> str:
        return ORUBuilder.build_r01(
            transcript=SAMPLE_TRANSCRIPT,
            patient_id=PATIENT_ID,
            order_id=ORDER_ID,
            provider_npi=PROVIDER_NPI,
        )

    def test_message_type_oru_r01(self, oru_message: str) -> None:
        msh = oru_message.split("\r")[0]
        assert "ORU^R01" in msh

    def test_pid_segment_present(self, oru_message: str) -> None:
        assert any(s.startswith("PID") for s in oru_message.split("\r"))

    def test_obr_segment_present(self, oru_message: str) -> None:
        assert any(s.startswith("OBR") for s in oru_message.split("\r"))

    def test_obx_segment_present(self, oru_message: str) -> None:
        assert any(s.startswith("OBX") for s in oru_message.split("\r"))

    def test_transcript_in_obx(self, oru_message: str) -> None:
        obx = next(s for s in oru_message.split("\r") if s.startswith("OBX"))
        assert "chest pain" in obx

    def test_hl7_parseable(self, oru_message: str) -> None:
        parsed = hl7.parse(oru_message)
        assert parsed is not None

    def test_custom_loinc_code(self) -> None:
        msg = ORUBuilder.build_r01(
            transcript=SAMPLE_TRANSCRIPT,
            patient_id=PATIENT_ID,
            order_id=ORDER_ID,
            provider_npi=PROVIDER_NPI,
            loinc_code="11488-4",
            loinc_display="Consult note",
        )
        assert "11488-4" in msg
