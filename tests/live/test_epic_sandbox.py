"""Live Epic App Orchard sandbox tests.

Requires:
  EPIC_CLIENT_ID          — from apps.epic.com developer portal
  EPIC_PRIVATE_KEY_PATH   — path to RSA private key registered with Epic

Epic sandbox base URL: https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4
Token URL:             https://fhir.epic.com/interconnect-fhir-oauth/oauth2/token

Getting sandbox credentials:
  1. Create a free account at https://fhir.epic.com
  2. Register a new app (backend services, non-production)
  3. Generate an RSA key pair, register the public key with Epic
  4. Set EPIC_CLIENT_ID and EPIC_PRIVATE_KEY_PATH

Run:
  export EPIC_CLIENT_ID=your_client_id
  export EPIC_PRIVATE_KEY_PATH=./keys/epic_rsa.pem
  pytest tests/live/test_epic_sandbox.py -v -m live
"""

from __future__ import annotations

import pytest

from ehr_integration.transcription.models import Utterance
from ehr_integration.fhir.document_reference import DocumentReferenceBuilder
from ehr_integration.ehr.epic_client import EpicFHIRClient
from tests.live.conftest import skip_no_epic

pytestmark = [pytest.mark.live, skip_no_epic]

EPIC_BASE_URL  = "https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4"
EPIC_TOKEN_URL = "https://fhir.epic.com/interconnect-fhir-oauth/oauth2/token"

SAMPLE_UTTERANCES = [
    Utterance(speaker=0, transcript="Sandbox test note — patient stable.", start=0.0, end=3.0, confidence=0.99),
]


class TestEpicSandbox:

    @pytest.fixture(scope="class")
    def authenticated_client(self, epic_credentials) -> EpicFHIRClient:
        client = EpicFHIRClient(
            base_url=EPIC_BASE_URL,
            token_url=EPIC_TOKEN_URL,
        )
        client.authenticate(
            client_id=epic_credentials["client_id"],
            private_key_path=epic_credentials["private_key_path"],
        )
        return client

    def test_authentication_returns_token(self, epic_credentials) -> None:
        client = EpicFHIRClient(base_url=EPIC_BASE_URL, token_url=EPIC_TOKEN_URL)
        token = client.authenticate(
            client_id=epic_credentials["client_id"],
            private_key_path=epic_credentials["private_key_path"],
        )
        assert token
        assert len(token) > 20

    def test_submit_document_reference_returns_201(
        self, authenticated_client: EpicFHIRClient
    ) -> None:
        doc = DocumentReferenceBuilder.from_transcript(
            SAMPLE_UTTERANCES,
            patient_id="eD3NT2C.bpwdHdPlWePHU5w3",  # Epic sandbox test patient
            encounter_id="eKDXLHBXCkr8S3ylzdFWgjA3",  # Epic sandbox test encounter
            doc_type_code="progress_note",
        )
        response = authenticated_client.submit_document_reference(doc)
        assert response.status_code == 201, (
            f"Expected 201, got {response.status_code}: {response.text[:200]}"
        )

    def test_submitted_resource_has_id(self, authenticated_client: EpicFHIRClient) -> None:
        doc = DocumentReferenceBuilder.from_transcript(
            SAMPLE_UTTERANCES,
            patient_id="eD3NT2C.bpwdHdPlWePHU5w3",
            encounter_id="eKDXLHBXCkr8S3ylzdFWgjA3",
        )
        response = authenticated_client.submit_document_reference(doc)
        if response.status_code == 201:
            body = response.json()
            assert body.get("id"), "Created resource must have an id"
            assert body.get("resourceType") == "DocumentReference"
