# Deploying MarkMyAss to markmyass.com

This is a step-by-step guide for deploying MarkMyAss (engine name:
GhostMark) on your Moseisley VPS, written for someone who isn't a
developer. It assumes your VPS already runs Caddy (if it runs something
else, the general shape is the same but the exact reload command will
differ).

MarkMyAss lives on its own apex domain, `https://markmyass.com` -- that
is the one and only canonical host. `www.markmyass.com` is NOT a second
site: Caddy permanently redirects it to the apex (see
`deploy/Caddyfile.snippet`), and no canonical URL, sitemap entry or
robots/llms line ever uses `www`. Point DNS `A`/`AAAA` records for BOTH
`markmyass.com` and `www.markmyass.com` at this VPS before starting --
Caddy's automatic HTTPS needs that to issue certificates for both
names.

## What you're deploying

- A small Docker container running MarkMyAss's web app on
  `127.0.0.1:8765` -- **not** exposed to the internet directly.
- The image is **built by GitHub Actions and pulled from GHCR**
  (`ghcr.io/bens777/markmyass:latest`) -- the VPS never compiles
  anything itself. Every push to `main` publishes a fresh image.
- ExifTool and c2patool (for independent verification) installed inside
  that same image, automatically, when GitHub Actions builds it.
- Caddy serves `https://markmyass.com` as its own site and
  proxies every request to that container. MarkMyAss itself never
  touches the public internet directly.
- (If you'd rather keep MarkMyAss at a subpath of an existing domain
  instead of its own domain -- e.g. `https://example.com/ghostmark` -- both
  `docker-compose.prod.yml` and `deploy/Caddyfile.snippet` document that
  as "Option B." Everything else in this guide is the same either way.)

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

**3. One-time: make sure the GHCR package is public.**

The very first time GitHub Actions publishes the image, GitHub creates
the `markmyass` package as **private** (that's GitHub's default, even
for public repositories). Make it public once so the VPS can pull it
anonymously, with no `docker login` and no token stored on the VPS:

1. On GitHub, open your profile → **Packages** → **markmyass**
   (direct link: https://github.com/users/bens777/packages/container/package/markmyass).
2. On the package page, click **Package settings** (right-hand side).
3. At the bottom, under **Danger Zone**, click **Change visibility**,
   select **Public**, and confirm by typing the package name.

This only ever needs to be done once (note: GitHub does not let you make
a public package private again).

**4. Get the MarkMyAss deploy files onto the VPS.**

If you don't already have them there:

```bash
cd /opt
git clone https://github.com/bens777/MarkMyAss.git
cd MarkMyAss
```

If you already cloned it before, just update it:

```bash
cd /opt/MarkMyAss
git pull
```

(The clone is only needed for `docker-compose.prod.yml` and the Caddy
snippet -- the application code itself arrives inside the pulled image.)

**5. Pull and start MarkMyAss.**

```bash
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

This downloads the ready-made image from GHCR (ExifTool and c2patool are
already inside it) and starts it in the background. Nothing is compiled
on the VPS. If you ever need to build locally instead (for development),
use `docker-compose.yml`, which keeps the `build: .` behavior.

**6. Confirm it's running correctly, from the VPS itself:**

```bash
curl -s http://127.0.0.1:8765/health
docker ps --filter name=markmyass
docker system df
df -h /
```

You should see something like:

```json
{"status": "ok", "ghostmark": "0.5.0", "exiftool_available": true, "c2patool_available": true}
```

If `exiftool_available` or `c2patool_available` is `false`, something is
wrong with the published image -- check the "Publish Docker image" run on
the repo's GitHub Actions page, then re-run step 5. MarkMyAss still runs fine with either one missing (it degrades to
"unknown"/"unverified" for the checks that tool would have performed), so
this isn't fatal, but you won't get independent verification for that
signal.

**7. Add MarkMyAss to your Caddy configuration.**

Open your existing Caddyfile (commonly `/etc/caddy/Caddyfile`):

```bash
sudo nano /etc/caddy/Caddyfile
```

Copy BOTH blocks from this repo's `deploy/Caddyfile.snippet` file --
the `www.markmyass.com { ... }` permanent redirect and the
`markmyass.com { ... }` site block -- and paste them as new, separate
site blocks anywhere in the file. They do not need to live inside any
other site's block, since markmyass.com is its own domain.

Save and exit (in `nano`: Ctrl+O, Enter, then Ctrl+X).

**8. Reload Caddy so it picks up the change:**

```bash
sudo systemctl reload caddy
```

(If your setup doesn't use systemd, use whatever command you normally
use to reload Caddy without dropping connections -- `caddy reload` if
you run it directly.)

**9. Visit it in a browser:**

```
https://markmyass.com
```

You should see the MarkMyAss page. Try pasting some text or uploading a
small PDF/image and running through Inspect → Clean → Verify → Download
to confirm everything works end to end.

## Updating MarkMyAss later

```bash
cd /opt/MarkMyAss
git pull
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
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

## What's different from running MarkMyAss locally

The local desktop version of MarkMyAss (`ghostmark ui` on your own
computer) keeps files 100% on your machine. This hosted version at
markmyass.com is different: uploaded files are processed
temporarily on the VPS and automatically deleted within a few minutes
(a session's cleaned file and its Verification Receipt aren't
necessarily downloaded at the same moment, so deletion is on a timer
rather than tied to the first download -- see `PRIVACY.md` for the exact
policy). Nothing is stored permanently, logged, or put in a database,
but it isn't the same "never leaves your device" guarantee as the local
tool.

## Configuration reference

All of these are set in `docker-compose.prod.yml` already, with
reasonable defaults. You only need to touch them if you want to change
behavior:

| Variable | Default | What it does |
| --- | --- | --- |
| `GHOSTMARK_MAX_UPLOAD_MB` | `10` | Max upload size |
| `GHOSTMARK_SESSION_TTL_MINUTES` | `8` | How long an unclaimed cleaned file is kept before automatic deletion (max 15) |
| `GHOSTMARK_RATE_LIMIT_PER_MINUTE` | `20` | Requests per minute allowed per visitor IP on the API |
| `GHOSTMARK_MAX_CONCURRENT` | `4` | Max file-processing jobs running at once |
| `GHOSTMARK_PROCESSING_TIMEOUT_SECONDS` | `30` | Hard timeout per processing job |
