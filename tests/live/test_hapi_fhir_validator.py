"""Live FHIR R4 validation against the public HAPI FHIR server.

The HAPI FHIR R4 server at https://hapi.fhir.org/baseR4 is a publicly
available reference server. POSTing to its $validate operation returns a
FHIR OperationOutcome with real schema errors. No API key required.

This is the gold standard for FHIR R4 conformance testing short of running
Epic or Cerner sandboxes.

What is validated:
  - Our DocumentReference passes the HAPI FHIR R4 $validate operation
  - The OperationOutcome contains no errors (warnings are acceptable)
  - All four LOINC document types pass R4 validation

Run:
  pytest tests/live/test_hapi_fhir_validator.py -v -m live
  (No credentials needed — HAPI is a public server)
"""

from __future__ import annotations

import pytest
import requests

from ehr_integration.transcription.models import Utterance
from ehr_integration.fhir.document_reference import DocumentReferenceBuilder

pytestmark = pytest.mark.live

HAPI_R4_BASE = "https://hapi.fhir.org/baseR4"
VALIDATE_URL = f"{HAPI_R4_BASE}/DocumentReference/$validate"
TIMEOUT_S    = 30

SAMPLE_UTTERANCES = [
    Utterance(speaker=0, transcript="Assessment: patient is stable.", start=0.0, end=3.0, confidence=0.99),
    Utterance(speaker=1, transcript="I feel much better.", start=3.5, end=5.0, confidence=0.97),
]


def _post_validate(doc_ref: dict) -> requests.Response:
    return requests.post(
        VALIDATE_URL,
        json=doc_ref,
        headers={"Content-Type": "application/fhir+json", "Accept": "application/fhir+json"},
        timeout=TIMEOUT_S,
    )


def _has_errors(operation_outcome: dict) -> list[str]:
    """Return list of error messages from a FHIR OperationOutcome, empty if none.

    Reference-resolution failures are excluded: the $validate operation checks
    structural conformance, not whether referenced resources exist on this server.
    Test IDs such as Patient/patient-hapi-001 are intentionally synthetic and will
    never resolve against the public HAPI server.
    """
    errors = []
    for issue in operation_outcome.get("issue", []):
        severity = issue.get("severity", "")
        if severity in ("error", "fatal"):
            diagnostics = issue.get("diagnostics", issue.get("details", {}).get("text", str(issue)))
            if isinstance(diagnostics, str) and diagnostics.startswith(
                "Unable to resolve resource with reference "
            ):
                continue
            errors.append(diagnostics)
    return errors


class TestHAPIFHIRR4Validation:

    def test_progress_note_passes_hapi_validation(self) -> None:
        doc = DocumentReferenceBuilder.from_transcript(
            SAMPLE_UTTERANCES, "patient-hapi-001", "encounter-hapi-001",
            doc_type_code="progress_note",
        )
        response = _post_validate(doc)
        assert response.status_code in (200, 201), (
            f"HAPI $validate returned unexpected status {response.status_code}"
        )
        outcome = response.json()
        errors = _has_errors(outcome)
        assert not errors, f"FHIR R4 validation errors:\n" + "\n".join(errors)

    @pytest.mark.parametrize("doc_type", [
        "progress_note",
        "consult_note",
        "discharge_summary",
        "ambient",
    ])
    def test_all_doc_types_pass_hapi_r4_validation(self, doc_type: str) -> None:
        doc = DocumentReferenceBuilder.from_transcript(
            SAMPLE_UTTERANCES,
            patient_id=f"patient-{doc_type}",
            encounter_id=f"encounter-{doc_type}",
            doc_type_code=doc_type,
        )
        response = _post_validate(doc)
        assert response.status_code in (200, 201)
        errors = _has_errors(response.json())
        assert not errors, (
            f"doc_type={doc_type!r} failed HAPI R4 validation:\n" + "\n".join(errors)
        )

    def test_deliberately_invalid_doc_is_rejected_by_hapi(self) -> None:
        """Confirm HAPI actually rejects invalid resources (sanity check on the validator)."""
        bad_doc = {
            "resourceType": "DocumentReference",
            "status": "TOTALLY_INVALID_STATUS",
            "content": [{"attachment": {"contentType": "text/plain"}}],
        }
        response = _post_validate(bad_doc)
        # HAPI should return 200 with an OperationOutcome containing errors,
        # or a 4xx directly
        if response.status_code == 200:
            errors = _has_errors(response.json())
            assert errors, "HAPI must reject a DocumentReference with an invalid status code"

    def test_hapi_server_is_reachable(self) -> None:
        """Smoke test: HAPI R4 base URL responds."""
        response = requests.get(
            f"{HAPI_R4_BASE}/metadata",
            headers={"Accept": "application/fhir+json"},
            timeout=TIMEOUT_S,
        )
        assert response.status_code == 200
        assert response.json().get("resourceType") == "CapabilityStatement"
