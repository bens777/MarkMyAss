"""SynthID-Text behaviour study (isolated R&D).

This package characterises how the SynthID-Text watermark statistic behaves
when watermarked (AI-generated) tokens are progressively replaced by
un-watermarked ("human original") tokens, and under a range of realistic
edit categories.

It is deliberately isolated from the MarkMyAss production package
(`src/ghostmark`). It shares no code, no dependencies, and no runtime with
production. Nothing here is wired into the cleaner, API, CLI, or Docker image.

Scope guardrails (see README.md):
  * Uses OUR OWN local watermark keys, never Google's production key.
  * Success is never measured against defeating any detector; this package
    only *characterises* a mechanism and reports it honestly.
"""

__all__ = ["metrics", "mixtures", "edits"]
