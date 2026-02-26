"""Ambient clinical documentation use case.

Combines streaming transcription with automatic FHIR DocumentReference creation.
The physician's voice is captured in real time; the note is posted to the EHR
when the encounter ends.
"""

from __future__ import annotations

from ..fhir.document_reference import DocumentReferenceBuilder
from ..ehr.base_ehr_client import BaseEHRClient
from ..transcription.models import Utterance


class AmbientDocumentationPipeline:
    """Ambient documentation: streaming transcription → FHIR DocumentReference → EHR."""

    def __init__(self, ehr_client: BaseEHRClient) -> None:
        self._ehr = ehr_client
        self._utterances: list[Utterance] = []

    def add_utterance(self, utterance: Utterance) -> None:
        """Accumulate an utterance from streaming transcription."""
        self._utterances.append(utterance)

    def finalize_and_submit(
        self,
        patient_id: str,
        encounter_id: str,
        doc_type_code: str = "progress_note",
        author_practitioner_id: str | None = None,
    ) -> dict:
        """Build a FHIR DocumentReference and post it to the EHR.

        Returns:
            Dict with 'doc_ref' (the resource) and 'status_code' (HTTP response).
        """
        doc_ref = DocumentReferenceBuilder.from_transcript(
            utterances=self._utterances,
            patient_id=patient_id,
            encounter_id=encounter_id,
            doc_type_code=doc_type_code,
            author_practitioner_id=author_practitioner_id,
        )
        response = self._ehr.submit_document_reference(doc_ref)
        response.raise_for_status()
        return {"doc_ref": doc_ref, "status_code": response.status_code}
