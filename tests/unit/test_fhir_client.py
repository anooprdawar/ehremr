"""Unit tests for the generic FHIR HTTP client."""

from __future__ import annotations

import pytest
import requests_mock as req_mock

from ehr_integration.fhir.fhir_client import FHIRClient


BASE_URL = "https://fhir.example.com/r4"
SAMPLE_DOC_REF = {"resourceType": "DocumentReference", "status": "current"}


class TestFHIRClientPost:
    def test_post_resource_sends_to_correct_url(self) -> None:
        with req_mock.Mocker() as m:
            m.post(f"{BASE_URL}/DocumentReference", json={"id": "dr-001"}, status_code=201)
            client = FHIRClient(BASE_URL)
            response = client.post_resource("DocumentReference", SAMPLE_DOC_REF)
        assert response.status_code == 201

    def test_post_resource_sets_fhir_content_type(self) -> None:
        with req_mock.Mocker() as m:
            m.post(f"{BASE_URL}/DocumentReference", json={}, status_code=201)
            client = FHIRClient(BASE_URL)
            client.post_resource("DocumentReference", SAMPLE_DOC_REF)
            assert m.last_request.headers["Content-Type"] == "application/fhir+json"

    def test_post_resource_custom_headers_merged(self) -> None:
        with req_mock.Mocker() as m:
            m.post(f"{BASE_URL}/DocumentReference", json={}, status_code=201)
            client = FHIRClient(BASE_URL)
            client.post_resource(
                "DocumentReference",
                SAMPLE_DOC_REF,
                headers={"Authorization": "Bearer tok"},
            )
            assert m.last_request.headers["Authorization"] == "Bearer tok"

    def test_post_resource_strips_trailing_slash(self) -> None:
        with req_mock.Mocker() as m:
            m.post(f"{BASE_URL}/Patient", json={}, status_code=201)
            client = FHIRClient(BASE_URL + "/")  # trailing slash
            response = client.post_resource("Patient", {"resourceType": "Patient"})
        assert response.status_code == 201


class TestFHIRClientGet:
    def test_get_resource_correct_url(self) -> None:
        with req_mock.Mocker() as m:
            m.get(f"{BASE_URL}/Patient/p-001", json={"resourceType": "Patient", "id": "p-001"})
            client = FHIRClient(BASE_URL)
            response = client.get_resource("Patient", "p-001")
        assert response.status_code == 200
        assert response.json()["id"] == "p-001"

    def test_get_resource_accept_header(self) -> None:
        with req_mock.Mocker() as m:
            m.get(f"{BASE_URL}/Encounter/e-001", json={})
            client = FHIRClient(BASE_URL)
            client.get_resource("Encounter", "e-001")
            assert m.last_request.headers["Accept"] == "application/fhir+json"
