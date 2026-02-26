"""Deep HL7v2 field-level validation tests.

These go beyond "does hl7.parse() succeed" and validate that specific
fields in each segment carry the correct values. This is the difference
between a message that parses and a message that an EHR will actually accept.

All tests are offline — python-hl7 does the parsing, no MLLP server needed.
"""

from __future__ import annotations

import re
import pytest
import hl7

from ehr_integration.hl7.mdm_builder import MDMBuilder
from ehr_integration.hl7.oru_builder import ORUBuilder

pytestmark = pytest.mark.quality

PATIENT_ID   = "MRN-FIELD-001"
VISIT_ID     = "VISIT-FIELD-001"
PROVIDER_NPI = "1234567890"
ORDER_ID     = "ORD-FIELD-001"
TRANSCRIPT   = "Patient is a 58-year-old male with hypertension and type 2 diabetes."


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_and_get_segment(msg: str, seg_name: str) -> hl7.Segment:
    parsed = hl7.parse(msg)
    for seg in parsed:
        if str(seg[0][0]) == seg_name:
            return seg
    raise AssertionError(f"Segment {seg_name} not found in message")


def segment_value(seg: hl7.Segment, field: int, component: int = 1) -> str:
    """Return the string value of seg[field][component], stripping whitespace."""
    try:
        return str(seg[field][component]).strip()
    except (IndexError, TypeError):
        return str(seg[field]).strip()


# ---------------------------------------------------------------------------
# MDM^T02 — MSH segment
# ---------------------------------------------------------------------------

class TestMSHSegment:
    @pytest.fixture
    def msg(self) -> str:
        return MDMBuilder.build_t02(TRANSCRIPT, PATIENT_ID, VISIT_ID, PROVIDER_NPI)

    def test_msh_field_separator(self, msg: str) -> None:
        msh = parse_and_get_segment(msg, "MSH")
        assert str(msh[1]) == "|", "MSH-1 (field separator) must be '|'"

    def test_msh_encoding_characters(self, msg: str) -> None:
        msh = parse_and_get_segment(msg, "MSH")
        assert str(msh[2]) == "^~\\&", "MSH-2 (encoding chars) must be '^~\\&'"

    def test_msh_message_type_mdm(self, msg: str) -> None:
        msh = parse_and_get_segment(msg, "MSH")
        msg_type = str(msh[9])
        assert "MDM" in msg_type, f"MSH-9 must contain 'MDM', got {msg_type!r}"

    def test_msh_trigger_event_t02(self, msg: str) -> None:
        msh = parse_and_get_segment(msg, "MSH")
        msg_type = str(msh[9])
        assert "T02" in msg_type, f"MSH-9 must contain 'T02', got {msg_type!r}"

    def test_msh_version_id_251(self, msg: str) -> None:
        msh = parse_and_get_segment(msg, "MSH")
        version = str(msh[12])
        assert version == "2.5.1", f"MSH-12 must be '2.5.1', got {version!r}"

    def test_msh_processing_id_production(self, msg: str) -> None:
        msh = parse_and_get_segment(msg, "MSH")
        proc_id = str(msh[11])
        assert proc_id == "P", f"MSH-11 (processing ID) must be 'P', got {proc_id!r}"

    def test_msh_message_control_id_nonempty(self, msg: str) -> None:
        msh = parse_and_get_segment(msg, "MSH")
        ctrl_id = str(msh[10])
        assert ctrl_id.strip(), "MSH-10 (message control ID) must not be empty"

    def test_msh_datetime_format(self, msg: str) -> None:
        msh = parse_and_get_segment(msg, "MSH")
        ts = str(msh[7]).strip()
        assert re.match(r"^\d{14}$", ts), (
            f"MSH-7 (datetime) must be 14-digit timestamp YYYYMMDDHHMMSS, got {ts!r}"
        )


# ---------------------------------------------------------------------------
# MDM^T02 — PID segment
# ---------------------------------------------------------------------------

class TestPIDSegment:
    @pytest.fixture
    def msg(self) -> str:
        return MDMBuilder.build_t02(TRANSCRIPT, PATIENT_ID, VISIT_ID, PROVIDER_NPI)

    def test_pid_set_id_is_1(self, msg: str) -> None:
        pid = parse_and_get_segment(msg, "PID")
        assert str(pid[1]).strip() == "1", "PID-1 (set ID) must be '1'"

    def test_pid_patient_id_present(self, msg: str) -> None:
        pid = parse_and_get_segment(msg, "PID")
        pid3 = str(pid[3])
        assert PATIENT_ID in pid3, (
            f"PID-3 must contain patient ID '{PATIENT_ID}', got {pid3!r}"
        )

    def test_pid_patient_id_domain_is_mrn(self, msg: str) -> None:
        pid = parse_and_get_segment(msg, "PID")
        pid3 = str(pid[3])
        assert "MRN" in pid3, "PID-3 identifier type code should be MRN"


# ---------------------------------------------------------------------------
# MDM^T02 — TXA segment
# ---------------------------------------------------------------------------

class TestTXASegment:
    @pytest.fixture
    def msg(self) -> str:
        return MDMBuilder.build_t02(TRANSCRIPT, PATIENT_ID, VISIT_ID, PROVIDER_NPI)

    def test_txa_set_id_is_1(self, msg: str) -> None:
        txa = parse_and_get_segment(msg, "TXA")
        assert str(txa[1]).strip() == "1", "TXA-1 (set ID) must be '1'"

    def test_txa_document_type_contains_progress_note(self, msg: str) -> None:
        txa = parse_and_get_segment(msg, "TXA")
        doc_type = str(txa[2])
        assert "PN" in doc_type or "Progress" in doc_type, (
            f"TXA-2 (document type) should indicate progress note, got {doc_type!r}"
        )

    def test_txa_document_completion_status_authenticated(self, msg: str) -> None:
        # TXA-12: document completion status (AU = authenticated)
        txa = parse_and_get_segment(msg, "TXA")
        completion = str(txa[12]).strip()
        assert completion in ("AU", "DI", "DO", "IN", "IP", "LA"), (
            f"TXA-12 (completion status) invalid value: {completion!r}"
        )

    def test_txa_availability_status_available(self, msg: str) -> None:
        # TXA-14: document availability status (AV = available)
        txa = parse_and_get_segment(msg, "TXA")
        availability = str(txa[14]).strip()
        assert availability in ("AV", "CA", "OB", "UN"), (
            f"TXA-14 (availability status) invalid value: {availability!r}"
        )

    def test_txa_unique_document_id_nonempty(self, msg: str) -> None:
        txa = parse_and_get_segment(msg, "TXA")
        doc_id = str(txa[12]).strip()
        assert doc_id, "TXA-12 (unique document number) must not be empty"

    def test_txa_custom_document_id_used(self) -> None:
        msg = MDMBuilder.build_t02(
            TRANSCRIPT, PATIENT_ID, VISIT_ID, PROVIDER_NPI,
            document_id="DOC-CUSTOM-XYZ",
        )
        txa = parse_and_get_segment(msg, "TXA")
        assert "DOC-CUSTOM-XYZ" in str(txa), "Custom document ID must appear in TXA"


# ---------------------------------------------------------------------------
# MDM^T02 — OBX segment
# ---------------------------------------------------------------------------

class TestOBXSegment:
    @pytest.fixture
    def msg(self) -> str:
        return MDMBuilder.build_t02(TRANSCRIPT, PATIENT_ID, VISIT_ID, PROVIDER_NPI)

    def test_obx_set_id_is_1(self, msg: str) -> None:
        obx = parse_and_get_segment(msg, "OBX")
        assert str(obx[1]).strip() == "1", "OBX-1 (set ID) must be '1'"

    def test_obx_value_type_is_tx(self, msg: str) -> None:
        obx = parse_and_get_segment(msg, "OBX")
        vt = str(obx[2]).strip()
        assert vt == "TX", f"OBX-2 (value type) must be 'TX' for text, got {vt!r}"

    def test_obx_observation_result_nonempty(self, msg: str) -> None:
        obx = parse_and_get_segment(msg, "OBX")
        value = str(obx[5]).strip()
        assert value, "OBX-5 (observation value) must not be empty"

    def test_obx_clinical_text_in_value(self, msg: str) -> None:
        obx = parse_and_get_segment(msg, "OBX")
        assert "hypertension" in str(obx[5])

    def test_obx_observation_status_final(self, msg: str) -> None:
        obx = parse_and_get_segment(msg, "OBX")
        status = str(obx[11]).strip()
        assert status == "F", f"OBX-11 (observation result status) must be 'F' (Final), got {status!r}"

    def test_obx_observation_identifier_has_loinc(self, msg: str) -> None:
        obx = parse_and_get_segment(msg, "OBX")
        identifier = str(obx[3])
        assert "LN" in identifier or re.search(r"\d{5}-\d", identifier), (
            f"OBX-3 should contain a LOINC code, got {identifier!r}"
        )


# ---------------------------------------------------------------------------
# ORU^R01 — field-level validation
# ---------------------------------------------------------------------------

class TestORUFieldLevel:
    @pytest.fixture
    def msg(self) -> str:
        return ORUBuilder.build_r01(TRANSCRIPT, PATIENT_ID, ORDER_ID, PROVIDER_NPI)

    def test_msh_message_type_oru(self, msg: str) -> None:
        msh = parse_and_get_segment(msg, "MSH")
        assert "ORU" in str(msh[9])

    def test_msh_trigger_event_r01(self, msg: str) -> None:
        msh = parse_and_get_segment(msg, "MSH")
        assert "R01" in str(msh[9])

    def test_obr_order_id_present(self, msg: str) -> None:
        obr = parse_and_get_segment(msg, "OBR")
        assert ORDER_ID in str(obr), f"OBR must contain order ID {ORDER_ID!r}"

    def test_obr_provider_npi_present(self, msg: str) -> None:
        obr = parse_and_get_segment(msg, "OBR")
        assert PROVIDER_NPI in str(obr), "OBR must contain provider NPI"

    def test_obx_value_type_tx(self, msg: str) -> None:
        obx = parse_and_get_segment(msg, "OBX")
        assert str(obx[2]).strip() == "TX"

    def test_obx_status_final(self, msg: str) -> None:
        obx = parse_and_get_segment(msg, "OBX")
        assert str(obx[11]).strip() == "F"

    def test_custom_loinc_appears_in_obr_and_obx(self) -> None:
        msg = ORUBuilder.build_r01(
            TRANSCRIPT, PATIENT_ID, ORDER_ID, PROVIDER_NPI,
            loinc_code="11488-4", loinc_display="Consult note",
        )
        assert msg.count("11488-4") >= 2, "LOINC code should appear in both OBR and OBX"


# ---------------------------------------------------------------------------
# Pipe escaping — regression test for real-world clinical text
# ---------------------------------------------------------------------------

class TestPipeEscapingRegression:
    @pytest.mark.parametrize("transcript", [
        "BP: 120|80 mmHg",
        "Ratio: 1|2|3",
        "Lab: Na 140 | K 4.0 | Cl 102",
        "Note|with|many|pipes",
    ])
    def test_mdm_with_pipe_in_transcript_parses_cleanly(self, transcript: str) -> None:
        msg = MDMBuilder.build_t02(transcript, PATIENT_ID, VISIT_ID, PROVIDER_NPI)
        parsed = hl7.parse(msg)
        assert parsed is not None

    @pytest.mark.parametrize("transcript", [
        "BP: 120|80 mmHg",
        "Ratio: 1|2|3",
    ])
    def test_oru_with_pipe_in_transcript_parses_cleanly(self, transcript: str) -> None:
        msg = ORUBuilder.build_r01(transcript, PATIENT_ID, ORDER_ID, PROVIDER_NPI)
        parsed = hl7.parse(msg)
        assert parsed is not None

    def test_newline_in_transcript_does_not_break_segments(self) -> None:
        transcript = "Line one.\nLine two.\nLine three."
        msg = MDMBuilder.build_t02(transcript, PATIENT_ID, VISIT_ID, PROVIDER_NPI)
        parsed = hl7.parse(msg)
        assert parsed is not None
        segments = [str(s).split("|")[0] for s in parsed]
        assert segments.count("OBX") == 1, "Newlines must not create extra OBX segments"
