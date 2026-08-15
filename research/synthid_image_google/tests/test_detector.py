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


class _FakeResponse:
    """Matches the documented WatermarkVerificationResponse contract:
    a `watermark_verification_result` string + a `_prediction_response`."""

    def __init__(self, result, prediction_response=None):
        self.watermark_verification_result = result
        self._prediction_response = prediction_response


def _det(**kw):
    return VertexImagenDetector(project="p", enable_paid=True, **kw)


def test_build_result_positive_label_maps_to_detected():
    d = _det(positive_labels=["ACCEPT"], price_per_call_usd=0.02)
    r = d._build_result(_FakeResponse("ACCEPT", {"predictions": [{"decision": "ACCEPT"}]}))
    assert r.status is Status.DETECTED
    assert r.detected is True
    assert r.confidence == "ACCEPT"
    assert r.raw_result["watermark_verification_result"] == "ACCEPT"
    assert r.raw_result["prediction_response"] == {"predictions": [{"decision": "ACCEPT"}]}
    assert r.estimated_cost_usd == 0.02


def test_build_result_negative_label_maps_to_not_detected():
    d = _det(negative_labels=["reject"])   # case-insensitive
    r = d._build_result(_FakeResponse("REJECT"))
    assert r.status is Status.NOT_DETECTED
    assert r.detected is False
    assert r.confidence == "REJECT"


def test_build_result_unknown_decision_is_uncertain_not_fabricated():
    d = _det()  # no label sets configured -> decision strings are undocumented
    r = d._build_result(_FakeResponse("SOME_LABEL"))
    assert r.status is Status.UNCERTAIN
    assert r.detected is None            # never guesses a boolean
    assert r.confidence == "SOME_LABEL"  # raw string preserved for research


def test_build_result_none_decision():
    r = _det()._build_result(_FakeResponse(None))
    assert r.status is Status.UNCERTAIN
    assert r.detected is None
    assert r.confidence is None


def test_build_result_preserves_nonserializable_raw():
    obj = object()  # not JSON serialisable
    r = _det()._build_result(_FakeResponse("X", prediction_response=obj))
    assert "prediction_response" in r.raw_result
    assert isinstance(r.raw_result["prediction_response"], str)  # repr fallback, still preserved
