"""EXPERIMENTAL: placeholder for future statistical-watermark-reduction research.

No transformation is implemented here in V0. GhostMark will not silently
rewrite user text on the strength of an unproven technique, and there is
currently no reproducible, independently-verifiable method GhostMark can
point to for defeating a provider's statistical text watermark.

If/when such a method is added, it MUST:
  - be opt-in (never run as part of the default ``clean`` pipeline),
  - be labeled EXPERIMENTAL in the CLI and web UI,
  - state plainly that there is no guarantee the target provider's detector
    is defeated,
  - never run automatically on user text without an explicit flag.
"""

from __future__ import annotations


class StatisticalReductionUnavailable(NotImplementedError):
    """Raised by any call site that tries to invoke unimplemented experimental reduction."""


def reduce_statistical_watermark(text: str, *, provider: str) -> str:
    raise StatisticalReductionUnavailable(
        f"No experimental statistical watermark reduction is implemented for "
        f"provider={provider!r} in this version of GhostMark."
    )
