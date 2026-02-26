"""Example: batch-transcribe an audio file (or run in demo mode with mock data).

Usage:
    # Demo mode — no real API key or audio file needed:
    python examples/batch_transcribe.py

    # Real file:
    DEEPGRAM_API_KEY=<key> python examples/batch_transcribe.py path/to/audio.wav
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Make sure the package is importable when running from the project root
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ehr_integration.transcription.batch import BatchTranscriber
from ehr_integration.transcription.models import ClinicalTranscriptionResult, Utterance


DEMO_UTTERANCES = [
    Utterance(speaker=0, transcript="Good morning, how are you feeling today?", start=0.5, end=3.2, confidence=0.98),
    Utterance(speaker=1, transcript="I've had a persistent headache for the past three days.", start=4.1, end=7.8, confidence=0.97),
    Utterance(speaker=0, transcript="Is the pain localized or does it radiate to your neck?", start=8.2, end=11.5, confidence=0.99),
    Utterance(speaker=1, transcript="It's mostly in the front and sometimes radiates behind my eyes.", start=12.0, end=16.3, confidence=0.96),
]


def run_demo() -> None:
    """Run with mock Deepgram response — no API key required."""
    print("=== Batch Transcription Demo (mock mode) ===\n")

    mock_result = ClinicalTranscriptionResult(
        utterances=DEMO_UTTERANCES,
        full_transcript=" ".join(u.transcript for u in DEMO_UTTERANCES),
        request_id="demo-request-001",
        model="nova-3-medical",
    )

    mock_response = MagicMock()
    mock_response.results.utterances = [
        MagicMock(
            speaker=u.speaker,
            transcript=u.transcript,
            start=u.start,
            end=u.end,
            confidence=u.confidence,
        )
        for u in DEMO_UTTERANCES
    ]
    mock_response.results.channels = [
        MagicMock(alternatives=[MagicMock(transcript=mock_result.full_transcript)])
    ]
    mock_response.metadata = MagicMock(request_id="demo-request-001")

    with patch("ehr_integration.transcription.batch.DeepgramClient") as mock_client:
        mock_client.return_value.listen.rest.v.return_value.transcribe_file.return_value = mock_response

        transcriber = BatchTranscriber(api_key="demo-key")
        # Create a dummy 100-byte wav file
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(b"\x00" * 100)
            tmp_path = f.name

        try:
            result = transcriber.transcribe_file(tmp_path, keyterms=["headache", "migraine"])
        finally:
            os.unlink(tmp_path)

    print("Formatted utterances:")
    print("-" * 50)
    print(BatchTranscriber.format_utterances(result))
    print()
    print("Full transcript:")
    print(result.full_transcript)
    print()
    print("Metadata:")
    print(json.dumps({"request_id": result.request_id, "model": result.model}, indent=2))


def run_real(audio_path: str) -> None:
    """Transcribe a real audio file (requires DEEPGRAM_API_KEY env var)."""
    print(f"=== Transcribing: {audio_path} ===\n")
    transcriber = BatchTranscriber()
    result = transcriber.transcribe_file(audio_path, keyterms=["patient", "diagnosis"])
    print(BatchTranscriber.format_utterances(result))


if __name__ == "__main__":
    if len(sys.argv) > 1:
        run_real(sys.argv[1])
    else:
        run_demo()
