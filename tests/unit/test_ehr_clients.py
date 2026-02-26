"""Unit tests for Epic and Cerner EHR FHIR clients."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from ehr_integration.ehr.epic_client import EpicFHIRClient
from ehr_integration.ehr.cerner_client import CernerFHIRClient
from ehr_integration.ehr.base_ehr_client import BaseEHRClient
from ehr_integration.transcription.models import Utterance
from ehr_integration.fhir.document_reference import DocumentReferenceBuilder


SAMPLE_DOC_REF = DocumentReferenceBuilder.from_transcript(
    utterances=[Utterance(speaker=0, transcript="Test note.", start=0.0, end=2.0, confidence=0.99)],
    patient_id="p-test",
    encounter_id="e-test",
)


class TestEpicFHIRClientAuth:
    def _make_client(self, session: MagicMock) -> EpicFHIRClient:
        return EpicFHIRClient(
            base_url="https://fhir.epic.com/api/FHIR/R4",
            token_url="https://fhir.epic.com/oauth2/token",
            session=session,
        )

    def test_authenticate_returns_token(self, mock_epic_session: MagicMock) -> None:
        client = self._make_client(mock_epic_session)
        with patch("ehr_integration.ehr.epic_client.jwt.encode", return_value="signed.jwt.token"):
            token = client.authenticate(client_id="test-client", private_key=b"fake-key")
        assert token == "epic-test-token"

    def test_authenticate_posts_to_token_url(self, mock_epic_session: MagicMock) -> None:
        client = self._make_client(mock_epic_session)
        with patch("ehr_integration.ehr.epic_client.jwt.encode", return_value="signed.jwt.token"):
            client.authenticate(client_id="test-client", private_key=b"fake-key")

        post_call = mock_epic_session.post.call_args_list[0]
        assert "https://fhir.epic.com/oauth2/token" in post_call[0][0]

    def test_authenticate_uses_jwt_bearer_grant(self, mock_epic_session: MagicMock) -> None:
        client = self._make_client(mock_epic_session)
        with patch("ehr_integration.ehr.epic_client.jwt.encode", return_value="signed.jwt.token"):
            client.authenticate(client_id="test-client", private_key=b"fake-key")

        post_data = mock_epic_session.post.call_args_list[0][1]["data"]
        assert post_data["grant_type"] == "client_credentials"
        assert "jwt-bearer" in post_data["client_assertion_type"]

    def test_authenticate_private_key_path(self, mock_epic_session: MagicMock, tmp_path) -> None:
        key_file = tmp_path / "private_key.pem"
        key_file.write_bytes(b"-----BEGIN RSA PRIVATE KEY-----\nfake\n-----END RSA PRIVATE KEY-----\n")
        client = self._make_client(mock_epic_session)
        with patch("ehr_integration.ehr.epic_client.jwt.encode", return_value="signed.jwt.token"):
            token = client.authenticate(client_id="test-client", private_key_path=key_file)
        assert token == "epic-test-token"

    def test_authenticate_raises_without_key(self, mock_epic_session: MagicMock) -> None:
        client = self._make_client(mock_epic_session)
        with pytest.raises(ValueError, match="private_key"):
            client.authenticate(client_id="test-client")


class TestEpicFHIRClientSubmit:
    def test_submit_document_reference_posts_to_fhir_endpoint(self, mock_epic_session: MagicMock) -> None:
        client = EpicFHIRClient(
            base_url="https://fhir.epic.com/api/FHIR/R4",
            token_url="https://fhir.epic.com/oauth2/token",
            session=mock_epic_session,
        )
        with patch("ehr_integration.ehr.epic_client.jwt.encode", return_value="signed.jwt.token"):
            client.authenticate(client_id="test-client", private_key=b"fake-key")

        response = client.submit_document_reference(SAMPLE_DOC_REF)
        assert response.status_code == 201

        fhir_post = mock_epic_session.post.call_args_list[1]
        assert "DocumentReference" in fhir_post[0][0]

    def test_submit_includes_bearer_token(self, mock_epic_session: MagicMock) -> None:
        client = EpicFHIRClient(
            base_url="https://fhir.epic.com/api/FHIR/R4",
            token_url="https://fhir.epic.com/oauth2/token",
            session=mock_epic_session,
        )
        with patch("ehr_integration.ehr.epic_client.jwt.encode", return_value="signed.jwt.token"):
            client.authenticate(client_id="test-client", private_key=b"fake-key")
        client.submit_document_reference(SAMPLE_DOC_REF)

        fhir_post = mock_epic_session.post.call_args_list[1]
        headers = fhir_post[1]["headers"]
        assert headers["Authorization"] == "Bearer epic-test-token"

    def test_submit_without_auth_raises(self) -> None:
        session = MagicMock()
        client = EpicFHIRClient(
            base_url="https://fhir.epic.com/api/FHIR/R4",
            session=session,
        )
        with pytest.raises(RuntimeError, match="Not authenticated"):
            client.submit_document_reference(SAMPLE_DOC_REF)

    def test_submit_content_type_fhir_json(self, mock_epic_session: MagicMock) -> None:
        client = EpicFHIRClient(
            base_url="https://fhir.epic.com/api/FHIR/R4",
            token_url="https://fhir.epic.com/oauth2/token",
            session=mock_epic_session,
        )
        with patch("ehr_integration.ehr.epic_client.jwt.encode", return_value="signed.jwt.token"):
            client.authenticate(client_id="test-client", private_key=b"fake-key")
        client.submit_document_reference(SAMPLE_DOC_REF)

        fhir_post = mock_epic_session.post.call_args_list[1]
        headers = fhir_post[1]["headers"]
        assert headers["Content-Type"] == "application/fhir+json"


class TestCernerFHIRClientAuth:
    def _make_client(self, session: MagicMock) -> CernerFHIRClient:
        return CernerFHIRClient(
            base_url="https://fhir-ehr.cerner.com/r4/tenant",
            token_url="https://authorization.cerner.com/token",
            session=session,
        )

    def test_authenticate_returns_token(self, mock_cerner_session: MagicMock) -> None:
        client = self._make_client(mock_cerner_session)
        token = client.authenticate(client_id="cerner-id", client_secret="cerner-secret")
        assert token == "cerner-test-token"

    def test_authenticate_client_credentials_grant(self, mock_cerner_session: MagicMock) -> None:
        client = self._make_client(mock_cerner_session)
        client.authenticate(client_id="cerner-id", client_secret="cerner-secret")

        post_data = mock_cerner_session.post.call_args_list[0][1]["data"]
        assert post_data["grant_type"] == "client_credentials"
        assert post_data["client_id"] == "cerner-id"
        assert post_data["client_secret"] == "cerner-secret"

    def test_submit_document_reference_201(self, mock_cerner_session: MagicMock) -> None:
        client = self._make_client(mock_cerner_session)
        client.authenticate(client_id="cerner-id", client_secret="cerner-secret")
        response = client.submit_document_reference(SAMPLE_DOC_REF)
        assert response.status_code == 201
