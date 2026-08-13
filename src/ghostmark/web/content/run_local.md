<p class="article-hero">
<img src="static/run-local-hero.svg" alt="" width="240" height="130" class="hero-illustration" />
</p>

<p class="kicker">Sail your own stack.</p>

# Run Models Locally

### A practical guide to avoiding provider-side provenance at the source

GhostMark's main tool cleans up supported metadata and provenance signals
**after** a file already exists — it inspects, cleans, and verifies what a
hosted AI provider (or any tool) left behind. That's useful, but it's
downstream of the problem.

There's another path upstream of it: run the model yourself. If you
generate text or images with an **open-weight model under your own
inference stack**, you are no longer dependent on a hosted provider's own
generation pipeline, and whatever that provider's service adds at
generation time or file-export time simply never happens in the first
place.

This page is a practical, no-hype guide to that path: what "open-weight"
actually means, what's realistic to run given your hardware and budget,
which current models and tools are worth using, and when renting a GPU
beats buying one. It's written for developers, not for people looking for
a five-minute miracle.

[← Back to the GhostMark cleaner](.)

---

## Hosted vs. local: what actually changes

### Hosted closed models (Anthropic Claude, OpenAI GPT, Google Gemini, and similar)

These are usually the best all-around choice for most people: frontier
quality, no setup, no hardware, and the provider handles scaling and
reliability for you. The tradeoff is that **you are calling someone
else's pipeline**. The provider controls how your request is processed,
what's logged, and what (if anything) is embedded in what comes back --
including any provenance or watermarking signal the provider chooses to
attach, such as [C2PA Content Credentials](https://c2pa.org/) on
generated images, or a statistical bias in how the model samples tokens
for text (see GhostMark's main page for why that specific mechanism can't
currently be verified by anyone outside the provider).

### Open-weight models, run yourself

"Open-weight" means the trained model's parameters are published for
anyone to download and run -- on your own laptop, your own server, or a
rented GPU. You control the entire stack: the inference engine, the
runtime, and the output pipeline. Nothing is added to your output that
you didn't put there yourself, because there is no hosted service in the
loop at generation time.

**Open-weight is not the same as "open source."** Some releases (DeepSeek,
Qwen, Mistral's newer models, Microsoft's Phi, OpenAI's gpt-oss) use the
permissive, OSI-recognized **Apache 2.0** or **MIT** licenses. Others
(Meta's Llama family, Google's Gemma) ship under custom terms that the
[Open Source Initiative does not consider open source](https://opensource.org/)
-- they typically restrict use above a certain scale or add other
conditions. Always read the specific model's license before shipping a
product on top of it; a link is provided for every model below.

### Can you run the best closed models locally?

**No.** The frontier closed models from Anthropic, OpenAI, and Google are
not published as downloadable weights, and there is no legitimate way to
run them outside those providers' own infrastructure. What you *can* do
is run the strongest **open-weight** models, which have closed most of
the practical quality gap for everyday engineering, writing, and
reasoning work -- but a fair comparison still generally favors the
current frontier closed models on the hardest reasoning and long-context
tasks. Judge for your own use case; don't take anyone's marketing claim
(including this page's) at face value -- benchmarks move fast and are
easy to cherry-pick.

---

## Decision matrix

| Option | Privacy | Cost | Setup difficulty | Performance | Best for |
| --- | --- | --- | --- | --- | --- |
| Hosted closed model (API) | Provider sees your data | Pay per token, low upfront | Trivial | Frontier-level | Most products, fastest path to shipping |
| Local small model (laptop/CPU) | Fully private | Free after hardware you already own | Easy (Ollama/LM Studio) | Basic assistant tasks | Drafting, simple Q&A, offline use, learning |
| Local consumer GPU (8-24GB) | Fully private | One-time hardware cost | Moderate | Good 7B-30B-class models | Coding assistants, private chat, iteration |
| Self-hosted server/workstation | Fully private (your infra) | Higher upfront, ongoing power/space | Higher (multi-GPU, serving stack) | Strong, larger models | Small teams, persistent internal tools |
| Rented cloud GPU (hourly) | Depends on provider's policies | Pay per hour, no upfront cost | Moderate (image/template based) | Up to frontier-class open models | Occasional heavy workloads, experimentation, large models |

Treat this as a starting point, not a verdict -- the right column changes
based on how often you actually need the compute.

---

## Recommendations by hardware and budget

### A. No dedicated GPU (laptop, integrated graphics only)

Realistic today: small models in the **1B-4B** parameter range, quantized
(4-bit/`Q4`), run on CPU via [Ollama](https://ollama.com) or
[LM Studio](https://lmstudio.ai). Expect noticeably slower generation than
a hosted API and weaker reasoning than larger models. Good for: drafting,
simple rewriting, offline note-taking assistants, and learning the
tooling before investing in hardware. Not a realistic substitute for a
frontier hosted model on hard tasks.

### B. Consumer GPU

VRAM is the constraint that matters most -- not the GPU's raw compute.
As a rule of thumb for 4-bit (`Q4`) quantized models: **roughly 0.5-0.7 GB
of VRAM per billion parameters**, plus some headroom for context/KV
cache. That rule of thumb is approximate and varies by quantization
scheme and context length -- see
[llama.cpp's quantization docs](https://github.com/ggml-org/llama.cpp)
for specifics.

| VRAM | Realistic model class (Q4) | Notes |
| --- | --- | --- |
| 8 GB | 7B-8B dense models | Comfortable at moderate context; tight above ~8K tokens |
| 12 GB | 8B-14B dense models | Good sweet spot for coding assistants |
| 16 GB | up to ~20B dense, or small MoE (e.g. `gpt-oss-20b`-class) | Solid daily-driver tier |
| 24 GB | up to ~30-34B dense, larger MoE | Best consumer tier for serious local coding work |

### C. Higher-end local workstation (32GB+ system RAM, prosumer/multi-GPU)

Multi-GPU setups (e.g. dual 24GB cards) or a single 48-80GB professional
card open up **70B-class dense models** and larger mixture-of-experts
(MoE) models at usable quantization. This is where you can realistically
run models like `Qwen3` at large sizes or `gpt-oss-120b` (OpenAI states
it runs on a single 80GB GPU). Setup complexity rises: you're usually
moving from Ollama/LM Studio to [vLLM](https://github.com/vllm-project/vllm)
or [llama.cpp](https://github.com/ggml-org/llama.cpp) directly for proper
multi-GPU support and serving throughput.

### D. Mini PCs / compact local setups

Mini PCs with unified memory (e.g. Apple Silicon Mac mini/Studio, or
GPU-equipped mini workstations) can be a genuinely good fit **when your
bottleneck is memory capacity rather than raw throughput** -- Apple
Silicon's unified memory lets a modest-looking machine hold a
surprisingly large quantized model, at the cost of lower tokens/second
than a discrete high-end GPU. They make less sense if you need
high-throughput multi-user serving or training/fine-tuning workloads --
that's better served by a discrete-GPU workstation or a rented instance.

### E. Rent instead of buy

Renting a cloud GPU by the hour makes more sense than buying hardware
when: you need a large model (70B+ dense, or big MoE) only occasionally;
you're experimenting and don't yet know what you need long-term; you want
to avoid the capital cost and depreciation of GPUs that will be obsolete
in 2-3 years; or your workload is bursty (batch jobs, agent runs,
fine-tuning) rather than constant. See the dedicated section below.

---

## Recommended models

Model rankings and exact point releases change every few months --
that's normal and expected. Rather than chase a leaderboard snapshot,
this list favors **model families with stable, official homes** you can
check for the current best release yourself. Verify licenses before
commercial use; links go to the official source.

### Coding

- **Qwen3-Coder** (Alibaba's Qwen team) -- Apache 2.0, actively
  updated family purpose-built for code and agentic coding workflows,
  available from 30B-class MoE up to very large sizes.
  [Official repo](https://github.com/QwenLM) ·
  [Hugging Face](https://huggingface.co/Qwen)
- **DeepSeek-Coder-V2 / DeepSeek-V3** (DeepSeek) -- MIT license on
  recent flagship releases, strong at coding and math, MoE architecture
  with large total parameter counts but a much smaller active-parameter
  footprint per token.
  [Official repo](https://github.com/deepseek-ai) ·
  [Hugging Face](https://huggingface.co/deepseek-ai)
- **gpt-oss-20b / gpt-oss-120b** (OpenAI) -- Apache 2.0, OpenAI's first
  open-weight release since GPT-2. OpenAI states the 20b variant targets
  consumer hardware and the 120b variant runs on a single 80GB GPU.
  [Official announcement](https://openai.com/index/introducing-gpt-oss/) ·
  [GitHub](https://github.com/openai/gpt-oss)

### General reasoning

- **Qwen3 family** (0.6B up to very large MoE sizes) -- Apache 2.0, the
  widest range of sizes of any major open-weight family, making it a
  reasonable default to scale up or down as your hardware changes.
  [Official repo](https://github.com/QwenLM) ·
  [Hugging Face](https://huggingface.co/Qwen)
- **DeepSeek-R1** (and its distilled variants, 1.5B-70B+) -- MIT license
  on the flagship; distilled variants inherit the license of their base
  model (e.g. Qwen/Llama licensed variants). Strong step-by-step
  reasoning performance relative to size.
  [Official repo](https://github.com/deepseek-ai/DeepSeek-R1) ·
  [Hugging Face](https://huggingface.co/deepseek-ai/DeepSeek-R1)
- **Llama family** (Meta) -- Llama Community License, **not** an
  OSI-approved open source license (commercial-use cap around 700M
  monthly active users, plus other conditions) -- read it before shipping
  a product. Large ecosystem of tooling and fine-tunes.
  [Official repo](https://github.com/meta-llama) ·
  [License](https://github.com/meta-llama/llama3/blob/main/LICENSE)

### Lightweight / consumer-hardware-first

- **Ministral 3** (Mistral AI, 3B/8B/14B) -- Apache 2.0, explicitly
  targeted at edge and local deployment (Mistral names RTX PCs, laptops,
  and Jetson devices).
  [Official announcement](https://mistral.ai/news/mistral-3/) ·
  [Hugging Face](https://huggingface.co/mistralai)
- **Gemma 3** (Google, 270M up to 27B) -- Google's own Gemma Terms of Use
  (open-weight, not OSI open source); very wide size range including
  genuinely tiny variants that run on modest hardware.
  [Official docs](https://ai.google.dev/gemma/docs) ·
  [Terms](https://ai.google.dev/gemma/terms)
- **Phi family** (Microsoft, 3.8B-14B) -- MIT license, tuned for strong
  performance relative to parameter count, good fit for constrained
  hardware.
  [Hugging Face](https://huggingface.co/microsoft)

### Larger / server-grade deployment

- **Qwen3 and DeepSeek large MoE variants**, **Mistral Large 3** (Apache
  2.0, sparse MoE, tens of billions of active parameters) -- realistic
  only on multi-GPU workstations or rented instances, not consumer
  single-GPU setups.
  [Mistral Large 3](https://mistral.ai/news/mistral-3/)

---

## Tools, runtimes, and installation paths

| Tool | Best for | License | Link |
| --- | --- | --- | --- |
| [Ollama](https://ollama.com) | Easiest way to get a model running locally with an OpenAI-compatible API | MIT | ollama.com |
| [LM Studio](https://lmstudio.ai) | GUI-first, model browser with hardware-aware quantization suggestions | Free proprietary app (built on open runtimes) | lmstudio.ai |
| [llama.cpp](https://github.com/ggml-org/llama.cpp) | The engine underneath most of the local-AI ecosystem; best for maximum control and unusual hardware (Apple Silicon, CPU-only, etc.) | MIT | github.com/ggml-org/llama.cpp |
| [vLLM](https://github.com/vllm-project/vllm) | Production/multi-user serving on NVIDIA or AMD GPUs, much higher concurrent throughput than the single-user tools above | Apache 2.0 | github.com/vllm-project/vllm |
| [text-generation-webui](https://github.com/oobabooga/textgen) (now "TextGen") | Full-featured local desktop app: chat UI, multiple backends, fine-tuning | AGPL-3.0 | github.com/oobabooga/textgen |

### Quick starts (illustrative -- check each project's own docs for the current install method)

**Ollama** (macOS/Linux/Windows):

```bash
# Install from https://ollama.com/download, then:
ollama run qwen3
```

**llama.cpp** (build from source, works everywhere including CPU-only):

```bash
git clone https://github.com/ggml-org/llama.cpp
cd llama.cpp
cmake -B build
cmake --build build --config Release
```

**vLLM** (Python, NVIDIA/AMD GPU serving):

```bash
pip install vllm
vllm serve <model-name-or-path>
```

These commands are illustrative starting points, not guaranteed to be
exactly current -- always follow the linked project's own install
instructions, which are updated far more often than this page can be.

---

## Renting GPUs instead of buying

Renting makes the most sense for **occasional heavy workloads**:
experimenting with a model class you don't yet own hardware for, running
a large model (70B+ dense or big MoE) for a batch job, agent runs that
spike compute briefly, or fine-tuning -- all without the capital cost of
GPUs that depreciate quickly.

Reputable, commonly used options as of this writing:

- **[RunPod](https://www.runpod.io)** -- on-demand and serverless GPU
  pods, community and "secure" (higher-reliability) tiers at different
  price points.
- **[Lambda](https://lambda.ai)** (Lambda Labs) -- GPU cloud aimed at ML
  workloads, with an uptime SLA and direct human support.
- **[Vast.ai](https://vast.ai)** -- a peer-to-peer GPU marketplace;
  typically the cheapest headline prices, with the tradeoff of variable
  reliability depending on the individual host you rent from.

**On pricing:** hourly GPU rental prices change often and vary a lot by
GPU model, region, and provider tier (and, for marketplaces like Vast.ai,
by which specific host you pick). Rather than freeze numbers here that
will be stale in weeks, check each provider's own pricing page directly
before committing.

Tradeoffs versus buying hardware:

- **Privacy**: your data transits and is processed on the provider's
  infrastructure -- read their specific data-handling policy, this is
  not the same privacy model as fully local hardware.
- **Cost volatility**: hourly rates fluctuate, and marketplace-style
  providers can have interruptible/spot pricing that's cheaper but less
  predictable.
- **Performance**: renting gives you access to hardware classes (e.g.
  80GB+ data-center GPUs) that are impractical to own personally.
- **Persistence**: most rented instances are ephemeral by default --
  plan for where your data and model weights actually live between
  sessions.
- **Setup complexity**: usually template/image-based and faster to get
  running than provisioning physical hardware, but still requires
  comfort with SSH, containers, or the provider's own tooling.

---

## Suggested paths by user type

**If you just want something easy:** install [Ollama](https://ollama.com)
and run a mid-size model from the Qwen3 or Llama family. Minutes to
working, no GPU required (though one helps a lot with speed).

**If you want the cheapest local option:** a small quantized model
(Gemma 3 or Qwen3 in the 1B-4B range) via Ollama or llama.cpp on hardware
you already own.

**If you want the best coding performance under a reasonable budget:** a
consumer GPU with 16-24GB VRAM running a Qwen3-Coder or gpt-oss-20b class
model via Ollama, LM Studio, or llama.cpp directly.

**If you want stronger privacy with minimal hardware investment:** a
small model (Gemma 3, Phi, or Ministral 3) on a laptop CPU or modest GPU
-- fully local, no rented infrastructure involved at all.

**If you need bigger models but don't want to buy a GPU:** rent one --
start with [RunPod](https://www.runpod.io) or [Vast.ai](https://vast.ai)
for occasional use, or [Lambda](https://lambda.ai) if reliability and
support matter more to you than the lowest hourly rate.

---

## What this page does not claim

- Running locally does **not** automatically mean "no watermark" in every
  possible setup. It removes your dependence on a hosted provider's
  generation pipeline -- but the actual result still depends on your
  specific software stack, model, workflow, and output format. Verify
  your own output the way GhostMark's main tool does: inspect it.
- The current frontier **closed** models from Anthropic, OpenAI, and
  Google are generally **not** available to run locally at all -- only
  their providers' own infrastructure runs them.
- Model compatibility, tooling, and rankings change **quickly**. Treat
  every specific model/tool named on this page as a reasonable starting
  point to verify yourself, not a permanent recommendation.
- Hardware economics (GPU prices, VRAM-per-dollar, rental rates) change
  quickly too -- this page intentionally avoids freezing numbers that
  would go stale within weeks.
- Running your own stack still requires trust in *that* stack -- your
  OS, your inference engine, any library you install, and any service
  you rent from. "Local" reduces your dependence on one specific hosted
  provider; it does not eliminate every trust question.
- This page does not cover fine-tuning, RAG, or agent-framework choices
  in depth -- it's scoped to "how do I get a capable open-weight model
  running at all."

---

## Sources

- [C2PA -- Coalition for Content Provenance and Authenticity](https://c2pa.org/)
- [Open Source Initiative](https://opensource.org/)
- [Qwen (QwenLM) official GitHub](https://github.com/QwenLM)
- [DeepSeek official GitHub](https://github.com/deepseek-ai)
- [DeepSeek-R1 license FAQ](https://deepseeklicense.github.io/)
- [Meta Llama 3 license](https://github.com/meta-llama/llama3/blob/main/LICENSE)
- [Mistral AI -- Introducing Mistral 3](https://mistral.ai/news/mistral-3/)
- [Google Gemma documentation](https://ai.google.dev/gemma/docs) and [Gemma Terms of Use](https://ai.google.dev/gemma/terms)
- [OpenAI -- Introducing gpt-oss](https://openai.com/index/introducing-gpt-oss/)
- [Ollama model library](https://ollama.com/library)
- [llama.cpp](https://github.com/ggml-org/llama.cpp)
- [vLLM](https://github.com/vllm-project/vllm)
- [LM Studio](https://lmstudio.ai)
- [text-generation-webui / TextGen](https://github.com/oobabooga/textgen)
- [RunPod](https://www.runpod.io), [Lambda](https://lambda.ai), [Vast.ai](https://vast.ai)

## Is something outdated or inaccurate?

This page covers a fast-moving ecosystem and we'd rather correct it than
leave it stale. [Open an issue](https://github.com/bens777/ghostmark/issues)
or submit a pull request against
[`src/ghostmark/web/content/run_local.md`](https://github.com/bens777/ghostmark/blob/main/src/ghostmark/web/content/run_local.md)
on GitHub.

**Last reviewed:** 2026-08-13
