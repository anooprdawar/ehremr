"""Contact center / nurse triage use case.

Patient calls a triage line. The call is streamed to Deepgram; the
resulting transcript is posted to the EHR as a clinical note.
"""

from __future__ import annotations

from ..transcription.models import ClinicalTranscriptionResult
from ..fhir.document_reference import DocumentReferenceBuilder
from ..hl7.oru_builder import ORUBuilder


class ContactCenterPipeline:
    """Contact center: streaming call transcript → FHIR or HL7 ORU."""

    @staticmethod
    def to_fhir(
        result: ClinicalTranscriptionResult,
        patient_id: str,
        encounter_id: str,
    ) -> dict:
        """Build a FHIR DocumentReference from a call transcript."""
        return DocumentReferenceBuilder.from_transcript(
            utterances=result.utterances or [],
            patient_id=patient_id,
            encounter_id=encounter_id,
            doc_type_code="progress_note",
            title="Nurse Triage Call Transcript",
        )

    @staticmethod
    def to_hl7_oru(
        result: ClinicalTranscriptionResult,
        patient_id: str,
        order_id: str,
        provider_npi: str,
    ) -> str:
        """Build an HL7v2 ORU^R01 message from a call transcript."""
        return ORUBuilder.build_r01(
            transcript=result.full_transcript,
            patient_id=patient_id,
            order_id=order_id,
            provider_npi=provider_npi,
        )
