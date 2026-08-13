"""Pure decision-tree tests for VerificationVerdict -- no files, no subprocess.

A VERIFIED CLEAN verdict is the strongest claim GhostMark makes; these
tests exist specifically to make sure it can never be produced except
when every condition genuinely holds.
"""

from __future__ import annotations

from ghostmark.models import ExternalVerifierOutcome, VerificationSummary, VerificationVerdict


def _outcome(name: str, *, available: bool, applicable: bool, passed: bool | None) -> ExternalVerifierOutcome:
    return ExternalVerifierOutcome(name=name, label=name, available=available, applicable=applicable, passed=passed)


def test_not_applicable_when_nothing_found_before():
    summary = VerificationSummary(ghostmark_pass=True, supported_found_before=0, external_verifiers=[])
    assert summary.verdict is VerificationVerdict.NOT_APPLICABLE


def test_failed_when_ghostmark_itself_still_finds_the_signal():
    summary = VerificationSummary(ghostmark_pass=False, supported_found_before=2, external_verifiers=[])
    assert summary.verdict is VerificationVerdict.FAILED


def test_failed_takes_priority_even_with_passing_external_verifiers():
    summary = VerificationSummary(
        ghostmark_pass=False,
        supported_found_before=1,
        external_verifiers=[_outcome("exiftool", available=True, applicable=True, passed=True)],
    )
    assert summary.verdict is VerificationVerdict.FAILED


def test_unverified_when_no_external_verifier_available():
    summary = VerificationSummary(
        ghostmark_pass=True,
        supported_found_before=1,
        external_verifiers=[
            _outcome("exiftool", available=False, applicable=True, passed=None),
            _outcome("c2patool", available=False, applicable=True, passed=None),
        ],
    )
    assert summary.verdict is VerificationVerdict.UNVERIFIED


def test_unverified_when_external_verifiers_not_applicable():
    summary = VerificationSummary(
        ghostmark_pass=True,
        supported_found_before=1,
        external_verifiers=[
            _outcome("exiftool", available=True, applicable=False, passed=None),
            _outcome("c2patool", available=True, applicable=False, passed=None),
        ],
    )
    assert summary.verdict is VerificationVerdict.UNVERIFIED


def test_partial_when_one_applicable_verifier_disagrees():
    summary = VerificationSummary(
        ghostmark_pass=True,
        supported_found_before=1,
        external_verifiers=[
            _outcome("exiftool", available=True, applicable=True, passed=True),
            _outcome("c2patool", available=True, applicable=True, passed=False),
        ],
    )
    assert summary.verdict is VerificationVerdict.PARTIAL


def test_verified_clean_requires_ghostmark_and_all_applicable_verifiers_to_agree():
    summary = VerificationSummary(
        ghostmark_pass=True,
        supported_found_before=2,
        external_verifiers=[
            _outcome("exiftool", available=True, applicable=True, passed=True),
            _outcome("c2patool", available=True, applicable=True, passed=True),
        ],
    )
    assert summary.verdict is VerificationVerdict.VERIFIED_CLEAN


def test_verified_clean_ignores_inapplicable_verifiers_but_still_requires_at_least_one():
    """A verifier that simply doesn't apply to this file type shouldn't block
    VERIFIED CLEAN, as long as at least one applicable verifier passed."""

    summary = VerificationSummary(
        ghostmark_pass=True,
        supported_found_before=1,
        external_verifiers=[
            _outcome("exiftool", available=True, applicable=True, passed=True),
            _outcome("c2patool", available=True, applicable=False, passed=None),
        ],
    )
    assert summary.verdict is VerificationVerdict.VERIFIED_CLEAN


def test_never_verified_clean_from_ghostmark_alone():
    """The core guarantee: GhostMark saying "clean" is never sufficient by itself."""

    summary = VerificationSummary(ghostmark_pass=True, supported_found_before=3, external_verifiers=[])
    assert summary.verdict is not VerificationVerdict.VERIFIED_CLEAN
    assert summary.verdict is VerificationVerdict.UNVERIFIED


def test_supported_metadata_clean_property_matches_verdict_intent():
    passing = VerificationSummary(
        ghostmark_pass=True,
        supported_found_before=1,
        external_verifiers=[_outcome("exiftool", available=True, applicable=True, passed=True)],
    )
    assert passing.supported_metadata_clean is True

    disagreeing = VerificationSummary(
        ghostmark_pass=True,
        supported_found_before=1,
        external_verifiers=[_outcome("exiftool", available=True, applicable=True, passed=False)],
    )
    assert disagreeing.supported_metadata_clean is False


def test_backward_compatible_exiftool_accessors():
    summary = VerificationSummary(
        ghostmark_pass=True,
        supported_found_before=1,
        external_verifiers=[
            _outcome("exiftool", available=True, applicable=True, passed=True),
        ],
    )
    summary.external_verifiers[0].version = "13.25"
    assert summary.exiftool_pass is True
    assert summary.exiftool_available is True
    assert summary.exiftool_applicable is True
    assert summary.exiftool_version == "13.25"


def test_to_dict_includes_verdict_and_verifier_list():
    summary = VerificationSummary(
        ghostmark_pass=True,
        supported_found_before=1,
        external_verifiers=[_outcome("exiftool", available=True, applicable=True, passed=True)],
    )
    payload = summary.to_dict()
    assert payload["verdict"] == "verified_clean"
    assert len(payload["external_verifiers"]) == 1
    assert payload["external_verifiers"][0]["name"] == "exiftool"
