# Privacy

GhostMark exists in two modes with genuinely different privacy
guarantees. Read this before uploading anything you consider sensitive.

## Local GhostMark (CLI or `ghostmark ui` on your own computer)

**100% local. Nothing ever leaves your device.**

- No network calls of any kind. No telemetry, no analytics, no crash
  reporting, no update checks.
- The web UI binds to `127.0.0.1` only -- not reachable from other
  devices on your network.
- Files you inspect/clean are read, processed, and written entirely on
  your own filesystem.
- Temporary files (used internally during processing) live in your OS's
  temp directory and are cleaned up when the operation finishes.

This is the same guarantee GhostMark has always made, and it hasn't
changed.

## Hosted GhostMark (https://markmyass.com)

**This is different. Files ARE temporarily uploaded to a server.**

If you use the hosted version instead of running GhostMark locally:

- Uploaded files and pasted text are sent to, and temporarily processed
  on, the GhostMark server running at markmyass.com.
- Files are held only in a randomized, per-session temporary directory
  on that server -- never written to a database, never made
  permanent, and never included in application logs (server access
  logs record only the request path, e.g. `POST /api/inspect/file`, not
  the file's name or contents).
- A session's cleaned file and its downloadable Verification Receipt can
  be fetched separately, in either order, so nothing is deleted the
  instant you download one of them. Instead, the whole session
  (original + cleaned copy + receipt data) is deleted automatically
  after a short timeout -- 10-15 minutes maximum (see
  `GHOSTMARK_SESSION_TTL_MINUTES` in `docker-compose.prod.yml` for the
  exact current value).
- No accounts, no cookies used for tracking, no analytics, no
  advertising, no third-party trackers of any kind.
- No CORS is configured and the API is not intended for cross-origin use
  by other websites.

If you would rather not upload anything anywhere, use local GhostMark
instead -- see the README's "Run GhostMark locally" section. Both modes
run the exact same open-source code
(https://github.com/bens777/MarkMyAss); the only difference is where the
processing happens.

## What GhostMark never does, in either mode

- Never sells or shares data with third parties (there is nothing
  collected to share).
- Never uses uploaded content to train any model.
- Never requires an account, email address, or payment.
- Never adds tracking pixels, fingerprinting scripts, or ad networks.

## Independent verification (ExifTool + c2patool)

When available, GhostMark shells out to a locally/server-installed copy
of [ExifTool](https://exiftool.org/) and/or
[c2patool](https://github.com/contentauth/c2pa-rs) to independently
cross-check a cleaned file. This happens entirely within the same
process/server that already has the file -- neither tool is a network
service, and no data is sent anywhere by using them.

## Questions or reports

See `SECURITY.md` for how to report a security issue, or open a GitHub
issue for a general privacy question.
