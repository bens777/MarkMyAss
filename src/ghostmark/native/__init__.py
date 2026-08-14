"""MarkMyAss's native tag-level metadata engine.

The container layer (``ghostmark.formats``) isolates metadata payloads
(EXIF blobs, XMP packets, IPTC resource blocks, PNG text chunks); this
package reads *inside* those payloads and normalizes what it finds into
:class:`~ghostmark.native.signals.MetadataField` records, so MarkMyAss
can report WHAT is embedded (author, software, GPS, AI-provenance
markers, ...) without shelling out to any external tool.

ExifTool's role relative to this package: reference implementation,
differential-testing oracle (see tests/integration/), and optional
independent external verifier -- never a runtime requirement.

Every module declares its implementation provenance in its docstring.
"""

from ghostmark.native.signals import MetadataField, SignalCategory  # noqa: F401
