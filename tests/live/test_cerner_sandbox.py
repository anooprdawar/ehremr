"""Live Cerner Ignite sandbox tests.

Requires:
  CERNER_CLIENT_ID      — from code.cerner.com developer portal
  CERNER_CLIENT_SECRET  — from code.cerner.com
  CERNER_TOKEN_URL      — tenant-specific token endpoint
  CERNER_BASE_URL       — tenant-specific FHIR R4 base (optional, has default)

Getting sandbox credentials:
  1. Create a free account at https://code.cerner.com
  2. Register a new app (system account, R4)
  3. Note your client_id and client_secret
  4. Find your tenant token URL in the app registration

Run:
  export CERNER_CLIENT_ID=your_client_id
  export CERNER_CLIENT_SECRET=your_secret
  export CERNER_TOKEN_URL=https://authorization.cerner.com/tenants/YOUR_TENANT/...
  pytest tests/live/test_cerner_sandbox.py -v -m live
"""

from __future__ import annotations

import os
import pytest

from ehr_integration.transcription.models import Utterance
from ehr_integration.fhir.document_reference import DocumentReferenceBuilder
from ehr_integration.ehr.cerner_client import CernerFHIRClient
from tests.live.conftest import skip_no_cerner

pytestmark = [pytest.mark.live, skip_no_cerner]

_DEFAULT_BASE = "https://fhir-ehr-code.cerner.com/r4/ec2458f2-1e24-41c8-b71b-0e701af7583d"

SAMPLE_UTTERANCES = [
    Utterance(speaker=0, transcript="Cerner sandbox test note — patient stable.", start=0.0, end=3.0, confidence=0.99),
]


class TestCernerSandbox:

    @pytest.fixture(scope="class")
    def authenticated_client(self, cerner_credentials) -> CernerFHIRClient:
        base_url = os.environ.get("CERNER_BASE_URL", _DEFAULT_BASE)
        client = CernerFHIRClient(
            base_url=base_url,
            token_url=cerner_credentials["token_url"],
        )
        client.authenticate(
            client_id=cerner_credentials["client_id"],
            client_secret=cerner_credentials["client_secret"],
        )
        return client

    def test_authentication_returns_token(self, cerner_credentials) -> None:
        base_url = os.environ.get("CERNER_BASE_URL", _DEFAULT_BASE)
        client = CernerFHIRClient(
            base_url=base_url,
            token_url=cerner_credentials["token_url"],
        )
        token = client.authenticate(
            client_id=cerner_credentials["client_id"],
            client_secret=cerner_credentials["client_secret"],
        )
        assert token
        assert len(token) > 20

    def test_submit_document_reference_returns_201(
        self, authenticated_client: CernerFHIRClient
    ) -> None:
        doc = DocumentReferenceBuilder.from_transcript(
            SAMPLE_UTTERANCES,
            patient_id="12724066",  # Cerner sandbox test patient
            encounter_id="97953483",  # Cerner sandbox test encounter
            doc_type_code="progress_note",
        )
        response = authenticated_client.submit_document_reference(doc)
        assert response.status_code == 201, (
            f"Expected 201, got {response.status_code}: {response.text[:200]}"
        )

    def test_submitted_resource_has_id(self, authenticated_client: CernerFHIRClient) -> None:
        doc = DocumentReferenceBuilder.from_transcript(
            SAMPLE_UTTERANCES,
            patient_id="12724066",
            encounter_id="97953483",
        )
        response = authenticated_client.submit_document_reference(doc)
        if response.status_code == 201:
            body = response.json()
            assert body.get("id")
            assert body.get("resourceType") == "DocumentReference"
