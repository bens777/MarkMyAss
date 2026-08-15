"""Official SynthID-Text generation + tuning-free Weighted-Mean detector.

Thin wrapper over the DeepMind SynthID-Text implementation shipped in
`transformers` (`SynthIDTextWatermarkingConfig` +
`SynthIDTextWatermarkLogitsProcessor`). Uses OUR OWN local keys.

The Weighted-Mean detector is the tuning-free detector: it averages the
official g-values over the valid (non-repeated-context, non-eos) positions.
Un-watermarked text sits near the coin-flip mean; watermarked text is elevated.
No trained Bayesian detector is used (that would need labelled training data).
"""

from __future__ import annotations

from dataclasses import dataclass

import torch
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    SynthIDTextWatermarkingConfig,
)


@dataclass
class WatermarkParams:
    keys: list[int]
    ngram_len: int = 5
    sampling_table_size: int = 65536
    sampling_table_seed: int = 0
    context_history_size: int = 1024


@dataclass
class GenParams:
    max_new_tokens: int = 160
    temperature: float = 1.0
    top_k: int = 40
    top_p: float = 1.0


class Engine:
    """Loads a small causal LM and exposes generation, scoring, and embedding."""

    def __init__(
        self,
        model_name: str,
        wm: WatermarkParams,
        gen: GenParams,
        cache_dir: str | None = None,
        device: str = "cpu",
    ) -> None:
        self.model_name = model_name
        self.device = torch.device(device)
        self.tokenizer = AutoTokenizer.from_pretrained(model_name, cache_dir=cache_dir)
        if self.tokenizer.pad_token_id is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        self.model = AutoModelForCausalLM.from_pretrained(model_name, cache_dir=cache_dir)
        self.model.to(self.device)
        self.model.eval()
        self.gen = gen
        self.wm = wm
        self.vocab_size = int(self.model.config.vocab_size)
        self.eos_token_id = int(self.tokenizer.eos_token_id)

        self.wm_config = SynthIDTextWatermarkingConfig(
            ngram_len=wm.ngram_len,
            keys=wm.keys,
            sampling_table_size=wm.sampling_table_size,
            sampling_table_seed=wm.sampling_table_seed,
            context_history_size=wm.context_history_size,
        )
        self.processor = self.wm_config.construct_processor(self.vocab_size, self.device)

    # -- generation -----------------------------------------------------------
    @torch.no_grad()
    def generate(self, prompt: str, watermarked: bool, seed: int) -> list[int]:
        """Return the newly generated token ids (prompt excluded), fixed length."""
        torch.manual_seed(seed)
        enc = self.tokenizer(prompt, return_tensors="pt").to(self.device)
        n_new = self.gen.max_new_tokens
        kwargs = dict(
            do_sample=True,
            temperature=self.gen.temperature,
            top_k=self.gen.top_k,
            top_p=self.gen.top_p,
            max_new_tokens=n_new,
            min_new_tokens=n_new,  # force equal length so mixtures align
            pad_token_id=self.tokenizer.pad_token_id,
        )
        if watermarked:
            kwargs["watermarking_config"] = self.wm_config
        out = self.model.generate(**enc, **kwargs)
        new_ids = out[0, enc["input_ids"].shape[1] :]
        return new_ids.tolist()

    # -- detection ------------------------------------------------------------
    @torch.no_grad()
    def weighted_mean_score(self, token_ids: list[int]) -> tuple[float, int]:
        """Tuning-free Weighted-Mean detector score and the number of scored positions.

        Score is the mean official g-value over valid positions (contexts that
        are non-repeated and non-eos), averaged across the key depth.
        """
        if len(token_ids) <= self.wm.ngram_len:
            return float("nan"), 0
        ids = torch.tensor([token_ids], dtype=torch.long, device=self.device)
        g_values = self.processor.compute_g_values(ids)  # (1, L, depth) int
        crm = self.processor.compute_context_repetition_mask(ids)  # (1, L) bool
        eos = self.processor.compute_eos_token_mask(ids, self.eos_token_id)  # (1, S) bool
        # eos mask is full length; align to g_values by dropping the ngram warm-up.
        eos_aligned = eos[:, self.wm.ngram_len - 1 :]
        mask = crm & eos_aligned  # (1, L) bool
        n_scored = int(mask.sum().item())
        if n_scored == 0:
            return float("nan"), 0
        m = mask.unsqueeze(-1).expand_as(g_values)
        total = g_values[m].float().sum().item()
        count = int(m.sum().item())
        return total / count, n_scored

    # -- embedding ------------------------------------------------------------
    @torch.no_grad()
    def embed(self, token_ids: list[int]) -> list[float]:
        """Mean-pooled last-hidden-state embedding (documented proxy for semantics)."""
        if not token_ids:
            return [0.0] * int(self.model.config.hidden_size)
        ids = torch.tensor([token_ids], dtype=torch.long, device=self.device)
        out = self.model(input_ids=ids, output_hidden_states=True)
        vec = out.hidden_states[-1][0].mean(dim=0)
        return vec.tolist()

    def decode(self, token_ids: list[int]) -> str:
        return self.tokenizer.decode(token_ids, skip_special_tokens=True)
