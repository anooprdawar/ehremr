"""Physician dictation use case.

Physician dictates a note (batch upload); the transcript is formatted
and submitted as a FHIR DocumentReference or HL7v2 MDM^T02.
"""

from __future__ import annotations

from pathlib import Path

from ..transcription.batch import BatchTranscriber
from ..transcription.models import ClinicalTranscriptionResult
from ..fhir.document_reference import DocumentReferenceBuilder
from ..hl7.mdm_builder import MDMBuilder


class DictationPipeline:
    """Batch dictation: audio file → transcript → FHIR or HL7."""

    def __init__(self, api_key: str | None = None) -> None:
        self._transcriber = BatchTranscriber(api_key=api_key)

    def transcribe(
        self,
        audio_path: str | Path,
        keyterms: list[str] | None = None,
    ) -> ClinicalTranscriptionResult:
        """Transcribe the dictation audio file."""
        return self._transcriber.transcribe_file(audio_path, keyterms=keyterms)

    def to_fhir(
        self,
        result: ClinicalTranscriptionResult,
        patient_id: str,
        encounter_id: str,
        doc_type_code: str = "progress_note",
    ) -> dict:
        """Convert transcription result to a FHIR DocumentReference."""
        return DocumentReferenceBuilder.from_transcript(
            utterances=result.utterances,
            patient_id=patient_id,
            encounter_id=encounter_id,
            doc_type_code=doc_type_code,
        )

    def to_hl7_mdm(
        self,
        result: ClinicalTranscriptionResult,
        patient_id: str,
        visit_id: str,
        provider_npi: str,
    ) -> str:
        """Convert transcription result to an HL7v2 MDM^T02 message."""
        return MDMBuilder.build_t02(
            transcript=result.full_transcript,
            patient_id=patient_id,
            visit_id=visit_id,
            provider_npi=provider_npi,
        )
