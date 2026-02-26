"""Unit tests for WebSocket streaming transcription (Errors 4-7 corrections)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch, call

import pytest

from ehr_integration.transcription.streaming import StreamingTranscriber
from deepgram import LiveTranscriptionEvents


class TestStreamingImport:
    """Error 4: Verify correct import style."""

    def test_imports_live_transcription_events_directly(self) -> None:
        import ehr_integration.transcription.streaming as mod
        assert hasattr(mod, "LiveTranscriptionEvents")
        assert hasattr(mod, "LiveOptions")
        assert hasattr(mod, "DeepgramClient")


class TestConnectionFinish:
    """Error 5: connection.finish() must be called when done sending audio."""

    def _make_connected_transcriber(self) -> tuple[StreamingTranscriber, MagicMock]:
        mock_conn = MagicMock()
        mock_conn.start.return_value = True
        with patch("ehr_integration.transcription.streaming.DeepgramClient") as mock_cls:
            mock_cls.return_value.listen.websocket.v.return_value = mock_conn
            transcriber = StreamingTranscriber(api_key="test-key")
            transcriber.start(lambda *a: None)
        return transcriber, mock_conn

    def test_finish_calls_connection_finish(self) -> None:
        transcriber, mock_conn = self._make_connected_transcriber()
        transcriber.finish()
        mock_conn.finish.assert_called_once()

    def test_is_disconnected_after_finish(self) -> None:
        transcriber, mock_conn = self._make_connected_transcriber()
        assert transcriber.is_connected
        transcriber.finish()
        assert not transcriber.is_connected

    def test_finish_safe_to_call_twice(self) -> None:
        transcriber, mock_conn = self._make_connected_transcriber()
        transcriber.finish()
        transcriber.finish()  # Second call must not raise
        mock_conn.finish.assert_called_once()


class TestConnectionStartCheck:
    """Error 6: connection.start() must be checked; failure must raise RuntimeError."""

    def test_start_failure_raises_runtime_error(self) -> None:
        mock_conn = MagicMock()
        mock_conn.start.return_value = False  # Simulate Deepgram connection failure

        with patch("ehr_integration.transcription.streaming.DeepgramClient") as mock_cls:
            mock_cls.return_value.listen.websocket.v.return_value = mock_conn
            transcriber = StreamingTranscriber(api_key="test-key")
            with pytest.raises(RuntimeError, match="Failed to connect"):
                transcriber.start(lambda *a: None)

    def test_start_success_does_not_raise(self) -> None:
        mock_conn = MagicMock()
        mock_conn.start.return_value = True

        with patch("ehr_integration.transcription.streaming.DeepgramClient") as mock_cls:
            mock_cls.return_value.listen.websocket.v.return_value = mock_conn
            transcriber = StreamingTranscriber(api_key="test-key")
            transcriber.start(lambda *a: None)  # Must not raise
            transcriber.finish()


class TestEventHandlers:
    """Error 7: Error and Close event handlers must be wired."""

    def _get_registered_events(self, mock_conn: MagicMock) -> list[str]:
        return [str(c[0][0]) for c in mock_conn.on.call_args_list]

    def test_error_handler_wired(self) -> None:
        mock_conn = MagicMock()
        mock_conn.start.return_value = True

        with patch("ehr_integration.transcription.streaming.DeepgramClient") as mock_cls:
            mock_cls.return_value.listen.websocket.v.return_value = mock_conn
            transcriber = StreamingTranscriber(api_key="test-key")
            transcriber.start(lambda *a: None)
            transcriber.finish()

        events = self._get_registered_events(mock_conn)
        assert str(LiveTranscriptionEvents.Error) in events

    def test_close_handler_wired(self) -> None:
        mock_conn = MagicMock()
        mock_conn.start.return_value = True

        with patch("ehr_integration.transcription.streaming.DeepgramClient") as mock_cls:
            mock_cls.return_value.listen.websocket.v.return_value = mock_conn
            transcriber = StreamingTranscriber(api_key="test-key")
            transcriber.start(lambda *a: None)
            transcriber.finish()

        events = self._get_registered_events(mock_conn)
        assert str(LiveTranscriptionEvents.Close) in events

    def test_transcript_handler_wired(self) -> None:
        mock_conn = MagicMock()
        mock_conn.start.return_value = True

        with patch("ehr_integration.transcription.streaming.DeepgramClient") as mock_cls:
            mock_cls.return_value.listen.websocket.v.return_value = mock_conn
            transcriber = StreamingTranscriber(api_key="test-key")
            transcriber.start(lambda *a: None)
            transcriber.finish()

        events = self._get_registered_events(mock_conn)
        assert str(LiveTranscriptionEvents.Transcript) in events

    def test_custom_error_handler_called(self) -> None:
        mock_conn = MagicMock()
        mock_conn.start.return_value = True
        errors_received: list[Exception] = []

        with patch("ehr_integration.transcription.streaming.DeepgramClient") as mock_cls:
            mock_cls.return_value.listen.websocket.v.return_value = mock_conn
            transcriber = StreamingTranscriber(api_key="test-key")
            transcriber.start(lambda *a: None, on_error=errors_received.append)

        # Find the error handler registered with .on()
        error_handler = None
        for c in mock_conn.on.call_args_list:
            if str(c[0][0]) == str(LiveTranscriptionEvents.Error):
                error_handler = c[0][1]
                break

        assert error_handler is not None
        error_handler(None, "connection refused")
        assert len(errors_received) == 1


class TestSendAudio:
    def test_send_audio_calls_connection_send(self) -> None:
        mock_conn = MagicMock()
        mock_conn.start.return_value = True

        with patch("ehr_integration.transcription.streaming.DeepgramClient") as mock_cls:
            mock_cls.return_value.listen.websocket.v.return_value = mock_conn
            transcriber = StreamingTranscriber(api_key="test-key")
            transcriber.start(lambda *a: None)
            transcriber.send_audio(b"\x00" * 512)
            transcriber.finish()

        mock_conn.send.assert_called_once_with(b"\x00" * 512)

    def test_send_audio_before_start_raises(self) -> None:
        transcriber = StreamingTranscriber(api_key="test-key")
        with pytest.raises(RuntimeError, match="Call start\\(\\)"):
            transcriber.send_audio(b"\x00" * 100)
