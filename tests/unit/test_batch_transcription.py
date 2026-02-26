"""Unit tests for batch transcription (Error 1, 2, 3 corrections)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from ehr_integration.transcription.batch import BatchTranscriber, _mimetype_for
from ehr_integration.transcription.models import ClinicalTranscriptionResult, Utterance
from tests.conftest import make_deepgram_mock_response


class TestBatchTranscriberImport:
    """Error 1: Verify correct import style is used (DeepgramClient, PrerecordedOptions)."""

    def test_deepgram_client_imported_directly(self) -> None:
        import ehr_integration.transcription.batch as batch_module
        assert hasattr(batch_module, "DeepgramClient")
        assert hasattr(batch_module, "PrerecordedOptions")

    def test_no_bare_deepgram_module_import(self) -> None:
        """The module must not rely on bare 'import deepgram' style."""
        import ehr_integration.transcription.batch as batch_module
        assert not hasattr(batch_module, "deepgram")


class TestBatchTranscriberMimetypeInSource:
    """Error 2: Verify mimetype is passed in the buffer source dict."""

    def test_transcribe_file_passes_mimetype(
        self,
        dummy_wav_file: Path,
        sample_utterances: list[Utterance],
    ) -> None:
        mock_response = make_deepgram_mock_response(sample_utterances)

        with patch("ehr_integration.transcription.batch.DeepgramClient") as mock_cls:
            mock_rest = mock_cls.return_value.listen.rest.v.return_value
            mock_rest.transcribe_file.return_value = mock_response

            transcriber = BatchTranscriber(api_key="test-key")
            transcriber.transcribe_file(dummy_wav_file)

            call_args = mock_rest.transcribe_file.call_args
            source_dict = call_args[0][0]
            assert "mimetype" in source_dict, "mimetype must be included in source dict"
            assert source_dict["mimetype"] == "audio/wav"
            assert "buffer" in source_dict


class TestNullGuardOnUtterances:
    """Error 3: Verify null guard — diarize=True with no utterances must not crash."""

    def test_empty_utterances_returns_empty_list(
        self,
        dummy_wav_file: Path,
        deepgram_mock_response_no_utterances: MagicMock,
    ) -> None:
        with patch("ehr_integration.transcription.batch.DeepgramClient") as mock_cls:
            mock_rest = mock_cls.return_value.listen.rest.v.return_value
            mock_rest.transcribe_file.return_value = deepgram_mock_response_no_utterances

            transcriber = BatchTranscriber(api_key="test-key")
            result = transcriber.transcribe_file(dummy_wav_file)

        # Must not raise; utterances should be an empty list
        assert result.utterances == []

    def test_format_utterances_with_none_utterances(self) -> None:
        result = ClinicalTranscriptionResult(
            utterances=[],
            full_transcript="Some speech here.",
        )
        formatted = BatchTranscriber.format_utterances(result)
        # Falls back to full_transcript when no utterances
        assert formatted == "Some speech here."


class TestBatchTranscriberClinicalResult:
    """Verify ClinicalTranscriptionResult is correctly populated."""

    def test_utterances_populated(
        self,
        dummy_wav_file: Path,
        sample_utterances: list[Utterance],
    ) -> None:
        mock_response = make_deepgram_mock_response(
            sample_utterances,
            full_transcript="Good morning how are you feeling today",
        )

        with patch("ehr_integration.transcription.batch.DeepgramClient") as mock_cls:
            mock_cls.return_value.listen.rest.v.return_value.transcribe_file.return_value = mock_response
            transcriber = BatchTranscriber(api_key="test-key")
            result = transcriber.transcribe_file(dummy_wav_file)

        assert len(result.utterances) == len(sample_utterances)
        assert result.utterances[0].speaker == 0
        assert "headache" in result.utterances[1].transcript

    def test_keyterms_passed_to_options(
        self,
        dummy_wav_file: Path,
        sample_utterances: list[Utterance],
    ) -> None:
        mock_response = make_deepgram_mock_response(sample_utterances)

        with patch("ehr_integration.transcription.batch.DeepgramClient") as mock_cls:
            with patch("ehr_integration.transcription.batch.PrerecordedOptions") as mock_opts:
                mock_cls.return_value.listen.rest.v.return_value.transcribe_file.return_value = mock_response
                transcriber = BatchTranscriber(api_key="test-key")
                transcriber.transcribe_file(dummy_wav_file, keyterms=["headache", "migraine"])

        mock_opts.assert_called_once()
        kwargs = mock_opts.call_args[1]
        assert kwargs["keyterm"] == ["headache", "migraine"]
        assert kwargs["model"] == "nova-3-medical"


class TestMimetypeHelper:
    @pytest.mark.parametrize("suffix,expected", [
        (".wav", "audio/wav"),
        (".mp3", "audio/mpeg"),
        (".flac", "audio/flac"),
        (".ogg", "audio/ogg"),
        (".webm", "audio/webm"),
        (".xyz", "audio/wav"),  # unknown extension defaults to wav
    ])
    def test_mimetype_for(self, suffix: str, expected: str, tmp_path: Path) -> None:
        p = tmp_path / f"audio{suffix}"
        assert _mimetype_for(p) == expected
