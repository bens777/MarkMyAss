# Google SynthID — Official Research Notes (R&D)

**Purpose.** Characterise how Google's *real production* SynthID watermark
behaves, using **current official Google / DeepMind primary sources**. This is
provenance **characterisation** (measuring robustness with Google's own
verifier), not a removal/evasion effort — consistent with the SynthID-Text lab
studies already in `research/`. Nothing here touches MarkMyAss production.

> Sourcing rule: statements below are tagged **[OFFICIAL]** (Google/DeepMind/
> Google Cloud primary pages) or **[SECONDARY]** (third-party testing/blogs).
> Where Google has not published an answer, this doc says so rather than
> guessing.

_Compiled 2026-08-15 from the sources in the last section._

---

## 1. Product / model matrix — what uses SynthID today

**[OFFICIAL]** DeepMind states SynthID is integrated across four modalities and
these products (DeepMind SynthID page; SynthID Detector post, 2025-05-20):

| Modality | Google products that embed SynthID | Notes |
|---|---|---|
| **Image** | **Imagen** (3 / 4 on Vertex AI) · **Gemini 2.5 Flash Image** ("Nano Banana") | Imagen: watermark **on by default**. Gemini 2.5 Flash Image: **all** generated/edited images watermarked. |
| **Video** | **Veo** (2 / 3) | "All creations generated with Veo utilize SynthID." |
| **Audio** | **Lyria** (music) · **NotebookLM** Audio Overviews / podcast feature | Inaudible spectrogram watermark. |
| **Text** | **Gemini app and web experience** (text output) | Modulates token-probability during generation. |

**[OFFICIAL]** "Over **10 billion** pieces of content have already been
watermarked with SynthID" (SynthID Detector post, 2025-05-20).

Anthropic / OpenAI: **not** SynthID (out of scope here; covered by the earlier
provider question — do not assume Anthropic uses SynthID).

---

## 2. Per-modality: embedding, robustness, verification

### Image  ← primary focus
- **Embedding [OFFICIAL].** "Two deep learning models — for watermarking and
  identifying — that have been trained together," "embedded directly into the
  **pixels** of an image," "visually aligning the watermark to the original
  content," and it "remains detectable even when metadata is lost" (DeepMind
  image blog, 2023-08-29). So the mark is a **learned pixel-space perturbation**,
  not a metadata/C2PA tag and **not a single pixel**.
- **Spatially distributed? [OFFICIAL wording is indirect].** Google does *not*
  publish the spatial layout. But the mark is "designed to stand up to
  **cropping**" (DeepMind SynthID page). A watermark that survives cropping
  cannot live in one location — it must be **redundant / spread across the
  image**. Treat "redundant across the image" as a *necessary inference from the
  official cropping claim*, not a published architectural spec. (Specific
  numbers like "survives 50% crop / JPEG q50" are **[SECONDARY]**, not official.)
- **Robustness [OFFICIAL].** "designed to stand up to modifications like
  cropping, adding filters, changing frame rates, or lossy compression" (SynthID
  page); "adding filters, changing colours and brightness … various lossy
  compression schemes — most commonly used for JPEGs" (image blog). Explicit
  official caveat: **"not foolproof against extreme image manipulations."**
- **Detection is not public at pixel level**; see §3.

### Video (Veo)
- **[OFFICIAL]** Watermark embedded into generated frames the moment content is
  created; "designed to stand up to … changing frame rates, or lossy
  compression." Verifiable via SynthID Detector / Gemini app.

### Audio (Lyria / NotebookLM)
- **[OFFICIAL]** "inaudible to the human ear, and can't be altered by common
  modifications like adding noise, MP3 compression, or changing the speed."
  SynthID Detector "pinpoints specific segments where a SynthID watermark is
  detected."

### Text (Gemini)
- **[OFFICIAL]** Generative watermark: "SynthID adjusts these probability scores
  to generate a watermark" (token-by-token). Applied to the "Gemini app and web
  experience." Method open-sourced (SynthID-Text in the Responsible GenAI
  Toolkit / Hugging Face; Nature paper 2024-10). Detection needs the **secret
  key held by Google** → no public text detector API. (This is exactly why our
  three local `research/synthid_text*` studies use our *own* key and cannot
  speak to Google's production text detector.)

---

## 3. Verification options — public? API? access limits

| Verifier | Modalities | Public? | Automatable API? | Access / limits |
|---|---|---|---|---|
| **Gemini app** ("upload and ask if made/edited by Google AI") | image/video/audio | Yes (consumer) | **No** structured verify API | Manual, one item at a time; not a benchmarking interface. **[OFFICIAL]** |
| **SynthID Detector portal** | image/video/audio/text | **No** — waitlist | **No public API** | "Journalists, media professionals and researchers can join our waitlist"; early testers only (2025-05-20). Highlights likely-watermarked regions. **[OFFICIAL]** |
| **Vertex AI — Imagen watermark verification** | image | Yes, with GCP account | **Yes (billed)** | "You can use the API to verify whether an image was generated using Imagen." Model Garden lists an `imagewatermarkdetector`. Watermark **on by default** (`add_watermark`). Returns a confidence/decision (labels reported as HIGH/MEDIUM/LOW are **[SECONDARY]** — confirm against the live API). **[OFFICIAL]** |

**Key takeaway:** the **only programmatically automatable, official verifier we
can actually use** is **Vertex AI's Imagen watermark verification** (needs a GCP
project + billing + credentials). The SynthID Detector portal has **no public
API** and is waitlist-gated; the Gemini app is manual. There is **no public
verifier for Google's production text or audio** for us.

---

## 4. Determinism / keys — official vs unknown

- **Text [OFFICIAL / published].** Keyed (watermarking keys), deterministic
  given key + context, open-sourced. Detection requires Google's secret
  production key.
- **Image [UNPUBLISHED].** Google has **not** disclosed whether image SynthID
  is keyed, whether it is deterministic, or whether the *same* pattern is reused
  across images vs varying per image/content. The only public hint is that the
  embedder is "visually aligned to the original content" (image blog), which
  *implies content-dependence* but says nothing about keys or determinism.
  → **Same-vs-different watermark across images, model/content/key dependence:
  not officially answered. Do not assume.**

---

## 5. The "1-pixel image" idea — verdict

- **Can Google's generators output a ~1-pixel image?** No. Imagen and Gemini
  2.5 Flash Image produce images at fixed supported sizes/aspect ratios
  (hundreds–1024+ px per side); they do not emit 1×1 (or tiny) images. Google
  has not published a minimum watermarkable size.
- **Would SynthID apply?** Image SynthID is a *spatially distributed* pixel
  perturbation; it needs many pixels of capacity. A 1-pixel (or sub-threshold)
  image has effectively **no capacity** to carry it.
- **Would the experiment reveal anything?** **No.** It is a degenerate case the
  generators will not produce and the watermark cannot occupy. It would tell us
  nothing about production behaviour. **Recommendation: drop it.** The
  informative capacity question is instead: *how small / how cropped can a
  genuine Imagen image get before the Vertex verifier drops from HIGH → LOW?* —
  which the benchmark in §7 measures directly.

---

## 6. Obtaining genuine SynthID-positive images + repeatable verification

The clean, fully-official pipeline (generation and verification from the **same
production system**, so positivity is guaranteed and re-checkable):

1. **Generate** with **Imagen on Vertex AI** (watermark on by default). This
   yields genuine, production-watermarked images we own.
2. **Confirm positive** by calling the **Vertex Imagen verification API** on each
   fresh image — keep only those the real verifier returns at **HIGH** as the
   benchmark baseline (record the label).
3. **Re-verify after each transformation** with the *same* API → repeatable,
   apples-to-apples confidence readings (HIGH → MEDIUM → LOW/absent).

Why Imagen-on-Vertex over the Gemini app / SynthID Detector: it is the only
route where **both** generation and verification are official **and**
programmatic, so a benchmark is reproducible and scriptable. (Gemini 2.5 Flash
Image is also on Vertex and also watermarks — a viable second source once the
Imagen path works.)

**Hard dependency:** all of the above needs a **GCP project with Vertex AI
enabled, billing, and credentials.** Without it we **cannot** touch Google's
production verifier at all (portal = waitlist, no API; text/audio = no public
verifier). This is the gating blocker to state plainly.

---

## 7. Proposed first real-image benchmark (design only — not implemented)

**Goal:** characterise how Google's *production* image watermark degrades under
common transforms, measured by Google's *own* verifier. Characterisation only —
no attempt to optimise against or defeat the watermark.

**Pipeline:** `generate (Imagen/Vertex) → verify baseline (HIGH) → apply one
transform → re-verify → record`.

**Transforms (each vs an untouched control):**
- Screenshot round-trips ×1 / ×2 / ×5 / ×10 (re-render + rescale loops)
- JPEG recompression quality sweep (95 / 85 / 75 / 50)
- Resize down/up (e.g. 0.75× / 0.5× then back)
- Crop (10% / 25% / 50%)
- Format conversions: PNG ↔ JPEG ↔ WebP
- Mild colour/contrast/brightness shifts

**Record per image × transform:** verifier label before/after (HIGH/MEDIUM/LOW/
none), transform params, SSIM/PSNR vs original (visual cost), file size, runtime.

**Reuse:** the transform/metrics/experiment-DB scaffolding from the SynthID-Text
labs transfers directly; only the detector adapter changes (Vertex verify API
instead of the local Weighted-Mean detector).

### Cost safety (MUST clear before running)
Vertex AI **charges** for Imagen generation and for verification calls. Rough
order-of-magnitude (to confirm against live pricing):
- Generation ≈ a few ¢/image (Imagen).
- Verification ≈ sub-cent to ~1¢/call (confirm).
- A 10-image pilot × ~15 transform variants ≈ 10 gens + ~160 verify calls ≈
  **well under $5** — but pricing is unconfirmed and billing is real.

**Per the project cost rule, do not auto-launch.** First step is a **≤10-image
pilot** to (a) confirm the verify API's real response schema and per-call price,
and (b) validate the pipeline — run only after the user provisions GCP/Vertex
access and explicitly approves the spend.

---

## 8. What we can test immediately vs what's unknowable

**Immediately (no Google access):**
- Build the transform + metrics + experiment-DB harness and a **DetectorAdapter**
  interface with a Vertex backend stub (mirrors the existing labs).
- Everything is inert until real credentials + images exist — no fabricated
  detections.

**Immediately (once GCP/Vertex is provisioned + spend approved):**
- The full §7 benchmark against the **real** Imagen verifier.

**Unknowable without Google's detector/key:**
- Google's production **text** and **audio** detection (no public verifier/API).
- Image SynthID **keying/determinism** and cross-image pattern reuse (§4).
- The exact spatial architecture / capacity / internal thresholds (unpublished).
- Anything about images generated *outside* Vertex that we can only check via the
  waitlisted portal.

**Bright line (unchanged):** this is measurement of the real watermark's
robustness, not a remover. We are not building, and this doc does not design, a
production "clean the watermark" feature.

---

## 9. Official sources (with dates)

- DeepMind — **SynthID** model page (products matrix, robustness wording): https://deepmind.google/models/synthid/ *(living page; accessed 2026-08-15)*
- DeepMind — **Identifying AI-generated images with SynthID** (image architecture): https://deepmind.google/blog/identifying-ai-generated-images-with-synthid/ *(2023-08-29)*
- Google — **SynthID Detector — a new portal** (portal, waitlist, modalities, 10B): https://blog.google/innovation-and-ai/products/google-synthid-ai-content-detector/ *(2025-05-20)*
- Google Developers Blog — **Introducing Gemini 2.5 Flash Image** (all images SynthID): https://developers.googleblog.com/introducing-gemini-2-5-flash-image/ *(2025-08-26)*
- Google Cloud — **A developer's guide to Imagen 3 on Vertex AI** (default watermark; verify via API): https://cloud.google.com/blog/products/ai-machine-learning/a-developers-guide-to-imagen-3-on-vertex-ai *(2024-08-30)*
- Google Cloud — Vertex AI **Imagen watermark verification** quickstart / `imagewatermarkdetector` Model Garden entry *(page moved/404 at fetch time 2026-08-15; API existence confirmed via the Imagen 3 developer guide above — reconfirm live before building)*
- Google AI for Developers — **SynthID text tools** (open-source text watermark/detector): https://ai.google.dev/responsible/docs/safeguards/synthid
- Nature — **SynthID-Text** (scalable text watermarking) *(2024-10)*

**[SECONDARY] (used only where flagged, never as ground truth):** third-party
robustness tests reporting numeric thresholds (crop ~50%, JPEG ~q50) and the
HIGH/MEDIUM/LOW confidence labels — to be confirmed against the live Vertex API.
