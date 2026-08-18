"""Tests for the explicit VerifierStatus outcome mapping.

The critical invariant: an unavailable / unsupported / errored verifier is
NEVER reported as NOT_DETECTED (i.e. never masquerades as a clean pass).
"""

from __future__ import annotations

import pytest

from ghostmark.models import (
    ExternalVerifierOutcome,
    VerifierStatus,
    _derive_verifier_status,
)


def _outcome(*, available, applicable, passed) -> ExternalVerifierOutcome:
    return ExternalVerifierOutcome(
        name="exiftool", label="ExifTool", available=available, applicable=applicable, passed=passed
    )


@pytest.mark.parametrize(
    "available,applicable,passed,expected",
    [
        (False, True, None, VerifierStatus.UNAVAILABLE),
        (False, False, None, VerifierStatus.UNAVAILABLE),
        (True, False, None, VerifierStatus.UNSUPPORTED),
        (True, True, None, VerifierStatus.ERROR),
        (True, True, True, VerifierStatus.NOT_DETECTED),
        (True, True, False, VerifierStatus.DETECTED),
    ],
)
def test_status_mapping(available, applicable, passed, expected):
    assert _derive_verifier_status(available, applicable, passed) is expected
    assert _outcome(available=available, applicable=applicable, passed=passed).status is expected


def test_unavailable_never_reads_as_not_detected():
    o = _outcome(available=False, applicable=True, passed=None)
    assert o.status is not VerifierStatus.NOT_DETECTED
    assert o.status is VerifierStatus.UNAVAILABLE


def test_errored_never_reads_as_not_detected():
    # available + applicable but no result (timeout/crash) -> ERROR, not a pass
    o = _outcome(available=True, applicable=True, passed=None)
    assert o.status is VerifierStatus.ERROR
    assert o.status is not VerifierStatus.NOT_DETECTED


def test_to_dict_carries_explicit_status_and_locality():
    o = _outcome(available=True, applicable=True, passed=True)
    d = o.to_dict()
    assert d["status"] == "not_detected"
    assert d["is_remote"] is False
    assert "passed" in d and d["passed"] is True
