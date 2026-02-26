"""Example: build a FHIR DocumentReference and (mock-)submit to Epic.

Usage:
    python examples/submit_to_fhir.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ehr_integration.transcription.models import Utterance
from ehr_integration.fhir.document_reference import DocumentReferenceBuilder
from ehr_integration.ehr.epic_client import EpicFHIRClient


SAMPLE_UTTERANCES = [
    Utterance(speaker=0, transcript="Patient presents with chest pain for two hours.", start=0.0, end=4.1, confidence=0.99),
    Utterance(speaker=1, transcript="The pain started after climbing stairs and is 7 out of 10.", start=5.0, end=9.2, confidence=0.97),
    Utterance(speaker=0, transcript="Any radiation to the arm or jaw?", start=10.1, end=12.3, confidence=0.98),
    Utterance(speaker=1, transcript="No radiation, but I feel short of breath.", start=13.0, end=16.1, confidence=0.96),
]


def main() -> None:
    print("=== FHIR DocumentReference Submission Demo ===\n")

    # 1. Build the FHIR resource
    doc_ref = DocumentReferenceBuilder.from_transcript(
        utterances=SAMPLE_UTTERANCES,
        patient_id="patient-123",
        encounter_id="encounter-456",
        doc_type_code="progress_note",
        author_practitioner_id="practitioner-789",
        title="Emergency Department Visit Note",
    )

    print("Built FHIR DocumentReference:")
    print(json.dumps(doc_ref, indent=2))
    print()

    # 2. Decode and display the embedded transcript
    decoded = DocumentReferenceBuilder.decode_content(doc_ref)
    print("Decoded transcript content:")
    print(decoded)
    print()

    # 3. Mock-authenticate and POST to Epic
    print("Mocking Epic OAuth2 + FHIR POST...")

    mock_token_response = MagicMock()
    mock_token_response.json.return_value = {"access_token": "mock-epic-token-xyz"}
    mock_token_response.raise_for_status = MagicMock()

    mock_fhir_response = MagicMock()
    mock_fhir_response.status_code = 201
    mock_fhir_response.json.return_value = {
        "resourceType": "DocumentReference",
        "id": "dr-created-001",
        "status": "current",
    }
    mock_fhir_response.raise_for_status = MagicMock()

    mock_session = MagicMock()
    mock_session.post.side_effect = [mock_token_response, mock_fhir_response]

    client = EpicFHIRClient(
        base_url="https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4",
        token_url="https://fhir.epic.com/interconnect-fhir-oauth/oauth2/token",
        session=mock_session,
    )

    with patch("ehr_integration.ehr.epic_client.jwt.encode", return_value="mock.signed.jwt"):
        token = client.authenticate(client_id="demo-client-id", private_key=b"fake-rsa-key")

    print(f"Token obtained: {token[:20]}...")

    response = client.submit_document_reference(doc_ref)
    print(f"FHIR POST status: {response.status_code}")
    print(f"Created resource ID: {response.json()['id']}")
    print("\nSubmission demo complete.")


if __name__ == "__main__":
    main()
