"""Skip guards for live tests.

Every live test that requires external credentials is guarded by a pytest.mark.skipif
that checks for the required environment variable. Tests silently skip when
credentials are absent — they never fail due to missing config.

Required environment variables:
  DEEPGRAM_API_KEY         Real Deepgram API key
  EPIC_CLIENT_ID           Epic App Orchard client ID
  EPIC_PRIVATE_KEY_PATH    Path to RSA private key PEM for Epic
  CERNER_CLIENT_ID         Cerner client ID
  CERNER_CLIENT_SECRET     Cerner client secret
  CERNER_TOKEN_URL         Cerner token endpoint

Set them in your shell before running:
  export DEEPGRAM_API_KEY=your_key_here
  pytest tests/live -v -m live
"""

from __future__ import annotations

import os
import pytest


def _skip_unless(env_var: str, reason: str | None = None):
    """Return a pytest.mark.skipif that skips when env_var is not set."""
    msg = reason or f"Set {env_var} to run this test"
    return pytest.mark.skipif(not os.environ.get(env_var), reason=msg)


# Convenience marks — import these in live test files
skip_no_deepgram  = _skip_unless("DEEPGRAM_API_KEY",  "Set DEEPGRAM_API_KEY to run live Deepgram tests")
skip_no_epic      = _skip_unless("EPIC_CLIENT_ID",    "Set EPIC_CLIENT_ID + EPIC_PRIVATE_KEY_PATH to run Epic sandbox tests")
skip_no_cerner    = _skip_unless("CERNER_CLIENT_ID",  "Set CERNER_CLIENT_ID + CERNER_CLIENT_SECRET to run Cerner sandbox tests")
skip_no_hapi      = pytest.mark.skipif(False, reason="HAPI FHIR public server — always available")  # no key needed


@pytest.fixture(scope="session")
def deepgram_api_key() -> str:
    key = os.environ.get("DEEPGRAM_API_KEY", "")
    if not key:
        pytest.skip("DEEPGRAM_API_KEY not set")
    return key


@pytest.fixture(scope="session")
def epic_credentials() -> dict:
    client_id = os.environ.get("EPIC_CLIENT_ID", "")
    key_path  = os.environ.get("EPIC_PRIVATE_KEY_PATH", "")
    if not client_id or not key_path:
        pytest.skip("EPIC_CLIENT_ID and EPIC_PRIVATE_KEY_PATH not set")
    return {"client_id": client_id, "private_key_path": key_path}


@pytest.fixture(scope="session")
def cerner_credentials() -> dict:
    client_id     = os.environ.get("CERNER_CLIENT_ID", "")
    client_secret = os.environ.get("CERNER_CLIENT_SECRET", "")
    token_url     = os.environ.get("CERNER_TOKEN_URL", "")
    if not all([client_id, client_secret, token_url]):
        pytest.skip("CERNER_CLIENT_ID, CERNER_CLIENT_SECRET, CERNER_TOKEN_URL not set")
    return {
        "client_id":     client_id,
        "client_secret": client_secret,
        "token_url":     token_url,
    }
