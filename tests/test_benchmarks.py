"""Benchmarks: generated from the real corpus, never hand-typed, never hides failures."""

from __future__ import annotations

from fastapi.testclient import TestClient

from ghostmark.web.app import create_app
from ghostmark.web.benchmarks import run_benchmarks, to_markdown_table, to_summary_markdown
from ghostmark.web.config import WebConfig


def _config(**overrides) -> WebConfig:
    base = dict(
        mode="hosted",
        base_path="/ghostmark/",
        public_url="https://moseisley.sh/ghostmark",
        session_ttl_seconds=720,
        rate_limit_per_minute=1000,
        max_concurrent_jobs=4,
        processing_timeout_seconds=30,
        max_upload_mb=20,
    )
    base.update(overrides)
    return WebConfig(**base)


def test_run_benchmarks_covers_every_corpus_fixture():
    report = run_benchmarks()
    assert report.fixture_count == 4
    assert {r.path for r in report.results} == {
        "text/hidden-unicode.txt",
        "jpeg/exif-xmp-iptc-comment.jpg",
        "png/exif-xmp-text.png",
        "pdf/docinfo-xmp.pdf",
    }


def test_run_benchmarks_all_pass_on_known_good_corpus():
    report = run_benchmarks()
    assert report.detection_pass == report.fixture_count
    assert report.cleaning_pass == report.fixture_count
    assert report.failures == []


def test_benchmark_report_to_dict_is_json_safe():
    import json

    report = run_benchmarks()
    json.dumps(report.to_dict())  # must not raise


def test_summary_markdown_never_hides_failures():
    """If cleaning is wired to always fail, the summary must say so, not silently show 0 fixtures."""

    from ghostmark.web.benchmarks import BenchmarkReport, FixtureResult

    report = BenchmarkReport(
        ghostmark_version="0.0.0-test",
        generated_at="2026-01-01T00:00:00+00:00",
        exiftool_available=False,
        exiftool_version=None,
        results=[
            FixtureResult(path="fake/one.txt", kind="text", detected_ok=True, cleaned_ok=False, independently_verified_ok=None, detail="oops"),
        ],
    )
    summary = to_summary_markdown(report)
    assert "known failure" in summary.lower()
    assert "fake/one.txt" in summary
    assert "oops" in summary

    table = to_markdown_table(report)
    assert "fake/one.txt" in table
    assert "NO" in table  # the failing cell must render as a visible failure, not blank


def test_summary_markdown_reports_zero_failures_honestly():
    from ghostmark.web.benchmarks import BenchmarkReport, FixtureResult

    report = BenchmarkReport(
        ghostmark_version="0.0.0-test",
        generated_at="2026-01-01T00:00:00+00:00",
        exiftool_available=False,
        exiftool_version=None,
        results=[
            FixtureResult(path="fake/one.txt", kind="text", detected_ok=True, cleaned_ok=True, independently_verified_ok=None),
        ],
    )
    summary = to_summary_markdown(report)
    assert "0 known failures" in summary


def test_benchmarks_route():
    client = TestClient(create_app(_config()))
    resp = client.get("/benchmarks")
    assert resp.status_code == 200
    assert "GhostMark" in resp.text
    assert "Summary" in resp.text
    assert "text/hidden-unicode.txt" in resp.text


def test_benchmarks_page_discloses_corpus_coverage_gaps():
    """Do not hide failures -- also don't imply coverage the corpus doesn't have."""

    client = TestClient(create_app(_config()))
    text = client.get("/benchmarks").text
    assert "C2PA" in text
    assert "not" in text.lower()  # explicit "does not include C2PA fixtures" disclosure


def test_benchmarks_page_has_no_unrendered_placeholders():
    client = TestClient(create_app(_config()))
    text = client.get("/benchmarks").text
    assert "{{" not in text
    assert "}}" not in text


def test_benchmarks_page_has_correction_cta():
    client = TestClient(create_app(_config()))
    text = client.get("/benchmarks").text
    assert "github.com/bens777/ghostmark/issues" in text


def test_api_benchmarks_endpoint():
    client = TestClient(create_app(_config()))
    resp = client.get("/api/benchmarks")
    assert resp.status_code == 200
    body = resp.json()
    assert body["fixture_count"] == 4
    assert body["detection_pass"] == 4
    assert body["cleaning_pass"] == 4
    assert len(body["results"]) == 4


def test_api_benchmarks_leaks_no_filesystem_paths():
    client = TestClient(create_app(_config()))
    text = client.get("/api/benchmarks").text
    assert "C:\\" not in text
    assert "AppData" not in text
