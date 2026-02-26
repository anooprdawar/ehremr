"""Cerner Ignite FHIR R4 client using SMART on FHIR client credentials flow."""

from __future__ import annotations

import requests

from .base_ehr_client import BaseEHRClient


class CernerFHIRClient(BaseEHRClient):
    """FHIR R4 client for Cerner Ignite (SMART on FHIR client credentials)."""

    def __init__(
        self,
        base_url: str,
        token_url: str,
        session: requests.Session | None = None,
    ) -> None:
        super().__init__(base_url, session)
        self._token_url = token_url

    def authenticate(  # type: ignore[override]
        self,
        client_id: str,
        client_secret: str,
        scope: str = "system/DocumentReference.write",
    ) -> str:
        """Obtain an access token using client credentials grant.

        Args:
            client_id: Cerner client ID.
            client_secret: Cerner client secret.
            scope: OAuth2 scope(s) to request.

        Returns:
            The access token string.
        """
        response = self._session.post(
            self._token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
                "scope": scope,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response.raise_for_status()
        self._access_token = response.json()["access_token"]
        return self._access_token
