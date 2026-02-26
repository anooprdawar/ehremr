"""Generic FHIR R4 HTTP client."""

from __future__ import annotations

import requests


class FHIRClient:
    """Minimal FHIR R4 REST client for posting resources."""

    def __init__(
        self,
        base_url: str,
        session: requests.Session | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._session = session or requests.Session()

    def post_resource(
        self,
        resource_type: str,
        resource: dict,
        headers: dict | None = None,
    ) -> requests.Response:
        """POST a FHIR resource and return the response."""
        url = f"{self.base_url}/{resource_type}"
        default_headers = {"Content-Type": "application/fhir+json"}
        if headers:
            default_headers.update(headers)
        return self._session.post(url, json=resource, headers=default_headers)

    def get_resource(
        self,
        resource_type: str,
        resource_id: str,
        headers: dict | None = None,
    ) -> requests.Response:
        """GET a FHIR resource by type and logical ID."""
        url = f"{self.base_url}/{resource_type}/{resource_id}"
        default_headers = {"Accept": "application/fhir+json"}
        if headers:
            default_headers.update(headers)
        return self._session.get(url, headers=default_headers)
