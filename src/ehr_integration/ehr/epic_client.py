"""Epic FHIR R4 client using App Orchard backend services (JWT) OAuth2 flow.

Epic's backend services flow:
  1. Build a JWT signed with your RSA private key.
  2. POST to Epic's token endpoint.
  3. Use the returned access token as Bearer on all FHIR API calls.
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path

import jwt
import requests

from .base_ehr_client import BaseEHRClient


_EPIC_TOKEN_PATH = "/oauth2/token"


class EpicFHIRClient(BaseEHRClient):
    """FHIR R4 client for Epic App Orchard (backend services JWT flow)."""

    def __init__(
        self,
        base_url: str,
        token_url: str | None = None,
        session: requests.Session | None = None,
    ) -> None:
        super().__init__(base_url, session)
        self._token_url = token_url or f"{base_url}{_EPIC_TOKEN_PATH}"

    def authenticate(  # type: ignore[override]
        self,
        client_id: str,
        private_key: str | bytes | None = None,
        private_key_path: str | Path | None = None,
    ) -> str:
        """Obtain an access token using Epic's backend services JWT flow.

        Args:
            client_id: Epic App Orchard client_id (non-production or production).
            private_key: PEM-encoded RSA private key as a string/bytes.
            private_key_path: Path to a PEM file (used if private_key is None).

        Returns:
            The access token string.
        """
        if private_key is None:
            if private_key_path is None:
                raise ValueError("Provide private_key or private_key_path")
            private_key = Path(private_key_path).read_bytes()

        now = int(time.time())
        claims = {
            "iss": client_id,
            "sub": client_id,
            "aud": self._token_url,
            "jti": str(uuid.uuid4()),
            "iat": now,
            "exp": now + 300,  # 5-minute expiry per Epic spec
        }
        signed_jwt = jwt.encode(claims, private_key, algorithm="RS384")

        response = self._session.post(
            self._token_url,
            data={
                "grant_type": "client_credentials",
                "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
                "client_assertion": signed_jwt,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response.raise_for_status()
        self._access_token = response.json()["access_token"]
        return self._access_token
