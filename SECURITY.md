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

GhostMark ships in two supported configurations with different threat
models -- see `PRIVACY.md` for the user-facing explanation of the
difference.

### Local mode (`ghostmark ui` on your own machine)

- Files and text you process **never leave your computer**. There are no
  network calls, no telemetry, no analytics, and no cloud dependencies.
- The web UI binds to `127.0.0.1` only, never `0.0.0.0` by default -- it
  is not reachable from other devices on your network.
- Uploaded/opened files are treated as **untrusted input**: parsing is
  defensive, temp files use randomized names in a per-session directory,
  filenames are sanitized before touching the filesystem, and uploads are
  size-limited.

### Hosted mode (public web deployment, e.g. moseisley.sh/ghostmark)

This IS a supported configuration as of 0.2.0, deployed per
`DEPLOY_MOSEISLEY.md`, with additional protections specifically because
it's reachable by the public internet:

- GhostMark's own process is never bound to a public interface -- it
  only listens on `127.0.0.1` on the host; a reverse proxy (Caddy) is the
  sole public entry point (see `docker-compose.prod.yml`).
- Runs as a non-root user inside its container.
- Every uploaded file is treated as hostile: allowlisted extensions,
  magic-byte MIME sniffing, a bounded/streaming reader that never
  buffers an unbounded body into memory, and a configurable size limit
  (20 MB by default in production).
- Per-IP rate limiting and a concurrent-job cap with a hard per-job
  timeout, so a handful of large/slow/parallel requests can't exhaust the
  host.
- Security response headers (CSP, `X-Content-Type-Options: nosniff`,
  `X-Frame-Options: DENY`, no permissive CORS -- no
  `Access-Control-Allow-Origin` is ever sent).
- Session data (uploaded + cleaned files) lives only in a randomized,
  per-session temp directory. Downloads are not single-use as of 0.4.0
  (a session's cleaned file and its Verification Receipt are commonly
  downloaded separately, in either order), so retention is enforced by an
  automatic TTL purge instead: every session is deleted after a 10-15
  minute TTL regardless of what was or wasn't downloaded.
- ExifTool and c2patool, GhostMark's independent verifiers, are invoked
  as separate OS processes with a fixed argument list and `shell=False`
  (never string-interpolated into a shell command), and only ever read
  the file being verified -- never passed untrusted user text. Both are
  optional; their absence degrades verification results, it does not
  break the app.
- Unhandled exceptions return a generic error to the client; internals
  (paths, tracebacks) are never included in a response, and access logs
  record only the request path, never file contents or (where avoidable)
  original filenames.

Things that remain explicitly **out of scope** in both modes:

- Cryptographic guarantees about C2PA manifest validity -- GhostMark's C2PA
  support is a structural heuristic, not a conformant validator, and the
  optional c2patool cross-check only reports whether a manifest is
  present, not whether its signature/trust chain is valid (see README's
  support matrix and `/lab/c2pa`).
- Defeating statistical/model-level text watermarks -- GhostMark does not
  claim to do this (see README).
- Running the hosted deployment behind anything other than the documented
  reverse-proxy setup (i.e. exposing GhostMark's own port directly to the
  internet) -- not supported, not hardened for that.

## Reporting other issues

Non-security bugs and feature requests should go through the normal GitHub
issue templates.
