"""Unit tests for use case modules (telehealth, contact_center)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from pathlib import Path

import pytest

from ehr_integration.transcription.models import ClinicalTranscriptionResult, Utterance
from ehr_integration.use_cases.telehealth import TelehealthPipeline, SPEAKER_PROVIDER, SPEAKER_PATIENT
from ehr_integration.use_cases.contact_center import ContactCenterPipeline
from tests.conftest import make_deepgram_mock_response


UTTERANCES_MIXED = [
    Utterance(speaker=0, transcript="How long have you had this cough?", start=0.0, end=3.0, confidence=0.99),
    Utterance(speaker=1, transcript="About two weeks now.", start=3.5, end=5.0, confidence=0.97),
    Utterance(speaker=0, transcript="Any fever or chills?", start=5.5, end=7.2, confidence=0.98),
    Utterance(speaker=1, transcript="Yes, fever of 38.5 celsius.", start=7.8, end=10.1, confidence=0.96),
]


class TestTelehealthPipeline:
    @pytest.fixture
    def result(self) -> ClinicalTranscriptionResult:
        return ClinicalTranscriptionResult(
            utterances=UTTERANCES_MIXED,
            full_transcript=" ".join(u.transcript for u in UTTERANCES_MIXED),
        )

    def test_separate_speakers_provider(self, result: ClinicalTranscriptionResult) -> None:
        separated = TelehealthPipeline.separate_speakers(result)
        provider_utts = separated["provider"]
        assert len(provider_utts) == 2
        assert all(u.speaker == SPEAKER_PROVIDER for u in provider_utts)

    def test_separate_speakers_patient(self, result: ClinicalTranscriptionResult) -> None:
        separated = TelehealthPipeline.separate_speakers(result)
        patient_utts = separated["patient"]
        assert len(patient_utts) == 2
        assert all(u.speaker == SPEAKER_PATIENT for u in patient_utts)

    def test_separate_speakers_empty(self) -> None:
        empty = ClinicalTranscriptionResult()
        separated = TelehealthPipeline.separate_speakers(empty)
        assert separated["provider"] == []
        assert separated["patient"] == []

    def test_to_fhir_consult_note_loinc(self, result: ClinicalTranscriptionResult) -> None:
        doc = TelehealthPipeline.to_fhir(result, "patient-tv-001", "encounter-tv-001")
        coding = doc["type"]["coding"][0]
        assert coding["code"] == "11488-4"  # consult note

    def test_to_fhir_correct_patient_ref(self, result: ClinicalTranscriptionResult) -> None:
        doc = TelehealthPipeline.to_fhir(result, "patient-tv-001", "encounter-tv-001")
        assert doc["subject"]["reference"] == "Patient/patient-tv-001"

    def test_to_fhir_telehealth_title(self, result: ClinicalTranscriptionResult) -> None:
        doc = TelehealthPipeline.to_fhir(result, "p", "e")
        assert "Telehealth" in doc["content"][0]["attachment"]["title"]


class TestContactCenterPipeline:
    @pytest.fixture
    def result(self) -> ClinicalTranscriptionResult:
        utts = [
            Utterance(speaker=0, transcript="Nurse triage line, how can I help?", start=0.0, end=2.5, confidence=0.99),
            Utterance(speaker=1, transcript="I have severe abdominal pain.", start=3.0, end=5.5, confidence=0.97),
        ]
        return ClinicalTranscriptionResult(
            utterances=utts,
            full_transcript=" ".join(u.transcript for u in utts),
        )

    def test_to_fhir_progress_note(self, result: ClinicalTranscriptionResult) -> None:
        doc = ContactCenterPipeline.to_fhir(result, "p-cc-001", "e-cc-001")
        assert doc["resourceType"] == "DocumentReference"
        coding = doc["type"]["coding"][0]
        assert coding["code"] == "11506-3"  # progress note

    def test_to_fhir_triage_title(self, result: ClinicalTranscriptionResult) -> None:
        doc = ContactCenterPipeline.to_fhir(result, "p", "e")
        assert "Triage" in doc["content"][0]["attachment"]["title"]

    def test_to_hl7_oru(self, result: ClinicalTranscriptionResult) -> None:
        import hl7
        msg = ContactCenterPipeline.to_hl7_oru(
            result,
            patient_id="CC-MRN-001",
            order_id="ORD-CC-001",
            provider_npi="1122334455",
        )
        assert "ORU^R01" in msg
        parsed = hl7.parse(msg)
        assert parsed is not None
        assert "abdominal pain" in msg


class TestBatchTranscriberURL:
    """Cover transcribe_url and format_utterances with real utterances."""

    def test_transcribe_url(self) -> None:
        from ehr_integration.transcription.batch import BatchTranscriber
        sample = [Utterance(speaker=0, transcript="Hello from URL.", start=0.0, end=1.5, confidence=0.99)]
        mock_response = make_deepgram_mock_response(sample, "Hello from URL.")

        with patch("ehr_integration.transcription.batch.DeepgramClient") as mock_cls:
            mock_cls.return_value.listen.rest.v.return_value.transcribe_url.return_value = mock_response
            transcriber = BatchTranscriber(api_key="test-key")
            result = transcriber.transcribe_url("https://example.com/audio.wav")

        assert result.utterances[0].transcript == "Hello from URL."

    def test_format_utterances_with_content(self) -> None:
        from ehr_integration.transcription.batch import BatchTranscriber
        result = ClinicalTranscriptionResult(
            utterances=[
                Utterance(speaker=0, transcript="Hello.", start=0.0, end=1.0, confidence=0.99),
                Utterance(speaker=1, transcript="World.", start=1.5, end=2.5, confidence=0.97),
            ],
            full_transcript="Hello. World.",
        )
        formatted = BatchTranscriber.format_utterances(result)
        assert "Speaker 0" in formatted
        assert "Speaker 1" in formatted
        assert "Hello." in formatted


class TestStreamingTranscriptHandler:
    """Cover the on_message handler path in streaming.py."""

    def test_on_transcript_callback_invoked(self) -> None:
        from ehr_integration.transcription.streaming import StreamingTranscriber
        from deepgram import LiveTranscriptionEvents

        received: list[tuple] = []
        mock_conn = MagicMock()
        mock_conn.start.return_value = True
        captured: dict = {}

        def capture_on(event, handler):
            captured[str(event)] = handler

        mock_conn.on.side_effect = capture_on

        with patch("ehr_integration.transcription.streaming.DeepgramClient") as mock_cls:
            mock_cls.return_value.listen.websocket.v.return_value = mock_conn
            transcriber = StreamingTranscriber(api_key="test-key")
            transcriber.start(lambda text, speaker, start, end: received.append((text, speaker, start, end)))

        # Simulate a transcript result event
        mock_result = MagicMock()
        mock_result.channel.alternatives[0].transcript = "Patient has fever."
        mock_word = MagicMock()
        mock_word.start = 0.5
        mock_word.end = 2.0
        mock_word.speaker = 1
        mock_result.channel.alternatives[0].words = [mock_word]

        transcript_handler = captured[str(LiveTranscriptionEvents.Transcript)]
        transcript_handler(None, mock_result)

        assert len(received) == 1
        assert received[0][0] == "Patient has fever."
        assert received[0][1] == 1  # speaker

        transcriber.finish()

    def test_on_transcript_empty_text_not_fired(self) -> None:
        from ehr_integration.transcription.streaming import StreamingTranscriber
        from deepgram import LiveTranscriptionEvents

        received: list = []
        mock_conn = MagicMock()
        mock_conn.start.return_value = True
        captured: dict = {}

        def capture_on(event, handler):
            captured[str(event)] = handler

        mock_conn.on.side_effect = capture_on

        with patch("ehr_integration.transcription.streaming.DeepgramClient") as mock_cls:
            mock_cls.return_value.listen.websocket.v.return_value = mock_conn
            transcriber = StreamingTranscriber(api_key="test-key")
            transcriber.start(lambda *a: received.append(a))

        mock_result = MagicMock()
        mock_result.channel.alternatives[0].transcript = ""  # empty
        mock_result.channel.alternatives[0].words = []

        transcript_handler = captured[str(LiveTranscriptionEvents.Transcript)]
        transcript_handler(None, mock_result)

        assert len(received) == 0  # empty transcript must not fire callback
        transcriber.finish()

    def test_default_error_handler_writes_stderr(self, capsys) -> None:
        from ehr_integration.transcription.streaming import StreamingTranscriber
        from deepgram import LiveTranscriptionEvents

        mock_conn = MagicMock()
        mock_conn.start.return_value = True
        captured: dict = {}

        def capture_on(event, handler):
            captured[str(event)] = handler

        mock_conn.on.side_effect = capture_on

        with patch("ehr_integration.transcription.streaming.DeepgramClient") as mock_cls:
            mock_cls.return_value.listen.websocket.v.return_value = mock_conn
            transcriber = StreamingTranscriber(api_key="test-key")
            transcriber.start(lambda *a: None, on_error=None)  # no custom error handler

        error_handler = captured[str(LiveTranscriptionEvents.Error)]
        error_handler(None, "network error")

        captured_err = capsys.readouterr()
        assert "network error" in captured_err.err

        transcriber.finish()

    def test_close_handler_invoked(self) -> None:
        from ehr_integration.transcription.streaming import StreamingTranscriber
        from deepgram import LiveTranscriptionEvents

        closed: list = []
        mock_conn = MagicMock()
        mock_conn.start.return_value = True
        captured: dict = {}

        def capture_on(event, handler):
            captured[str(event)] = handler

        mock_conn.on.side_effect = capture_on

        with patch("ehr_integration.transcription.streaming.DeepgramClient") as mock_cls:
            mock_cls.return_value.listen.websocket.v.return_value = mock_conn
            transcriber = StreamingTranscriber(api_key="test-key")
            transcriber.start(lambda *a: None, on_close=lambda: closed.append(True))

        close_handler = captured[str(LiveTranscriptionEvents.Close)]
        close_handler(None)
        assert len(closed) == 1

        transcriber.finish()
