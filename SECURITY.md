# Security Policy

## Reporting a vulnerability

Please do **not** open a public GitHub issue for security vulnerabilities.

Instead, use GitHub's private vulnerability reporting for this repository
(**Security** tab -> **Report a vulnerability**), or open a draft security
advisory. If that is not available, open an issue titled "Security contact
needed" with no details, and a maintainer will follow up with a private
channel.

Please include:

- A description of the vulnerability and its impact.
- Steps to reproduce (a minimal file/text input is ideal).
- The GhostMark version and OS you tested on.

We aim to acknowledge reports within a few days. GhostMark is a small
volunteer-maintained project -- please be patient.

## Supported versions

Only the latest released version of GhostMark receives security fixes.

## Scope and threat model

GhostMark is a **local-first, offline** tool. Its primary security promise
is:

- Files and text you process **never leave your computer**. There are no
  network calls, no telemetry, no analytics, and no cloud dependencies.
- The web UI binds to `127.0.0.1` only, never `0.0.0.0` -- it is not
  reachable from other devices on your network.
- Uploaded/opened files are treated as **untrusted input**: parsing is
  defensive, temp files use randomized names in a per-session directory,
  filenames are sanitized before touching the filesystem, and uploads are
  size-limited.

Things that are explicitly **out of scope**:

- Running GhostMark's web UI on a machine you don't control, or exposing
  it beyond localhost (e.g. via a reverse proxy) -- this is not a supported
  configuration and has not been hardened for multi-user or public
  exposure.
- Cryptographic guarantees about C2PA manifest validity -- GhostMark's C2PA
  support is a structural heuristic, not a conformant validator (see
  README's support matrix).
- Defeating statistical/model-level text watermarks -- GhostMark does not
  claim to do this (see README).

## Reporting other issues

Non-security bugs and feature requests should go through the normal GitHub
issue templates.
