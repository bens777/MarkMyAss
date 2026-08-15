"""Tests for corpus helpers (no network / no ML stack required)."""

from inverse_study import corpus


def test_trim_to_sentence_caps_length():
    text = "One two three four five. " * 20  # 100 words, sentences every 5 words
    out = corpus._trim_to_sentence(text, 23)
    assert len(out.split()) <= 23
    assert out.rstrip().endswith(".")  # trimmed at a sentence boundary


def test_trim_noop_when_short():
    text = "Short sentence here."
    assert corpus._trim_to_sentence(text, 100) == text


def test_paragraph_filter():
    good = " ".join(["word"] * 60) + "."
    junk_short = "too short"
    junk_caps = " ".join(["WORD"] * 60)
    junk_marker = "This paragraph mentions Project Gutenberg " + " ".join(["x"] * 60)
    body = "\n\n".join([good, junk_short, junk_caps, junk_marker])
    paras = corpus._paragraphs(body)
    assert good in paras
    assert junk_short not in paras
    assert junk_caps not in paras


def test_works_are_pinned_public_domain():
    assert len(corpus.WORKS) >= 5
    assert all(w["year"] < 1929 for w in corpus.WORKS)
