<p class="article-hero">
<img src="static/art/page-c2pa.webp" alt="Illustration: the pirate captain holds a sealed manifest up to the light while a sneaky ghost hides behind the paper" width="440" height="295" class="hero-illustration" />
</p>

<p class="kicker">The captain reads the manifest first.</p>

# C2PA Remover

### What MarkMyAss actually sees, removes, and cannot cryptographically validate

C2PA (the Coalition for Content Provenance and Authenticity) is a
technical standard for embedding a signed provenance manifest — what
tool created or edited a file, and when — directly inside an image, PDF,
or other media file. This page explains exactly what MarkMyAss can and
can't do with one.

[Clean a file now →](.)

---

## What C2PA actually is

C2PA manifests are packaged inside a file using a container format
called **JUMBF** (JPEG Universal Metadata Box Format), embedded as a
JPEG APP11 segment or a PNG `caBX` chunk. The manifest itself can be
**cryptographically signed**, meaning a compliant validator can check
whether the content has been altered since the manifest was created and
who signed it — that's the actual security property C2PA provides.
Official spec:
[spec.c2pa.org](https://spec.c2pa.org/specifications/specifications/2.2/specs/C2PA_Specification.html).

## What MarkMyAss sees

MarkMyAss scans for the **structural presence** of a JUMBF container —
the byte-level markers indicating a C2PA manifest is embedded. This is a
heuristic structural scan, not a manifest parser: MarkMyAss doesn't read
the manifest's claims, verify its signature, or check a trust chain.

## What MarkMyAss can remove

If a JUMBF container is present, MarkMyAss can strip it from JPEG and
PNG files — a structural removal, not a cryptographic operation. This
means the C2PA-formatted evidence trail is gone from that file; it does
not mean MarkMyAss broke or forged any cryptography, because it never
touched the manifest's contents to begin with.

```bash
ghostmark inspect image.jpg --json     # reports c2pa: found/not_found
ghostmark clean image.jpg              # strips the JUMBF container, if present
```

## Independent verification: c2patool

MarkMyAss cross-checks its own C2PA detection with the official
[c2patool](https://github.com/contentauth/c2pa-rs) CLI (Apache-2.0/MIT),
where installed. c2patool reads a file read-only and reports whether it
finds a manifest — this is a genuine second opinion on *presence*, but
it is **not a cryptographic trust validator either** in how MarkMyAss
uses it: a clean c2patool result means "no manifest found," not "this
content's provenance was cryptographically verified."

```bash
c2patool image.jpg   # read-only manifest presence check
```

## Limitations — read this before relying on this page

- **Not cryptographic validation.** MarkMyAss does not verify signatures,
  trust chains, or manifest authenticity. It only detects/removes the
  container structure.
- **JPEG and PNG only.** PDF C2PA detection is a heuristic best-effort;
  removal isn't currently supported for PDF.
- **Absence isn't proof of anything beyond absence.** A file reporting
  "no C2PA container found" tells you MarkMyAss's structural scan didn't
  find one — it says nothing about whether the content is AI-generated,
  human-made, or edited.
- **Robust provenance schemes are an active adversarial research area.**
  Removing a JUMBF container defeats *that specific embedding*; it is
  not a general claim about defeating every possible provenance
  mechanism now or in the future.

Full methodology, sources, and test commands: [/lab/c2pa](lab/c2pa).

For the consumer-facing "Content Credentials" branding of this same
standard (the small "cr" icon you might see on an image), see
[/content-credentials-remover](content-credentials-remover).

## Sources

- [C2PA specification](https://spec.c2pa.org/specifications/specifications/2.2/specs/C2PA_Specification.html)
- [c2patool (official CLI)](https://github.com/contentauth/c2pa-rs)
- [c2pa.org](https://c2pa.org/)
