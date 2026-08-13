# Deploying GhostMark to moseisley.sh/ghostmark

This is a step-by-step guide for deploying GhostMark on your Moseisley
VPS, written for someone who isn't a developer. It assumes your VPS
already runs Caddy as the reverse proxy in front of moseisley.sh (if it
runs something else, the general shape is the same but the exact reload
command will differ).

## What you're deploying

- A small Docker container running GhostMark's web app on
  `127.0.0.1:8765` -- **not** exposed to the internet directly.
- ExifTool (for independent verification) installed inside that same
  container, automatically, during the build.
- Your existing Caddy server proxies `https://moseisley.sh/ghostmark/`
  requests to that container. GhostMark itself never touches the public
  internet directly.

## One-time setup

**1. SSH into your VPS** the way you normally do.

**2. Make sure Docker and Docker Compose are installed.**

```bash
docker --version
docker compose version
```

If either command says "not found," install Docker first (see
https://docs.docker.com/engine/install/ for your VPS's Linux
distribution), then come back here.

**3. Get the GhostMark code onto the VPS.**

If you don't already have it there:

```bash
git clone https://github.com/bens777/ghostmark.git
cd ghostmark
```

If you already cloned it before, just update it:

```bash
cd ghostmark
git pull
```

**4. Build and start GhostMark.**

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

This builds the image (installing GhostMark, ExifTool, and c2patool inside
it) and starts it in the background. The first build takes a few minutes
(c2patool is compiled from source); after that, `up -d --build` only
rebuilds what changed.

**5. Confirm it's running correctly, from the VPS itself:**

```bash
curl http://127.0.0.1:8765/health
```

You should see something like:

```json
{"status": "ok", "ghostmark": "0.4.0", "exiftool_available": true, "c2patool_available": true}
```

If `exiftool_available` or `c2patool_available` is `false`, something went
wrong with the Docker build -- re-run step 4 and check the output for
errors. GhostMark still runs fine with either one missing (it degrades to
"unknown"/"unverified" for the checks that tool would have performed), so
this isn't fatal, but you won't get independent verification for that
signal.

**6. Add GhostMark to your Caddy configuration.**

Open your existing Caddyfile (commonly `/etc/caddy/Caddyfile`):

```bash
sudo nano /etc/caddy/Caddyfile
```

Find the block for `moseisley.sh` (it will look like
`moseisley.sh { ... }`). Copy the contents of this repo's
`deploy/Caddyfile.snippet` file and paste it **near the top, inside that
block, above any existing catch-all `reverse_proxy` or `handle { }`
block** for the rest of the site. (Full explanation of why is in the
comments inside that file.)

Save and exit (in `nano`: Ctrl+O, Enter, then Ctrl+X).

**7. Reload Caddy so it picks up the change:**

```bash
sudo systemctl reload caddy
```

(If your setup doesn't use systemd, use whatever command you normally
use to reload Caddy without dropping connections -- `caddy reload` if
you run it directly.)

**8. Visit it in a browser:**

```
https://moseisley.sh/ghostmark
```

You should see the GhostMark page. Try pasting some text or uploading a
small PDF/image and running through Inspect → Clean → Verify → Download
to confirm everything works end to end.

## Updating GhostMark later

```bash
cd ghostmark
git pull
docker compose -f docker-compose.prod.yml up -d --build
```

No Caddy changes are needed for a routine update (only if this guide's
deploy files change, which will be called out in the project's
CHANGELOG.md).

## Checking logs / troubleshooting

```bash
docker compose -f docker-compose.prod.yml logs -f
```

Press Ctrl+C to stop watching.

To check the container is healthy:

```bash
docker compose -f docker-compose.prod.yml ps
```

To restart it:

```bash
docker compose -f docker-compose.prod.yml restart
```

## What's different from running GhostMark locally

The local desktop version of GhostMark (`ghostmark ui` on your own
computer) keeps files 100% on your machine. This hosted version at
moseisley.sh/ghostmark is different: uploaded files are processed
temporarily on the VPS and automatically deleted (within a few minutes,
and immediately after a file is downloaded) -- see `PRIVACY.md` for the
exact policy. Nothing is stored permanently, logged, or put in a
database, but it isn't the same "never leaves your device" guarantee as
the local tool.

## Configuration reference

All of these are set in `docker-compose.prod.yml` already, with
reasonable defaults. You only need to touch them if you want to change
behavior:

| Variable | Default | What it does |
| --- | --- | --- |
| `GHOSTMARK_MAX_UPLOAD_MB` | `20` | Max upload size |
| `GHOSTMARK_SESSION_TTL_MINUTES` | `12` | How long an unclaimed cleaned file is kept before automatic deletion (max 15) |
| `GHOSTMARK_RATE_LIMIT_PER_MINUTE` | `20` | Requests per minute allowed per visitor IP on the API |
| `GHOSTMARK_MAX_CONCURRENT` | `4` | Max file-processing jobs running at once |
| `GHOSTMARK_PROCESSING_TIMEOUT_SECONDS` | `30` | Hard timeout per processing job |
