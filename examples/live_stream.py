"""Example: live WebSocket streaming transcription (demo mode).

Usage:
    python examples/live_stream.py
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ehr_integration.transcription.streaming import StreamingTranscriber


def run_demo() -> None:
    """Simulate a streaming session with mock Deepgram WebSocket."""
    print("=== Live Streaming Demo (mock mode) ===\n")

    transcripts: list[str] = []
    errors: list[str] = []

    def on_transcript(text: str, speaker: int, start: float, end: float) -> None:
        line = f"[{start:.1f}s] Speaker {speaker}: {text}"
        transcripts.append(line)
        print(line)

    def on_error(exc: Exception) -> None:
        errors.append(str(exc))
        print(f"[ERROR] {exc}", file=sys.stderr)

    mock_connection = MagicMock()
    mock_connection.start.return_value = True

    # Simulate transcript events being fired after audio is sent
    captured_handlers: dict = {}

    def capture_on(event: object, handler: object) -> None:
        captured_handlers[str(event)] = handler

    mock_connection.on.side_effect = capture_on

    with patch("ehr_integration.transcription.streaming.DeepgramClient") as mock_client:
        mock_client.return_value.listen.websocket.v.return_value = mock_connection

        transcriber = StreamingTranscriber(api_key="demo-key")
        transcriber.start(on_transcript, on_error=on_error)

        # Simulate sending audio chunks
        audio_chunk = b"\x00" * 1024
        print("Sending audio chunks...")
        for i in range(3):
            transcriber.send_audio(audio_chunk)
            time.sleep(0.05)

        # Gracefully close (Error 5 fix: connection.finish() must be called)
        transcriber.finish()

    print("\nVerifying connection.finish() was called:", mock_connection.finish.called)
    print("Total audio chunks sent:", mock_connection.send.call_count)
    print("\nStreaming demo complete.")


if __name__ == "__main__":
    run_demo()
