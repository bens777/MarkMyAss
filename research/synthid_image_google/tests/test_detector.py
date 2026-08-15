"""The detector must never fabricate a detection."""

from synthid_image.detector import MockVertexDetector, Status, VertexImagenDetector


def test_mock_is_clearly_labelled_not_a_real_detection():
    r = MockVertexDetector().verify("x.png")
    assert r.status is Status.MOCK
    assert r.detected is None                 # never asserts a real detection
    assert r.raw_result.get("mock") is True
    assert r.estimated_cost_usd == 0.0


def test_vertex_unavailable_without_enable_paid():
    r = VertexImagenDetector(project="p", enable_paid=False).verify("x.png")
    assert r.status is Status.DETECTOR_UNAVAILABLE
    assert r.detected is None


def test_vertex_unavailable_without_project():
    r = VertexImagenDetector(project=None, enable_paid=True).verify("x.png")
    assert r.status is Status.DETECTOR_UNAVAILABLE
    assert r.detected is None


def test_vertex_unavailable_when_sdk_missing():
    # enable_paid + project set, but the google SDK is not installed in this env
    r = VertexImagenDetector(project="p", enable_paid=True).verify("x.png")
    assert r.status is Status.DETECTOR_UNAVAILABLE
    assert r.detected is None
    # crucially, it is never DETECTED/NOT_DETECTED without a real response
    assert r.status not in (Status.DETECTED, Status.NOT_DETECTED)
