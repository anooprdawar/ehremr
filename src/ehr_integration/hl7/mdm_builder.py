"""HL7v2 MDM^T02 (Medical Document Management) message builder.

MDM^T02 is the standard HL7v2 message type for transmitting transcribed
clinical documents. Structure: MSH | EVN | PID | PV1 | TXA | OBX
"""

from __future__ import annotations

from datetime import datetime, timezone


class MDMBuilder:
    """Build HL7v2 MDM^T02 messages from clinical transcripts."""

    FIELD_SEP = "|"
    ENCODING_CHARS = "^~\\&"

    @classmethod
    def build_t02(
        cls,
        transcript: str,
        patient_id: str,
        visit_id: str,
        provider_npi: str,
        document_id: str | None = None,
        sending_app: str = "DEEPGRAM",
        sending_facility: str = "EHR",
        receiving_app: str = "EHR_SYSTEM",
        receiving_facility: str = "FACILITY",
    ) -> str:
        """Build an MDM^T02 message string.

        Args:
            transcript: Plain-text clinical transcript.
            patient_id: Patient MRN or identifier.
            visit_id: Visit/encounter number.
            provider_npi: Attending provider NPI.
            document_id: Unique document identifier (auto-generated if None).
            sending_app: MSH-3 sending application name.
            sending_facility: MSH-4 sending facility name.
            receiving_app: MSH-5 receiving application name.
            receiving_facility: MSH-6 receiving facility name.

        Returns:
            HL7v2 MDM^T02 message as a string (segments separated by \\r).
        """
        now = datetime.now(timezone.utc)
        ts = now.strftime("%Y%m%d%H%M%S")
        msg_id = f"MSG{now.strftime('%Y%m%d%H%M%S%f')[:18]}"
        doc_id = document_id or f"DOC{now.strftime('%Y%m%d%H%M%S%f')[:18]}"

        segments = [
            cls._msh(ts, msg_id, sending_app, sending_facility, receiving_app, receiving_facility),
            cls._evn(ts),
            cls._pid(patient_id),
            cls._pv1(visit_id, provider_npi),
            cls._txa(ts, doc_id, provider_npi),
            cls._obx(transcript),
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
            f"MDM^T02{sep}{msg_id}{sep}P{sep}2.5.1"
        )

    @classmethod
    def _evn(cls, ts: str) -> str:
        return f"EVN||{ts}"

    @classmethod
    def _pid(cls, patient_id: str) -> str:
        return f"PID|1||{patient_id}^^^MRN||LastName^FirstName|||U"

    @classmethod
    def _pv1(cls, visit_id: str, provider_npi: str) -> str:
        return f"PV1|1|I|^^^WARD^^BED||||||{provider_npi}^Provider^Name||||||||{visit_id}"

    @classmethod
    def _txa(cls, ts: str, doc_id: str, provider_npi: str) -> str:
        return (
            f"TXA|1|PN^Progress Note|TX|{ts}|{provider_npi}^Provider^Name|"
            f"{ts}|{ts}||{doc_id}||{doc_id}|AU||AV"
        )

    @classmethod
    def _obx(cls, transcript: str) -> str:
        # Escape pipe characters in the transcript to avoid breaking segment parsing
        safe = transcript.replace("|", "\\F\\").replace("\r", " ").replace("\n", " ")
        return f"OBX|1|TX|18842-5^Discharge summary^LN||{safe}||||||F"
