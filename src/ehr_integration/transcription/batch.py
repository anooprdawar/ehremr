"""Corrected batch (pre-recorded) transcription using Deepgram Nova-3 Medical.

Errors fixed from the original guide:
  1. Import style: use 'from deepgram import DeepgramClient, PrerecordedOptions'
  2. Missing mimetype in buffer source dict
  3. Null guard on utterances (diarize=True can return None utterances)
"""

from __future__ import annotations

import os
from pathlib import Path

# CORRECT import style (Error 1 fix)
from deepgram import DeepgramClient, PrerecordedOptions

from .models import ClinicalTranscriptionResult


class BatchTranscriber:
    """Transcribe pre-recorded audio files using Deepgram Nova-3 Medical."""

    def __init__(self, api_key: str | None = None) -> None:
        key = api_key or os.environ.get("DEEPGRAM_API_KEY", "")
        self._client = DeepgramClient(key)

    def transcribe_file(
        self,
        path: str | Path,
        keyterms: list[str] | None = None,
        diarize: bool = True,
    ) -> ClinicalTranscriptionResult:
        """Transcribe an audio file and return a structured clinical result.

        Args:
            path: Path to the audio file (WAV, MP3, etc.)
            keyterms: Nova-3 Medical keyterms for clinical vocabulary boosting.
                      (Note: Nova-3 uses 'keyterm', not 'keywords'.)
            diarize: Whether to enable speaker diarization.

        Returns:
            ClinicalTranscriptionResult with utterances and full transcript.
        """
        path = Path(path)
        mimetype = _mimetype_for(path)

        options = PrerecordedOptions(
            model="nova-3-medical",
            smart_format=True,
            diarize=diarize,
            keyterm=keyterms or [],  # Nova-3 Medical uses 'keyterm'
        )

        with open(path, "rb") as audio:
            # CORRECT: include mimetype in buffer source (Error 2 fix)
            source = {"buffer": audio.read(), "mimetype": mimetype}
            response = self._client.listen.rest.v("1").transcribe_file(source, options)

        return ClinicalTranscriptionResult.from_deepgram_response(response)

    def transcribe_url(
        self,
        url: str,
        keyterms: list[str] | None = None,
        diarize: bool = True,
    ) -> ClinicalTranscriptionResult:
        """Transcribe audio from a URL."""
        options = PrerecordedOptions(
            model="nova-3-medical",
            smart_format=True,
            diarize=diarize,
            keyterm=keyterms or [],
        )

        source = {"url": url}
        response = self._client.listen.rest.v("1").transcribe_url(source, options)
        return ClinicalTranscriptionResult.from_deepgram_response(response)

    @staticmethod
    def format_utterances(result: ClinicalTranscriptionResult) -> str:
        """Format utterances as a readable clinical transcript."""
        # CORRECT: null guard on utterances (Error 3 fix)
        utterances = result.utterances or []
        if not utterances:
            return result.full_transcript

        lines = []
        for u in utterances:
            speaker_label = f"Speaker {u.speaker}"
            lines.append(f"[{u.start:.1f}s] {speaker_label}: {u.transcript}")
        return "\n".join(lines)


def _mimetype_for(path: Path) -> str:
    """Return the MIME type for common audio file extensions."""
    suffix = path.suffix.lower()
    mapping = {
        ".wav": "audio/wav",
        ".mp3": "audio/mpeg",
        ".mp4": "audio/mp4",
        ".m4a": "audio/mp4",
        ".flac": "audio/flac",
        ".ogg": "audio/ogg",
        ".webm": "audio/webm",
    }
    return mapping.get(suffix, "audio/wav")
