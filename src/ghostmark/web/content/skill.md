<p class="article-hero">
<img src="static/art/page-metadata-cleaner.webp" alt="" width="440" height="295" class="hero-illustration" />
</p>

<p class="kicker">The crew comes aboard your AI workflow.</p>

# Install MarkMyAss in Your AI Workflow

### Inspect, clean and verify supported signals directly from your AI tools — free, open source, 100% local

MarkMyAss ships as an **Agent Skill**: a small instruction file that
teaches an AI agent to run the local MarkMyAss engine on the files and
text you're working with. Once installed, your AI workflow can
automatically **inspect, clean and verify supported AI watermark,
metadata and provenance signals** — hidden Unicode, EXIF/XMP/IPTC, PDF
and PNG metadata, and supported C2PA container structures — without you
visiting this site.

The workflow the Skill follows is the same honest pipeline as the
cleaner on this site:

<div class="log-entry">
<span class="log-label">The Skill's standing orders</span>
<p>AI creates content or a file → MarkMyAss <strong>inspects</strong>
supported signals → <strong>cleans</strong> what's supported →
<strong>verifies</strong> the result (with ExifTool cross-check when
available) → returns the cleaned file plus a real status report.</p>
</div>

Everything runs on your machine. Nothing is uploaded, and MarkMyAss
stays free.

**Technical honesty, up front:** the Skill uses the exact same
capability model as the rest of MarkMyAss. It removes and verifies
*supported* signals. It does not defeat statistical model-level
watermarks (Claude / Gemini / GPT — their status is always reported as
UNKNOWN, because no public verifier exists), and it never claims "100%
AI-undetectable." See the [AI Watermark Lab](lab) for the full scored
capability matrix.

---

## A. Install from your AI product

Different AI products use different mechanisms — these are the ones
that genuinely support it today.

### Claude Code

Claude Code discovers Agent Skills from your personal skills directory
(`~/.claude/skills/`) or a project's `.claude/skills/` folder.

1. Get the Skill folder:

```bash
git clone https://github.com/bens777/MarkMyAss
```

2. Install it as a personal skill (available in every project):

```bash
mkdir -p ~/.claude/skills && cp -r MarkMyAss/skill/markmyass ~/.claude/skills/
```

&nbsp;&nbsp;&nbsp;&nbsp;…or into one project only: `cp -r MarkMyAss/skill/markmyass YOUR_PROJECT/.claude/skills/`

3. That's it. Ask Claude Code to *"inspect this file for hidden
   metadata"* — it will install the `ghostmark` CLI on first use (the
   Skill checks before installing) and run the inspect → clean →
   verify pipeline.

### Claude (claude.ai web & desktop)

claude.ai supports uploading custom Skills on paid plans (Pro, Max,
Team, Enterprise), with code execution enabled:

1. <a href="static/markmyass-skill.zip" download>Download the MarkMyAss Skill (.zip)</a>
2. In claude.ai, open **Settings → Features → Skills** and upload the
   zip.
3. Enable it, then ask Claude to inspect/clean a file in any chat where
   code execution is available.

*Note: in the claude.ai sandbox, Claude runs the Skill's tooling inside
its code-execution environment rather than on your machine.*

### Claude API / Agent SDK

Building your own agent? The same Skill folder works with the Skills
API (`/v1/skills`) and with filesystem-based skills in the Claude Agent
SDK — point it at `skill/markmyass/` from the repository.

### ChatGPT / OpenAI

**Not currently supported as an installable skill.** OpenAI's products
don't use the Agent Skills format: ChatGPT's mechanism for external
tools is MCP connectors (Developer Mode, paid plans), which require a
*hosted* server — MarkMyAss is deliberately local-only and doesn't
currently ship one. What you can do today: install the CLI (below) and
run it on ChatGPT-produced files yourself, or have a terminal-capable
agent (e.g. Codex CLI) call the same `ghostmark` commands. If OpenAI
adds local-skill support, this page will be updated.

---

## B. Install from the terminal

The Skill drives the same free CLI you can use directly. One command
(verified against the public repository):

```bash
pip install "git+https://github.com/bens777/MarkMyAss"
```

Prefer an isolated install:

```bash
pipx install "git+https://github.com/bens777/MarkMyAss"
```

Then the full pipeline, on anything your AI produced:

```bash
ghostmark inspect document.pdf
ghostmark clean document.pdf
ghostmark verify document.cleaned.pdf
```

For pasted text (hidden Unicode):

```bash
ghostmark inspect-text "your text here"
ghostmark clean-text "your text here"
```

Every command has `--json` for machine-readable output, and `ghostmark
clean` never touches your original file.

---

## What "supported" means here

| Signal | Skill/CLI support |
| --- | --- |
| Hidden Unicode in text | **Supported** — detect + remove + verify |
| EXIF / XMP / IPTC (JPEG, PNG, WebP) | **Supported** — detect + remove + verify |
| PDF DocInfo + XMP | **Supported** — detect + remove + verify |
| C2PA / Content Credentials container | **Partial** — structural detection/removal, not cryptographic validation |
| Claude / Gemini / GPT statistical watermarks | **UNKNOWN** — no public verifier exists; never claimed as removed |

Proof, not promises — the Skill reports what it verified, and says
UNKNOWN when it can't.

---

## Want more than one Skill?

MarkMyAss is the specialist crew that hunts hidden marks and ghosts in
your files. [Moseisley](https://moseisley.sh/?utm_source=markmyass&utm_medium=skill&utm_campaign=acquisition)
is where you get the whole crew: build your own team of AI agents and
assistants to help you work, research, plan and automate — free to
start.

<p><a class="btn primary" href="https://moseisley.sh/?utm_source=markmyass&amp;utm_medium=skill&amp;utm_campaign=acquisition" rel="noopener">Explore Moseisley →</a></p>

[← Back to the MarkMyAss cleaner](.) · [Explore the AI Watermark Lab →](lab)

<script src="static/copy-buttons.js" defer></script>
