"""Pydantic models for clinical transcription results."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Utterance(BaseModel):
    """A single speaker utterance from diarized transcription."""

    speaker: int = Field(..., description="Speaker index (0-based)")
    transcript: str = Field(..., description="Transcribed text for this utterance")
    start: float = Field(..., description="Start time in seconds")
    end: float = Field(..., description="End time in seconds")
    confidence: float = Field(default=0.0, description="Confidence score 0-1")


class ClinicalTranscriptionResult(BaseModel):
    """Structured result from a Deepgram Nova-3 Medical transcription."""

    utterances: list[Utterance] = Field(default_factory=list)
    full_transcript: str = Field(default="", description="Full concatenated transcript")
    request_id: str = Field(default="", description="Deepgram request ID")
    model: str = Field(default="nova-3-medical")
    detected_language: str = Field(default="en-US")
    keyterms_detected: list[str] = Field(default_factory=list)

    @classmethod
    def from_deepgram_response(cls, response: object) -> "ClinicalTranscriptionResult":
        """Parse a Deepgram PreRecordedResponse into a ClinicalTranscriptionResult."""
        results = getattr(response, "results", None)
        if results is None:
            return cls()

        # Extract full transcript from first channel/alternative
        full_transcript = ""
        channels = getattr(results, "channels", None) or []
        if channels:
            alternatives = getattr(channels[0], "alternatives", None) or []
            if alternatives:
                full_transcript = getattr(alternatives[0], "transcript", "") or ""

        # Extract utterances (requires diarize=True)
        raw_utterances = getattr(results, "utterances", None) or []
        utterances = []
        for u in raw_utterances:
            utterances.append(
                Utterance(
                    speaker=getattr(u, "speaker", 0),
                    transcript=getattr(u, "transcript", ""),
                    start=getattr(u, "start", 0.0),
                    end=getattr(u, "end", 0.0),
                    confidence=getattr(u, "confidence", 0.0),
                )
            )

        # Extract metadata
        metadata = getattr(response, "metadata", None)
        request_id = getattr(metadata, "request_id", "") if metadata else ""
        model_info = getattr(metadata, "model_info", None) if metadata else None
        model_name = "nova-3-medical"
        if model_info and isinstance(model_info, dict):
            model_name = next(iter(model_info.values()), {}).get("name", "nova-3-medical")  # type: ignore[union-attr]

        return cls(
            utterances=utterances,
            full_transcript=full_transcript,
            request_id=request_id,
            model=model_name,
        )
