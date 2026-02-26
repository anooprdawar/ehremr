"""Corrected WebSocket streaming transcription using Deepgram Nova-3 Medical.

Errors fixed from the original guide:
  4. Import style: use 'from deepgram import DeepgramClient, LiveOptions, LiveTranscriptionEvents'
  5. Missing connection.finish() — without it Deepgram times out after ~12s silence
  6. connection.start() return not checked — should raise on failure
  7. Missing error/close event handlers for production safety
"""

from __future__ import annotations

import os
import threading
from collections.abc import Callable
from typing import Any

# CORRECT import style (Error 4 fix) — all symbols imported directly
from deepgram import DeepgramClient, LiveOptions, LiveTranscriptionEvents


class StreamingTranscriber:
    """Stream audio to Deepgram Nova-3 Medical via WebSocket."""

    def __init__(self, api_key: str | None = None) -> None:
        key = api_key or os.environ.get("DEEPGRAM_API_KEY", "")
        self._client = DeepgramClient(key)
        self._connection: Any = None
        self._lock = threading.Lock()

    def start(
        self,
        on_transcript: Callable[[str, int, float, float], None],
        on_error: Callable[[Exception], None] | None = None,
        on_close: Callable[[], None] | None = None,
        keyterms: list[str] | None = None,
    ) -> None:
        """Open a WebSocket connection and wire all event handlers.

        Args:
            on_transcript: Called with (text, speaker, start, end) for each final transcript.
            on_error: Called when Deepgram returns an error. Defaults to stderr logging.
            on_close: Called when the WebSocket connection closes.
            keyterms: Nova-3 Medical keyterms for vocabulary boosting.
        """
        options = LiveOptions(
            model="nova-3-medical",
            smart_format=True,
            diarize=True,
            keyterm=keyterms or [],
            interim_results=False,
        )

        connection = self._client.listen.websocket.v("1")

        def _on_message(_self: Any, result: Any, **kwargs: Any) -> None:  # noqa: ANN401
            sentence = result.channel.alternatives[0].transcript
            if not sentence:
                return
            words = result.channel.alternatives[0].words or []
            start = words[0].start if words else 0.0
            end = words[-1].end if words else 0.0
            speaker = words[0].speaker if words else 0
            on_transcript(sentence, speaker, start, end)

        def _on_error(_self: Any, error: Any, **kwargs: Any) -> None:  # noqa: ANN401
            exc = Exception(str(error))
            if on_error:
                on_error(exc)
            else:
                import sys
                print(f"[Deepgram error] {error}", file=sys.stderr)

        def _on_close(_self: Any, **kwargs: Any) -> None:  # noqa: ANN401
            if on_close:
                on_close()

        connection.on(LiveTranscriptionEvents.Transcript, _on_message)
        # CORRECT: wire error and close handlers (Error 7 fix)
        connection.on(LiveTranscriptionEvents.Error, _on_error)
        connection.on(LiveTranscriptionEvents.Close, _on_close)

        # CORRECT: check start() return value (Error 6 fix)
        if not connection.start(options):
            raise RuntimeError("Failed to connect to Deepgram WebSocket")

        with self._lock:
            self._connection = connection

    def send_audio(self, chunk: bytes) -> None:
        """Send a raw audio chunk to the open WebSocket."""
        with self._lock:
            if self._connection is None:
                raise RuntimeError("Call start() before send_audio()")
            self._connection.send(chunk)

    def finish(self) -> None:
        """Gracefully close the WebSocket connection.

        CORRECT: Must call finish() when done sending audio (Error 5 fix).
        Without this, Deepgram times out after ~12 seconds of silence.
        """
        with self._lock:
            conn = self._connection
            self._connection = None

        if conn is not None:
            conn.finish()

    @property
    def is_connected(self) -> bool:
        with self._lock:
            return self._connection is not None
