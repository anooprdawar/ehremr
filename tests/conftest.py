"""Shared pytest fixtures, mock factories, and test markers.

Test tiers
----------
  unit        Fast, fully offline, zero external dependencies.
              Always run. Target: < 1 second total.

  integration Mock external services. Always run. Validates end-to-end
              flow logic without real network calls.

  quality     Deep validation: FHIR schema, HL7 field-level, property-
              based (Hypothesis). Always run offline.

  live        Real API calls. Skipped unless the required environment
              variables are set. See tests/live/conftest.py for guards.

Run specific tiers:
  pytest tests/unit tests/integration tests/quality   # offline only
  pytest tests/live -m live                           # live only
  pytest tests/ -v                                    # everything
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ehr_integration.transcription.models import ClinicalTranscriptionResult, Utterance
from tests.fixtures.audio import generate_sine_wav, generate_silence_wav, validate_wav

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Pytest markers
# ---------------------------------------------------------------------------

def pytest_configure(config):
    config.addinivalue_line("markers", "unit: fast offline unit tests")
    config.addinivalue_line("markers", "integration: mock-based integration tests")
    config.addinivalue_line("markers", "quality: schema, deep-validation, property-based")
    config.addinivalue_line("markers", "live: requires real credentials (skipped by default)")


# ---------------------------------------------------------------------------
# Utterance / transcript fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_utterances() -> list[Utterance]:
    return [
        Utterance(speaker=0, transcript="Good morning, how are you feeling today?", start=0.5, end=3.2, confidence=0.98),
        Utterance(speaker=1, transcript="I've had a persistent headache for the past three days.", start=4.1, end=7.8, confidence=0.97),
        Utterance(speaker=0, transcript="Is the pain localized or does it radiate to your neck?", start=8.2, end=11.5, confidence=0.99),
        Utterance(speaker=1, transcript="It's mostly in the front and sometimes radiates behind my eyes.", start=12.0, end=16.3, confidence=0.96),
    ]


@pytest.fixture
def sample_transcript_result(sample_utterances: list[Utterance]) -> ClinicalTranscriptionResult:
    full = " ".join(u.transcript for u in sample_utterances)
    return ClinicalTranscriptionResult(
        utterances=sample_utterances,
        full_transcript=full,
        request_id="test-request-001",
        model="nova-3-medical",
    )


@pytest.fixture
def sample_transcript_json() -> dict:
    with open(FIXTURES_DIR / "sample_transcript.json") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Deepgram mock response factory
# ---------------------------------------------------------------------------

def make_deepgram_mock_response(utterances: list[Utterance], full_transcript: str = "") -> MagicMock:
    """Build a MagicMock that mimics a Deepgram PreRecordedResponse."""
    mock_response = MagicMock()
    mock_response.metadata.request_id = "mock-request-001"
    mock_response.results.channels = [
        MagicMock(alternatives=[MagicMock(transcript=full_transcript)])
    ]
    mock_response.results.utterances = [
        MagicMock(
            speaker=u.speaker,
            transcript=u.transcript,
            start=u.start,
            end=u.end,
            confidence=u.confidence,
        )
        for u in utterances
    ]
    return mock_response


@pytest.fixture
def deepgram_mock_response(sample_utterances: list[Utterance]) -> MagicMock:
    full = " ".join(u.transcript for u in sample_utterances)
    return make_deepgram_mock_response(sample_utterances, full)


@pytest.fixture
def deepgram_mock_response_no_utterances() -> MagicMock:
    """Simulates diarize=True but Deepgram returns None for utterances."""
    mock_response = MagicMock()
    mock_response.metadata.request_id = "mock-empty-001"
    mock_response.results.channels = [
        MagicMock(alternatives=[MagicMock(transcript="Some speech here.")])
    ]
    mock_response.results.utterances = None
    return mock_response


# ---------------------------------------------------------------------------
# Audio fixtures — real, spec-compliant WAV files
# ---------------------------------------------------------------------------

@pytest.fixture
def real_wav_file(tmp_path: Path) -> Path:
    """A real RIFF/WAV file: mono, 16-bit, 16kHz, 1-second sine wave at 440Hz.

    Unlike b'\\x00' * 100, this file has correct RIFF headers, a valid
    fmt chunk, and a valid data chunk. Any WAV parser can open it.
    """
    path = tmp_path / "test_440hz_1s.wav"
    generate_sine_wav(path, duration_seconds=1.0, frequency_hz=440.0)

    # Self-verify immediately so a bad fixture fails loudly
    props = validate_wav(path)
    assert props["channels"] == 1
    assert props["frame_rate"] == 16000
    assert props["n_frames"] == 16000
    assert path.stat().st_size > 32000  # header + 32000 bytes of PCM data

    return path


@pytest.fixture
def real_silence_wav_file(tmp_path: Path) -> Path:
    """A real RIFF/WAV silence file — valid headers, silent PCM data."""
    path = tmp_path / "test_silence_1s.wav"
    generate_silence_wav(path, duration_seconds=1.0)
    validate_wav(path)
    return path


@pytest.fixture
def dummy_wav_file(tmp_path: Path) -> Path:
    """Kept for backward compatibility with unit tests that mock DeepgramClient.
    Uses a real WAV file instead of null bytes.
    """
    path = tmp_path / "dummy.wav"
    generate_silence_wav(path, duration_seconds=0.1)
    return path


# ---------------------------------------------------------------------------
# FHIR fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fhir_document_ref_fixture() -> dict:
    with open(FIXTURES_DIR / "fhir_document_ref.json") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# EHR client session mocks
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_epic_session() -> MagicMock:
    session = MagicMock()
    token_resp = MagicMock()
    token_resp.json.return_value = {"access_token": "epic-test-token"}
    token_resp.raise_for_status = MagicMock()
    fhir_resp = MagicMock()
    fhir_resp.status_code = 201
    fhir_resp.json.return_value = {"resourceType": "DocumentReference", "id": "dr-001"}
    fhir_resp.raise_for_status = MagicMock()
    session.post.side_effect = [token_resp, fhir_resp]
    return session


@pytest.fixture
def mock_cerner_session() -> MagicMock:
    session = MagicMock()
    token_resp = MagicMock()
    token_resp.json.return_value = {"access_token": "cerner-test-token"}
    token_resp.raise_for_status = MagicMock()
    fhir_resp = MagicMock()
    fhir_resp.status_code = 201
    fhir_resp.json.return_value = {"resourceType": "DocumentReference", "id": "dr-002"}
    fhir_resp.raise_for_status = MagicMock()
    session.post.side_effect = [token_resp, fhir_resp]
    return session
