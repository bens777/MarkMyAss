<p class="article-hero">
<img src="static/art/verify-seal.svg" alt="" width="90" height="90" class="hero-illustration" />
</p>

<p class="kicker">No seal leaves this ship unexamined.</p>

# Content Credentials Remover

### The "cr" icon, explained — and what removing it actually involves

If you're here because you saw a small "cr" icon on an image (from
Adobe Firefly, Photoshop, or another Content Authenticity Initiative
member tool) and want to know what it is and whether it can be removed,
this page is for you. If you already know you're dealing with C2PA
specifically, the more technical writeup is at
[/c2pa-remover](c2pa-remover) — this page and that one share a
mechanism but answer different questions.

[Clean a file now →](.)

---

## Content Credentials vs. C2PA — same standard, different name

**C2PA** is the technical specification: a data format for embedding a
signed provenance manifest in a file, maintained by the Coalition for
Content Provenance and Authenticity ([c2pa.org](https://c2pa.org/)).

**Content Credentials** is the consumer-facing brand name for a C2PA
manifest, used across tools built on the standard (Adobe products,
various camera and generative-AI tools). It's the same underlying data —
"Content Credentials" is what you see; C2PA is the spec it's built on.
Official consumer site: [contentcredentials.org](https://contentcredentials.org/).

If you want to check what a Content Credentials manifest actually claims
about a specific file **before** touching it — issuer, edit history,
whether the signature validates — Adobe's official verification tool at
[verify.contentauthenticity.org](https://verify.contentauthenticity.org/verify)
is the right independent tool for that. MarkMyAss does not duplicate
that cryptographic verification; see the limitations section below.

## What MarkMyAss does with a Content Credentials manifest

Same underlying mechanism as [/c2pa-remover](c2pa-remover): MarkMyAss
scans for the JUMBF container a Content Credentials manifest is packaged
in and can strip that container from JPEG and PNG files.

```bash
ghostmark inspect image.jpg --json     # reports c2pa: found/not_found
ghostmark clean image.jpg              # strips the container, if present
```

This is removed as a **structural container**, not decrypted, forged, or
cryptographically altered — MarkMyAss never touches the manifest's
signed contents, it only detects and deletes the container they live in.

## Independent verification

MarkMyAss cross-checks its own detection against the official
[c2patool](https://github.com/contentauth/c2pa-rs) CLI where installed —
the same tool the C2PA ecosystem itself publishes for reading manifests.
A c2patool result of "no manifest found" after cleaning is a genuine
independent confirmation that the container is gone; it is not a claim
about cryptographic validity, because MarkMyAss never validates
signatures in either direction.

## Limitations

- Structural removal only — not a cryptographic operation, and not a
  claim about defeating every possible provenance mechanism.
- JPEG and PNG only; PDF Content Credentials detection is heuristic
  best-effort, removal isn't currently supported for PDF.
- If you need to *read* what a Content Credentials manifest claims
  (rather than remove it), use
  [Adobe's official verify tool](https://verify.contentauthenticity.org/verify) —
  that's a different job than MarkMyAss does.

Full technical methodology, sources, and reproducible commands:
[/lab/c2pa](lab/c2pa).

## Sources

- [Content Credentials — official site](https://contentcredentials.org/)
- [C2PA specification](https://spec.c2pa.org/specifications/specifications/2.2/specs/C2PA_Specification.html)
- [Content Authenticity Initiative verify tool](https://verify.contentauthenticity.org/verify)
- [c2patool (official CLI)](https://github.com/contentauth/c2pa-rs)
