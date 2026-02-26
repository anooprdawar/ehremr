"""Property-based tests using Hypothesis.

Property-based testing generates hundreds of random inputs and verifies that
invariants hold for all of them. This catches edge cases that hand-written
example tests miss: empty strings, unicode, very long inputs, special characters.

These tests do NOT mock anything — they test pure functions directly.
"""

from __future__ import annotations

import string
import pytest
import hl7
from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

from ehr_integration.transcription.models import Utterance, ClinicalTranscriptionResult
from ehr_integration.fhir.document_reference import (
    DocumentReferenceBuilder,
    FHIRValidationError,
)
from ehr_integration.hl7.mdm_builder import MDMBuilder
from ehr_integration.hl7.oru_builder import ORUBuilder
from ehr_integration.transcription.batch import _mimetype_for
from pathlib import Path

pytestmark = pytest.mark.quality

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Safe ID characters: alphanumeric + hyphens, at least 1 char
safe_id = st.text(
    alphabet=string.ascii_letters + string.digits + "-",
    min_size=1,
    max_size=40,
)

# FHIR resource types
resource_types = st.sampled_from(["Patient", "Encounter", "Practitioner", "Organization"])

# Speaker index 0 or 1
speaker_index = st.integers(min_value=0, max_value=1)

# Timestamps
start_time = st.floats(min_value=0.0, max_value=3600.0, allow_nan=False, allow_infinity=False)

# Non-empty clinical text (printable ASCII, arbitrary length)
clinical_text = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "Zs")),
    min_size=1,
    max_size=500,
)

# Utterance strategy
utterance_st = st.builds(
    Utterance,
    speaker=speaker_index,
    transcript=clinical_text,
    start=start_time,
    end=start_time.map(lambda s: s + 0.1),
    confidence=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
)

# List of 0–10 utterances
utterances_st = st.lists(utterance_st, min_size=0, max_size=10)

# NPI: 10-digit string
npi_st = st.from_regex(r"[0-9]{10}", fullmatch=True)


# ---------------------------------------------------------------------------
# FHIR builder properties
# ---------------------------------------------------------------------------

class TestFHIRBuilderProperties:

    @given(
        utterances=utterances_st,
        patient_id=safe_id,
        encounter_id=safe_id,
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_from_transcript_never_raises_for_valid_ids(
        self, utterances, patient_id, encounter_id
    ) -> None:
        """For any valid patient/encounter IDs and any utterances, builder must not raise."""
        doc = DocumentReferenceBuilder.from_transcript(utterances, patient_id, encounter_id)
        assert doc["resourceType"] == "DocumentReference"

    @given(
        utterances=utterances_st,
        patient_id=safe_id,
        encounter_id=safe_id,
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_output_always_passes_r4_schema_validation(
        self, utterances, patient_id, encounter_id
    ) -> None:
        """Every resource produced by from_transcript must pass validate_r4_schema."""
        doc = DocumentReferenceBuilder.from_transcript(utterances, patient_id, encounter_id)
        # Must not raise
        DocumentReferenceBuilder.validate_r4_schema(doc)

    @given(
        utterances=utterances_st,
        patient_id=safe_id,
        encounter_id=safe_id,
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_base64_always_roundtrips(
        self, utterances, patient_id, encounter_id
    ) -> None:
        """Encode → decode must recover the original transcript for any input."""
        doc = DocumentReferenceBuilder.from_transcript(utterances, patient_id, encounter_id)
        decoded = DocumentReferenceBuilder.decode_content(doc)
        for u in utterances:
            assert u.transcript in decoded

    @given(
        doc_type=st.sampled_from(["progress_note", "consult_note", "discharge_summary", "ambient"]),
        patient_id=safe_id,
        encounter_id=safe_id,
    )
    @settings(max_examples=50)
    def test_all_doc_types_produce_valid_loinc(
        self, doc_type, patient_id, encounter_id
    ) -> None:
        doc = DocumentReferenceBuilder.from_transcript([], patient_id, encounter_id, doc_type)
        code = doc["type"]["coding"][0]["code"]
        assert code in {"11506-3", "11488-4", "18842-5", "34109-9"}

    @given(patient_id=st.just("") | st.just("   "))
    @settings(max_examples=10)
    def test_empty_patient_id_always_raises(self, patient_id) -> None:
        with pytest.raises(ValueError, match="patient_id"):
            DocumentReferenceBuilder.from_transcript([], patient_id, "enc-001")

    @given(
        utterances=utterances_st,
        patient_id=safe_id,
        encounter_id=safe_id,
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_subject_reference_always_valid_pattern(
        self, utterances, patient_id, encounter_id
    ) -> None:
        doc = DocumentReferenceBuilder.from_transcript(utterances, patient_id, encounter_id)
        ref = doc["subject"]["reference"]
        assert ref.startswith("Patient/")
        assert len(ref) > len("Patient/")


# ---------------------------------------------------------------------------
# HL7 builder properties
# ---------------------------------------------------------------------------

class TestHL7BuilderProperties:

    @given(
        transcript=clinical_text,
        patient_id=safe_id,
        visit_id=safe_id,
        provider_npi=npi_st,
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_mdm_always_parseable(
        self, transcript, patient_id, visit_id, provider_npi
    ) -> None:
        """For any clinical text, MDM^T02 must always produce a parseable HL7 message."""
        msg = MDMBuilder.build_t02(transcript, patient_id, visit_id, provider_npi)
        parsed = hl7.parse(msg)
        assert parsed is not None

    @given(
        transcript=clinical_text,
        patient_id=safe_id,
        visit_id=safe_id,
        provider_npi=npi_st,
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_mdm_always_has_all_required_segments(
        self, transcript, patient_id, visit_id, provider_npi
    ) -> None:
        msg = MDMBuilder.build_t02(transcript, patient_id, visit_id, provider_npi)
        seg_names = {s.split("|")[0] for s in msg.split("\r")}
        for required in ("MSH", "EVN", "PID", "PV1", "TXA", "OBX"):
            assert required in seg_names, f"Required segment {required} missing"

    @given(
        transcript=clinical_text,
        patient_id=safe_id,
        order_id=safe_id,
        provider_npi=npi_st,
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_oru_always_parseable(
        self, transcript, patient_id, order_id, provider_npi
    ) -> None:
        msg = ORUBuilder.build_r01(transcript, patient_id, order_id, provider_npi)
        parsed = hl7.parse(msg)
        assert parsed is not None

    @given(
        before=st.text(min_size=0, max_size=80, alphabet=string.ascii_letters + string.digits + " .,"),
        after=st.text(min_size=0, max_size=80, alphabet=string.ascii_letters + string.digits + " .,"),
    )
    @settings(max_examples=100)
    def test_pipe_in_transcript_never_breaks_parsing(self, before, after) -> None:
        """Any transcript containing '|' must still produce a parseable HL7 message."""
        transcript = f"{before}|{after}"  # guaranteed to contain a pipe
        msg = MDMBuilder.build_t02(transcript, "MRN-001", "V-001", "1234567890")
        parsed = hl7.parse(msg)
        assert parsed is not None


# ---------------------------------------------------------------------------
# Utterance model properties
# ---------------------------------------------------------------------------

class TestUtteranceModelProperties:

    @given(
        speaker=speaker_index,
        transcript=clinical_text,
        start=start_time,
        confidence=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    )
    @settings(max_examples=200)
    def test_utterance_construction_never_raises(
        self, speaker, transcript, start, confidence
    ) -> None:
        end = start + 0.5
        u = Utterance(
            speaker=speaker,
            transcript=transcript,
            start=start,
            end=end,
            confidence=confidence,
        )
        assert u.speaker == speaker
        assert u.transcript == transcript

    @given(utterances=utterances_st)
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_null_guard_holds_for_any_utterance_list(self, utterances) -> None:
        """The null guard (utterances or []) must be safe for any list, including empty."""
        result = ClinicalTranscriptionResult(utterances=utterances, full_transcript="")
        safe = result.utterances or []
        assert isinstance(safe, list)


# ---------------------------------------------------------------------------
# MIME type helper properties
# ---------------------------------------------------------------------------

class TestMimetypeProperties:

    @given(ext=st.sampled_from([".wav", ".mp3", ".flac", ".ogg", ".webm", ".mp4", ".m4a"]))
    @settings(max_examples=50)
    def test_known_extensions_return_audio_mimetype(self, ext) -> None:
        # _mimetype_for only uses path.suffix — no real file needed
        p = Path(f"audio{ext}")
        result = _mimetype_for(p)
        assert result.startswith("audio/")

    @given(ext=st.text(alphabet=string.ascii_lowercase, min_size=1, max_size=6))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.filter_too_much])
    def test_unknown_extension_always_returns_audio_wav(self, ext) -> None:
        known = {".wav", ".mp3", ".flac", ".ogg", ".webm", ".mp4", ".m4a"}
        assume("." + ext not in known)
        p = Path(f"audio.{ext}")
        result = _mimetype_for(p)
        assert result == "audio/wav"
