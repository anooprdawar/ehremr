"""HL7v2 ORU^R01 (Observation Result Unsolicited) message builder.

ORU^R01 is used to transmit clinical observations and results,
including transcribed notes as text observations.
"""

from __future__ import annotations

from datetime import datetime, timezone


class ORUBuilder:
    """Build HL7v2 ORU^R01 messages from clinical transcripts."""

    FIELD_SEP = "|"
    ENCODING_CHARS = "^~\\&"

    @classmethod
    def build_r01(
        cls,
        transcript: str,
        patient_id: str,
        order_id: str,
        provider_npi: str,
        loinc_code: str = "11506-3",
        loinc_display: str = "Progress note",
        sending_app: str = "DEEPGRAM",
        sending_facility: str = "EHR",
        receiving_app: str = "EHR_SYSTEM",
        receiving_facility: str = "FACILITY",
    ) -> str:
        """Build an ORU^R01 message string."""
        now = datetime.now(timezone.utc)
        ts = now.strftime("%Y%m%d%H%M%S")
        msg_id = f"MSG{now.strftime('%Y%m%d%H%M%S%f')[:18]}"

        segments = [
            cls._msh(ts, msg_id, sending_app, sending_facility, receiving_app, receiving_facility),
            cls._pid(patient_id),
            cls._obr(order_id, ts, provider_npi, loinc_code, loinc_display),
            cls._obx(transcript, loinc_code, loinc_display),
        ]
        return "\r".join(segments)

    @classmethod
    def _msh(
        cls,
        ts: str,
        msg_id: str,
        sending_app: str,
        sending_facility: str,
        receiving_app: str,
        receiving_facility: str,
    ) -> str:
        sep = cls.FIELD_SEP
        enc = cls.ENCODING_CHARS
        return (
            f"MSH{sep}{enc}{sep}{sending_app}{sep}{sending_facility}{sep}"
            f"{receiving_app}{sep}{receiving_facility}{sep}{ts}{sep}{sep}"
            f"ORU^R01{sep}{msg_id}{sep}P{sep}2.5.1"
        )

    @classmethod
    def _pid(cls, patient_id: str) -> str:
        return f"PID|1||{patient_id}^^^MRN||LastName^FirstName|||U"

    @classmethod
    def _obr(
        cls,
        order_id: str,
        ts: str,
        provider_npi: str,
        loinc_code: str,
        loinc_display: str,
    ) -> str:
        return (
            f"OBR|1|{order_id}||{loinc_code}^{loinc_display}^LN|||{ts}|||"
            f"{provider_npi}^Provider^Name"
        )

    @classmethod
    def _obx(cls, transcript: str, loinc_code: str, loinc_display: str) -> str:
        safe = transcript.replace("|", "\\F\\").replace("\r", " ").replace("\n", " ")
        return f"OBX|1|TX|{loinc_code}^{loinc_display}^LN||{safe}||||||F"
