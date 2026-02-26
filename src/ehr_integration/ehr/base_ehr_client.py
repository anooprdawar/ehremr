"""Abstract base class for EHR FHIR clients."""

from __future__ import annotations

from abc import ABC, abstractmethod

import requests


class BaseEHRClient(ABC):
    """Abstract base for Epic, Cerner, and other EHR FHIR clients."""

    def __init__(self, base_url: str, session: requests.Session | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self._session = session or requests.Session()
        self._access_token: str | None = None

    @abstractmethod
    def authenticate(self, **kwargs: object) -> str:
        """Obtain an OAuth2 access token. Returns the token string."""

    def submit_document_reference(self, doc_ref: dict) -> requests.Response:
        """POST a FHIR DocumentReference to the EHR.

        Args:
            doc_ref: A FHIR R4 DocumentReference dict.

        Returns:
            requests.Response (201 Created on success).
        """
        headers = self._auth_headers()
        headers["Content-Type"] = "application/fhir+json"
        return self._session.post(
            f"{self.base_url}/DocumentReference",
            json=doc_ref,
            headers=headers,
        )

    def _auth_headers(self) -> dict[str, str]:
        if not self._access_token:
            raise RuntimeError("Not authenticated. Call authenticate() first.")
        return {"Authorization": f"Bearer {self._access_token}"}
