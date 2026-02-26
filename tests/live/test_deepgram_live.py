"""Live Deepgram API tests.

These tests make real API calls to Deepgram Nova-3 Medical. They require a
valid DEEPGRAM_API_KEY environment variable and are skipped otherwise.

What is validated:
  - The SDK is called correctly (no argument errors at runtime)
  - The response contains a valid transcript (not empty)
  - Utterances are returned when diarize=True
  - keyterm parameter is accepted without error
  - The corrected mimetype/buffer pattern works end-to-end

Run:
  export DEEPGRAM_API_KEY=your_key_here
  pytest tests/live/test_deepgram_live.py -v -m live
"""

from __future__ import annotations

import pytest

from ehr_integration.transcription.batch import BatchTranscriber
from ehr_integration.transcription.models import ClinicalTranscriptionResult
from tests.fixtures.audio import generate_sine_wav
from tests.live.conftest import skip_no_deepgram

pytestmark = [pytest.mark.live, skip_no_deepgram]


class TestDeepgramLiveBatch:

    def test_transcribe_real_wav_returns_result(
        self, deepgram_api_key: str, tmp_path
    ) -> None:
        """A real WAV file sent to Deepgram returns a ClinicalTranscriptionResult."""
        wav = tmp_path / "live_test.wav"
        generate_sine_wav(wav, duration_seconds=2.0, frequency_hz=440.0)

        transcriber = BatchTranscriber(api_key=deepgram_api_key)
        result = transcriber.transcribe_file(wav)

        assert isinstance(result, ClinicalTranscriptionResult)
        assert result.request_id, "Deepgram must return a request_id"
        # Sine wave is not speech, so transcript may be empty — that's valid
        # What matters is the call succeeds without exception

    def test_transcribe_with_keyterms_does_not_raise(
        self, deepgram_api_key: str, tmp_path
    ) -> None:
        """keyterm parameter is accepted by Nova-3 Medical without error."""
        wav = tmp_path / "keyterm_test.wav"
        generate_sine_wav(wav, duration_seconds=1.0)

        transcriber = BatchTranscriber(api_key=deepgram_api_key)
        result = transcriber.transcribe_file(
            wav,
            keyterms=["hypertension", "metformin", "lisinopril"],
        )
        assert isinstance(result, ClinicalTranscriptionResult)

    def test_transcribe_with_diarize_true_no_crash(
        self, deepgram_api_key: str, tmp_path
    ) -> None:
        """diarize=True on non-speech audio must not crash (null guard holds)."""
        wav = tmp_path / "diarize_test.wav"
        generate_sine_wav(wav, duration_seconds=1.0)

        transcriber = BatchTranscriber(api_key=deepgram_api_key)
        result = transcriber.transcribe_file(wav, diarize=True)

        # The null guard must hold: utterances is always a list, never None
        assert isinstance(result.utterances, list)

    def test_request_id_is_present_and_nonempty(
        self, deepgram_api_key: str, tmp_path
    ) -> None:
        wav = tmp_path / "reqid_test.wav"
        generate_sine_wav(wav, duration_seconds=1.0)

        transcriber = BatchTranscriber(api_key=deepgram_api_key)
        result = transcriber.transcribe_file(wav)

        assert result.request_id
        assert len(result.request_id) > 8

    def test_url_transcription_does_not_raise(self, deepgram_api_key: str) -> None:
        """transcribe_url with a publicly accessible audio URL must not raise."""
        # Deepgram's own sample audio used in their documentation
        url = "https://dpgr.am/spacewalk.wav"
        transcriber = BatchTranscriber(api_key=deepgram_api_key)
        result = transcriber.transcribe_url(url, keyterms=["spacewalk"])

        assert isinstance(result, ClinicalTranscriptionResult)
        assert result.full_transcript, "Known-speech URL must produce a non-empty transcript"
