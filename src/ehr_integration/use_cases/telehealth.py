"""Telehealth transcription use case.

Both the provider and patient are on a video call; audio streams are
captured separately and diarized by Deepgram.
"""

from __future__ import annotations

from ..transcription.models import ClinicalTranscriptionResult, Utterance
from ..fhir.document_reference import DocumentReferenceBuilder


SPEAKER_PROVIDER = 0
SPEAKER_PATIENT = 1


class TelehealthPipeline:
    """Telehealth: diarized transcript → structured SOAP note → FHIR."""

    @staticmethod
    def separate_speakers(result: ClinicalTranscriptionResult) -> dict[str, list[Utterance]]:
        """Split utterances into provider and patient tracks."""
        provider: list[Utterance] = []
        patient: list[Utterance] = []
        for u in result.utterances or []:
            if u.speaker == SPEAKER_PROVIDER:
                provider.append(u)
            else:
                patient.append(u)
        return {"provider": provider, "patient": patient}

    @staticmethod
    def to_fhir(
        result: ClinicalTranscriptionResult,
        patient_id: str,
        encounter_id: str,
    ) -> dict:
        """Build a FHIR DocumentReference (consult note) from telehealth transcript."""
        return DocumentReferenceBuilder.from_transcript(
            utterances=result.utterances or [],
            patient_id=patient_id,
            encounter_id=encounter_id,
            doc_type_code="consult_note",
            title="Telehealth Visit Transcript",
        )
