"""Google production SynthID image benchmark harness (isolated R&D).

Characterises how Google's *real* image watermark behaves under common
transformations, measured by Google's *own* verifier (Vertex AI Imagen watermark
verification). Characterisation only — NOT a remover/evasion tool.

Design guarantees:
  * The Vertex verifier NEVER fabricates a detection. When credentials/API access
    are absent it returns status DETECTOR_UNAVAILABLE.
  * A clearly-labelled MOCK detector exists ONLY so the pipeline/tests can run
    offline; its results are stamped `mock` and are never presented as real
    Google detections.
  * No paid API call is made unless a pilot is run with an explicit opt-in flag
    AND live credentials are present.

Isolated from MarkMyAss production: own directory, own deps, nothing wired in.
"""

__all__ = ["detector", "transforms", "metrics", "schema", "experiment", "report"]
