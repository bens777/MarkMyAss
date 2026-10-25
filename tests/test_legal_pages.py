"""/legal (legal notice + terms of sale) and /privacy (privacy policy).

Two plain bilingual pages on the site's single i18n system (i18n.js
resolver, shared i18n-fr.js dictionary, i18n-apply.js, FR | EN switcher,
`markmyass-language` preference), linked from the footer of every public
page. They change nothing about the free tool or the paid batch.

Three layers, like tests/test_batch_upsell.py:

1. Static checks (always run): exact legal facts, every marker translated,
   wording of both languages, footer links in every page template.
2. Server checks (always run): both pages 200, links on every public page,
   no Stripe secret exposed, free flow and batch untouched.
3. Browser checks (skipped without Playwright + its Chromium): language from
   the browser, remembered preference, the switcher, mobile readability.
"""

from __future__ import annotations

import io
import re
import socket
import threading
import time
from html import unescape
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from ghostmark.web.app import INDEXABLE_PAGES, create_app
from ghostmark.web.config import WebConfig

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src" / "ghostmark" / "web" / "static"
LEGAL_HTML = (STATIC / "legal.html").read_text(encoding="utf-8")
PRIVACY_HTML = (STATIC / "privacy.html").read_text(encoding="utf-8")
INDEX_HTML = (STATIC / "index.html").read_text(encoding="utf-8")
BATCH_HTML = (STATIC / "batch.html").read_text(encoding="utf-8")
I18N_FR_SRC = (STATIC / "i18n-fr.js").read_text(encoding="utf-8")
APP_PY = (ROOT / "src" / "ghostmark" / "web" / "app.py").read_text(encoding="utf-8")
CONTENT_RENDER_PY = (ROOT / "src" / "ghostmark" / "web" / "content_render.py").read_text(encoding="utf-8")

SIREN = "915 385 124"
ADDRESS_LINES = ("66 Avenue des Champs-Élysées", "75008 Paris", "France")
LEGAL_TITLE_FR = "Mentions légales et conditions générales de vente"
LEGAL_TITLE_EN = "Legal notice and terms of sale"
PRIVACY_TITLE_FR = "Politique de confidentialité"
PRIVACY_TITLE_EN = "Privacy Policy"
WITHDRAWAL_FR = "En commandant, le client demande l'exécution immédiate du service numérique et reconnaît perdre son droit de rétractation dès que le traitement du lot a commencé."
WITHDRAWAL_EN = "By ordering, the customer requests immediate performance of the digital service and acknowledges that the right of withdrawal is lost once batch processing has begun."
REFUND_FR = (
    "En cas d'échec technique imputable à MarkMyAss empêchant la fourniture d'un résultat exploitable, le client peut "
    "demander un remboursement en contactant le support. Aucun remboursement n'est dû après la fourniture réussie du "
    "fichier ZIP ou lorsque le paiement expire sans utilisation par le client, sous réserve des droits légaux applicables."
)
FOOTER_FR = {"footer.legal": "Mentions légales &amp; CGV", "footer.privacy": "Confidentialité"}
FOOTER_EN = {"legal": "Legal &amp; Terms", "privacy": "Privacy"}


def _fr_dict() -> dict[str, str]:
    block = I18N_FR_SRC[I18N_FR_SRC.index("var dict = {"): I18N_FR_SRC.index("var reprocessProfilesFr")]
    return dict(re.findall(r'"([\w.]+)"\s*:\s*"((?:[^"\\]|\\.)*)"', block))


def _markers(html: str) -> dict[str, str]:
    """data-i18n key -> English inner HTML; attribute keys map to ''."""

    out = {}
    for m in re.finditer(r'<(\w+)[^>]*\sdata-i18n="([^"]+)"[^>]*>(.*?)</\1>', html, re.S):
        out[m.group(2)] = m.group(3).strip()
    for spec in re.findall(r'data-i18n-attr="([^"]+)"', html):
        for pair in spec.split(";"):
            if ":" in pair:
                out[pair.split(":", 1)[1].strip()] = ""
    return out


def _strip(html: str) -> str:
    return unescape(re.sub(r"<[^>]+>", "", html)).strip()


def _config(tmp_path=None, *, batch=False) -> WebConfig:
    kw = dict(
        mode="hosted", base_path="/", public_url="https://markmyass.test", session_ttl_seconds=600,
        rate_limit_per_minute=1000, max_concurrent_jobs=4, processing_timeout_seconds=30, max_upload_mb=10,
    )
    if tmp_path is not None:
        kw["stats_db_path"] = str(tmp_path / "stats.db")
    if batch:
        kw.update(batch_enabled=True, commerce_db_path=str(tmp_path / "commerce.db"), stripe_secret_key="sk_test_SECRET", stripe_price_id="price_SECRET")
    return WebConfig(**kw)


class _Gateway:
    def create_checkout_session(self, **kwargs):
        return "https://checkout.stripe.test/session"

    def retrieve_session(self, session_id):
        return None


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), color=(4, 5, 6)).save(buf, format="PNG")
    return buf.getvalue()


# --- 1. static: the exact legal facts ------------------------------------------------------------


@pytest.mark.parametrize("html", [LEGAL_HTML, PRIVACY_HTML], ids=["legal", "privacy"])
def test_pages_carry_the_exact_identity_siren_rcs_and_address(html):
    fr = _fr_dict()
    assert "Benoit Sartre" in html
    assert html.count(SIREN) >= 2  # SIREN and RCS
    assert f"<strong>SIREN:</strong> {SIREN}" in html and f"<strong>RCS:</strong> Paris {SIREN}" in html
    for line in ADDRESS_LINES:
        assert line in html
    # The address block is literal (identical in both languages): one block, lines in order.
    block = re.search(r'<address class="legal-address">(.*?)</address>', html, re.S).group(1)
    assert block.split("\n") == list(ADDRESS_LINES)
    assert "entrepreneur individuel" in html and "EI" in html
    # The French carries the same identifiers.
    page = "legal" if html is LEGAL_HTML else "privacy"
    assert f"<strong>SIREN :</strong> {SIREN} · <strong>RCS :</strong> Paris {SIREN}" == fr[f"{page}.s1.ids"]
    assert "Monsieur Benoit Sartre" in fr[f"{page}.s1.{'publisher' if page == 'legal' else 'who'}"]
    assert "entrepreneur individuel (EI)" in fr[f"{page}.s1.{'publisher' if page == 'legal' else 'who'}"]


def test_legal_notice_facts():
    fr = _fr_dict()
    assert "registered with the Paris Trade and Companies Register (RCS) under number 915 385 124" in LEGAL_HTML
    assert "immatriculé au Registre du commerce et des sociétés de Paris sous le numéro 915 385 124" in fr["legal.s1.publisher"]
    assert "<strong>Publication director:</strong> Mr Benoit Sartre" in LEGAL_HTML
    assert fr["legal.s1.director"] == "<strong>Directeur de la publication :</strong> Monsieur Benoit Sartre"
    # Hosting provider: name only (no address exists in the project, none invented).
    assert "<strong>Hosting provider:</strong> Hetzner Online GmbH." in LEGAL_HTML
    assert fr["legal.s1.host"] == "<strong>Hébergeur :</strong> Hetzner Online GmbH."
    assert not re.search(r"Gunzenhausen|Industriestr|91710", LEGAL_HTML + I18N_FR_SRC)
    # Contact e-mail: none exists in the project, so it is an explicit placeholder, never an invented address.
    assert "<strong>Contact e-mail:</strong> to be completed" in LEGAL_HTML
    assert fr["legal.s1.contact"].startswith("<strong>Adresse e-mail de contact :</strong> à compléter")
    assert "@" not in _strip(LEGAL_HTML.split("<body>")[1]) and "mailto:" not in LEGAL_HTML
    # Consumer mediator: explicit placeholder, none invented.
    assert "Consumer mediator: to be completed." in LEGAL_HTML
    assert fr["legal.s5.i3"] == "Médiateur de la consommation : à compléter."


def test_terms_of_sale_state_the_offer_exactly():
    fr = _fr_dict()
    en = _markers(LEGAL_HTML)
    expected_fr = {
        "legal.s2.i1": "MarkMyAss propose un outil gratuit de traitement individuel et une option payante de traitement par lot.",
        "legal.s2.i2": "L'offre payante permet de traiter un seul lot de 2 à 50 images ou PDF.",
        "legal.s2.i3": "Prix : 1,99 € TTC.",
        "legal.s2.i4": "Paiement unique, sans compte et sans abonnement.",
        "legal.s2.i5": "Paiement sécurisé traité par Stripe.",
        "legal.s2.i6": "Limites : 10 Mo par fichier et 64 Mo par lot.",
        "legal.s2.i7": "Après confirmation du paiement, le client dispose de 24 heures pour traiter et finaliser son lot.",
        "legal.s2.i8": "Une fois créé, le fichier ZIP reste téléchargeable pendant 1 heure.",
        "legal.s2.i9": "Un paiement correspond à un seul lot finalisé.",
        "legal.s2.i10": "Les fichiers temporaires peuvent être supprimés avant la fin des 24 heures. Dans ce cas, le client peut les sélectionner à nouveau tant que son paiement reste valide.",
        "legal.s2.i11": "MarkMyAss retire les métadonnées et les éléments techniques pris en charge.",
        "legal.s2.i12": "MarkMyAss ne garantit pas la suppression des filigranes visibles ou des filigranes statistiques tels que SynthID.",
        "legal.s2.i13": "Les résultats peuvent être signalés comme vérifiés, incomplets ou en échec selon les outils de vérification disponibles.",
    }
    for key, value in expected_fr.items():
        assert fr[key] == value, key
        assert en[key], key
    assert "€1.99 including VAT" in en["legal.s2.i3"] and "2 to 50 images or PDFs" in en["legal.s2.i2"]
    assert "10 MB per file and 64 MB per batch" in en["legal.s2.i6"] and "24 hours" in en["legal.s2.i7"] and "1 hour" in en["legal.s2.i8"]
    # The withdrawal clause and the refund clause, word for word, in both languages.
    assert _strip(en["legal.s2.withdrawal"]).endswith(WITHDRAWAL_EN)
    assert _strip(fr["legal.s2.withdrawal"]).endswith(WITHDRAWAL_FR)
    assert fr["legal.s3.p1"] == REFUND_FR
    assert "technical failure attributable to MarkMyAss" in en["legal.s3.p1"] and "subject to applicable statutory rights" in en["legal.s3.p1"]
    # Liability and governing law.
    for key, needle in (("legal.s4.i1", "necessary rights"), ("legal.s4.i2", "cannot be detected"), ("legal.s4.i3", "illegal or unauthorised use"), ("legal.s4.i4", "French law"), ("legal.s5.i1", "French law"), ("legal.s5.i2", "applicable legal rules")):
        assert needle in en[key], key
    assert fr["legal.s5.i1"] == "Droit applicable : droit français." and "loi française" in fr["legal.s4.i4"]


def test_privacy_policy_describes_what_the_code_really_does():
    fr = _fr_dict()
    en = _markers(PRIVACY_HTML)
    # Files: purpose, temporary, automatic deletion, one hour for batch, no AI training / ads / profiling.
    assert "only to provide the service" in en["privacy.s2.i1"] and "deleted automatically" in en["privacy.s2.i3"]
    assert "one hour at most" in en["privacy.s2.i4"] and "advertising, profiling or training" in en["privacy.s2.i5"]
    assert "une durée maximale d'une heure" in fr["privacy.s2.i4"]
    # Batch data: exactly the commerce DB's columns, nothing else.
    assert [en[f"privacy.s3.i{i}"] for i in range(1, 5)] == [
        "the Stripe Checkout Session identifier;", "the status of the batch (paid, processing, finalized);",
        "the payment date, as reported by Stripe;", "the technical creation and finalization timestamps.",
    ]
    assert "No file name, no uploaded content" in en["privacy.s3.p2"] and "Aucun nom de fichier, aucun contenu téléversé" in fr["privacy.s3.p2"]
    # Stripe: official policy link in both languages.
    assert 'href="https://stripe.com/privacy"' in PRIVACY_HTML and "https://stripe.com/fr/privacy" in fr["privacy.s4.i3"]
    assert "never receives or stores full card numbers" in en["privacy.s4.i2"]
    # Statistics: what stats.py stores (lifetime counter + 24h timestamps), nothing identifying.
    assert "lifetime count of files cleaned" in en["privacy.s5.p1"] and "timestamp kept for 24 hours" in en["privacy.s5.p1"]
    assert "no IP address and no identifier" in en["privacy.s5.p2"]
    # GDPR rights + CNIL link.
    for right in ("access", "rectify", "erase", "restrict", "object", "portability"):
        assert right in en["privacy.s7.p1"], right
    for right in ("accès", "rectification", "effacement", "limitation", "opposition", "portabilité"):
        assert right in fr["privacy.s7.p1"], right
    assert 'href="https://www.cnil.fr/"' in PRIVACY_HTML and "https://www.cnil.fr/" in fr["privacy.s7.p2"]
    # Cookies: none set by the site; local storage for theme + language only (what theme-init.js / i18n.js do).
    assert "sets no cookies" in en["privacy.s8.p1"] and "markmyass-theme" in en["privacy.s8.p1"] and "markmyass-language" in en["privacy.s8.p1"]
    assert "ne dépose aucun cookie" in fr["privacy.s8.p1"]
    assert "cookie-banner" not in INDEX_HTML.lower() and "consent" not in INDEX_HTML.lower()


def test_site_really_sets_no_cookies_and_uses_only_the_two_storage_keys():
    """The privacy page's cookie statement must match the shipped JavaScript."""

    js = "".join(p.read_text(encoding="utf-8") for p in STATIC.glob("*.js"))
    py = "".join(p.read_text(encoding="utf-8") for p in (ROOT / "src" / "ghostmark" / "web").glob("*.py"))
    assert "document.cookie" not in js and "set_cookie" not in py and "Set-Cookie" not in py
    assert set(re.findall(r'localStorage\.(?:getItem|setItem)\(\s*"([^"]+)"', js)) == {"markmyass-theme"}
    assert 'STORAGE_KEY = "markmyass-language"' in js
    assert "sessionStorage" not in js


# --- 1b. static: full bilingual coverage and the footers -----------------------------------------


@pytest.mark.parametrize(("html", "prefix"), [(LEGAL_HTML, "legal."), (PRIVACY_HTML, "privacy.")], ids=["legal", "privacy"])
def test_every_visible_text_is_marked_and_translated(html, prefix):
    fr = _fr_dict()
    markers = _markers(html)
    assert len(markers) >= 40
    missing = sorted(k for k in markers if k not in fr)
    assert not missing, f"French missing for: {missing}"
    for key, en in markers.items():
        if not en:
            continue
        assert _strip(fr[key]), key
        if key not in (f"{prefix}s1.ids",):  # identical identifiers are expected
            assert _strip(fr[key]) != _strip(en), f"{key}: French equals English"
        # Links survive translation: same number, same hosts (the French may
        # point at a localized page of the same site, e.g. stripe.com/fr/privacy).
        hrefs_en, hrefs_fr = re.findall(r"href=.([^'\"]+)", en), re.findall(r"href=.([^'\"]+)", fr[key])
        host = lambda u: re.sub(r"^https?://([^/]+).*$", r"\1", u)  # noqa: E731
        assert sorted(map(host, hrefs_en)) == sorted(map(host, hrefs_fr)), key
    # Every text-bearing element in the article is marked (no untranslatable paragraph).
    article = html.split('<article class="article legal-page">')[1].split("</article>")[0]
    for tag in re.findall(r"<(p|h1|h2|li)\b([^>]*)>", article):
        assert 'data-i18n="' in tag[1], f"<{tag[0]}{tag[1]}> has no data-i18n marker"
    assert '<title data-i18n="' in html and 'data-i18n-attr="content:' in html
    # No French in the English source, no English left in the French.
    body = _strip(html.split("<body>")[1]).lower()
    for word in (" vos ", " fichiers", " paiement", "téléch", "responsable du traitement"):
        assert word not in body, word
    for key in markers:
        if key.startswith(prefix):
            value = _strip(fr[key]).lower()
            for word in (" your ", " files ", "payment ", "the customer", "privacy policy"):
                assert word not in value, f"{key}: English left in French ({word!r})"


def test_pages_use_the_site_locale_engine_and_switcher():
    for html in (LEGAL_HTML, PRIVACY_HTML):
        assert html.startswith('<!doctype html>\n<html lang="en-US">')
        head = html.split("</head>")[0]
        assert 'src="static/theme-init.js"' in head and 'src="static/i18n.js"' in head
        body = html.split("<body>")[1]
        assert body.index('src="static/i18n-fr.js"') < body.index('src="static/i18n-apply.js"')
        assert 'data-lang-set="fr-FR"' in html and 'data-lang-set="en-US"' in html and html.count("data-lang-set=") == 2
        # No page script of its own, no second translation mechanism.
        assert "<script>" not in html and html.count("<script ") == 4
        assert 'href="."' in html  # brand link home
    assert LEGAL_HTML.count('<title data-i18n="legal.meta.title">') == 1
    assert PRIVACY_HTML.count('<title data-i18n="privacy.meta.title">') == 1
    fr = _fr_dict()
    assert fr["legal.h1"] == LEGAL_TITLE_FR and fr["privacy.h1"] == PRIVACY_TITLE_FR
    assert f"<h1 data-i18n=\"legal.h1\">{LEGAL_TITLE_EN}</h1>" in LEGAL_HTML
    assert f"<h1 data-i18n=\"privacy.h1\">{PRIVACY_TITLE_EN}</h1>" in PRIVACY_HTML
    assert fr["legal.meta.title"].startswith(LEGAL_TITLE_FR) and fr["privacy.meta.title"].startswith(PRIVACY_TITLE_FR)


def test_footer_links_exist_in_every_page_template():
    fr = _fr_dict()
    for key, value in FOOTER_FR.items():
        assert fr[key] == value
    localized = (
        '<a href="legal" data-i18n="footer.legal">Legal &amp; Terms</a>',
        '<a href="privacy" data-i18n="footer.privacy">Privacy</a>',
    )
    for html in (INDEX_HTML, BATCH_HTML, LEGAL_HTML, PRIVACY_HTML):
        footer = html.split("<footer>")[1]
        for snippet in localized:
            assert snippet in footer, snippet
        assert 'data-i18n-attr="aria-label:footer.legal.aria"' in footer
    # English-only article pages (lab, benchmarks, SEO landing pages...) and the 404 page.
    english = '<a href="legal">Legal &amp; Terms</a><a href="privacy">Privacy</a>'
    assert english in CONTENT_RENDER_PY and english in APP_PY
    # Relative hrefs only (base-href convention), so /legal and /privacy stay right under a subpath.
    for html in (INDEX_HTML, BATCH_HTML, LEGAL_HTML, PRIVACY_HTML):
        assert 'href="/legal"' not in html and 'href="/privacy"' not in html


# --- 2. server --------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app(_config()))


def test_legal_and_privacy_return_200_with_canonical_and_description(client):
    for path, title in (("/legal", LEGAL_TITLE_EN), ("/privacy", PRIVACY_TITLE_EN)):
        resp = client.get(path)
        assert resp.status_code == 200 and resp.headers["content-type"].startswith("text/html")
        html = resp.text
        assert f">{title} | MarkMyAss</title>" in html or f">{title}</h1>" in html
        assert f'rel="canonical" href="https://markmyass.test{path}"' in html
        assert "{{" not in html  # every placeholder rendered
        assert '<base href="/">' in html
        assert 'content="index, follow"' in html
        assert SIREN in html and all(line in html for line in ADDRESS_LINES)


def test_footer_links_are_served_on_every_public_page(client):
    pages = [*INDEXABLE_PAGES, "/legal", "/privacy"]
    for path in pages:
        html = client.get(path).text
        footer = html.split("<footer>")[1]
        assert 'href="legal"' in footer and 'href="privacy"' in footer, path
        assert "Legal &amp; Terms" in footer and "Privacy" in footer, path
    # The 404 page too.
    html = client.get("/no-such-page", headers={"accept": "text/html"}).text
    assert 'href="legal"' in html and 'href="privacy"' in html
    # Each link target is the page itself.
    assert client.get("/legal").status_code == 200 and client.get("/privacy").status_code == 200


def test_pages_work_under_a_subpath():
    cfg = WebConfig(
        mode="hosted", base_path="/ghostmark/", public_url="https://example.test/ghostmark", session_ttl_seconds=600,
        rate_limit_per_minute=1000, max_concurrent_jobs=4, processing_timeout_seconds=30, max_upload_mb=10,
    )
    with TestClient(create_app(cfg)) as c:
        for path in ("/legal", "/privacy"):
            html = c.get(path).text
            assert '<base href="/ghostmark/">' in html
            assert f'rel="canonical" href="https://example.test/ghostmark{path}"' in html
            stripped = re.sub(r"<base[^>]*>", "", html)
            for m in re.finditer(r'(?:href|src)="([^"]*)"', stripped):
                v = m.group(1)
                if not v.startswith(("http://", "https://", "#")):
                    assert not v.startswith("/"), v


def test_no_stripe_secret_or_price_id_on_the_pages(tmp_path, monkeypatch):
    monkeypatch.setattr("ghostmark.web.batch.tempfile.gettempdir", lambda: str(tmp_path))
    with TestClient(create_app(_config(tmp_path, batch=True), batch_gateway=_Gateway())) as c:
        text = c.get("/legal").text + c.get("/privacy").text + c.get("/").text + c.get("/batch").text
        assert "sk_test" not in text and "SECRET" not in text and "price_" not in text
        assert "stripe_secret" not in text.lower()
    assert "sk_" not in LEGAL_HTML + PRIVACY_HTML + I18N_FR_SRC


def test_free_flow_and_batch_are_untouched(tmp_path, monkeypatch):
    monkeypatch.setattr("ghostmark.web.batch.tempfile.gettempdir", lambda: str(tmp_path))
    with TestClient(create_app(_config(tmp_path, batch=True), batch_gateway=_Gateway())) as c:
        # Free single-file flow.
        resp = c.post("/api/inspect/file", files={"file": ("photo.png", _png(), "image/png")})
        assert resp.status_code == 200
        sid = resp.json()["session_id"]
        assert c.post(f"/api/clean/{sid}").status_code == 200
        assert c.post(f"/api/verify/{sid}").status_code == 200
        assert c.get(f"/api/download/{sid}").status_code == 200
        assert c.post("/api/inspect/text", json={"text": "hello"}).status_code == 200
        # Batch: same offer, same page, same payment checks.
        assert c.get("/api/batch/offer").json() == {
            "price_cents": 199, "currency": "eur", "min_files": 2, "max_files": 50, "max_upload_mb": 10, "max_total_mb": 64,
            "window_hours": 24, "zip_hours": 1,
        }
        assert c.get("/batch").status_code == 200
        assert c.post("/api/batch/verify", json={"session_id": "cs_nope"}).status_code == 402
        assert c.get("/api/config").json()["batch_enabled"] is True
    # Feature off: the legal pages are still there, the batch is not.
    with TestClient(create_app(_config(tmp_path))) as c:
        assert c.get("/legal").status_code == 200 and c.get("/privacy").status_code == 200
        assert c.get("/batch").status_code == 404
        assert c.get("/api/config").json()["batch_enabled"] is False


# --- 3. browser (isolated Playwright Chromium, never the user's browser) ------------------------

try:  # pragma: no cover - availability differs per machine
    import uvicorn
    from playwright.sync_api import Error as _PWError
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover
    sync_playwright = None

_needs_browser = pytest.mark.skipif(sync_playwright is None, reason="Playwright (and uvicorn) not installed")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def server():
    if sync_playwright is None:
        pytest.skip("Playwright not installed")
    port = _free_port()
    srv = uvicorn.Server(uvicorn.Config(create_app(_config()), host="127.0.0.1", port=port, log_level="warning"))
    th = threading.Thread(target=srv.run, daemon=True)
    th.start()
    deadline = time.time() + 15
    while not srv.started:
        assert time.time() < deadline, "uvicorn did not start"
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}/"
    srv.should_exit = True
    th.join(timeout=10)


@pytest.fixture(scope="module")
def browser():
    if sync_playwright is None:
        pytest.skip("Playwright not installed")
    with sync_playwright() as p:
        try:
            b = p.chromium.launch()  # isolated, project-owned instance
        except _PWError as exc:
            pytest.skip(f"Playwright Chromium unavailable: {exc.message.splitlines()[0]}")
        yield b
        b.close()  # closes ONLY this instance


def _open(browser, url, *, locale, width=1400, saved=None):
    ctx = browser.new_context(locale=locale, viewport={"width": width, "height": 900}, color_scheme="light")
    if saved:
        ctx.add_init_script(f'try {{ localStorage.setItem("markmyass-language", "{saved}"); }} catch (e) {{}}')
    page = ctx.new_page()
    page.goto(url)
    page.wait_for_function("() => !document.documentElement.hasAttribute('data-i18n-pending')")
    return ctx, page


@_needs_browser
@pytest.mark.parametrize("path", ["legal", "privacy"])
@pytest.mark.parametrize(
    ("locale", "saved", "lang"),
    [("fr-FR", None, "fr"), ("fr-CA", None, "fr"), ("en-US", None, "en"), ("de-DE", None, "en"), ("en-US", "fr-FR", "fr"), ("fr-FR", "en-US", "en")],
)
def test_browser_language_and_remembered_preference(server, browser, path, locale, saved, lang):
    ctx, page = _open(browser, server + path, locale=locale, saved=saved)
    try:
        titles = {"legal": (LEGAL_TITLE_EN, LEGAL_TITLE_FR), "privacy": (PRIVACY_TITLE_EN, PRIVACY_TITLE_FR)}[path]
        expected = titles[1] if lang == "fr" else titles[0]
        assert page.locator("h1").inner_text().strip() == expected
        assert page.evaluate("() => document.documentElement.lang") == ("fr-FR" if lang == "fr" else "en-US")
        assert page.title().startswith(expected)
        # Essential facts in the active language.
        body = page.locator("article").inner_text()
        assert SIREN in body and "66 Avenue des Champs-Élysées" in body and "75008 Paris" in body
        if path == "legal":
            assert (WITHDRAWAL_FR if lang == "fr" else WITHDRAWAL_EN) in body
        else:
            assert ("ne dépose aucun cookie" if lang == "fr" else "sets no cookies") in body
        # Footer links, translated, pointing at /legal and /privacy.
        links = page.locator("footer .footer-legal a")
        assert links.count() == 2
        assert [links.nth(i).inner_text().strip() for i in range(2)] == (
            ["Mentions légales & CGV", "Confidentialité"] if lang == "fr" else ["Legal & Terms", "Privacy"]
        )
        assert [links.nth(i).evaluate("a => new URL(a.href).pathname") for i in range(2)] == ["/legal", "/privacy"]
        # The switcher shows the active language.
        active = page.locator(".lang-option.active").inner_text().strip()
        assert active == ("FR" if lang == "fr" else "EN")
    finally:
        ctx.close()


@_needs_browser
def test_switcher_changes_language_and_remembers_it_across_pages(server, browser):
    ctx, page = _open(browser, server + "legal", locale="en-US")
    try:
        assert page.locator("h1").inner_text().strip() == LEGAL_TITLE_EN
        page.locator('[data-lang-set="fr-FR"]').click()
        page.wait_for_function("() => document.documentElement.lang === 'fr-FR'")
        page.wait_for_function("() => !document.documentElement.hasAttribute('data-i18n-pending')")
        assert page.locator("h1").inner_text().strip() == LEGAL_TITLE_FR
        assert page.evaluate("() => localStorage.getItem('markmyass-language')") == "fr-FR"
        # The preference follows to the other page and the homepage footer.
        page.goto(server + "privacy")
        page.wait_for_function("() => !document.documentElement.hasAttribute('data-i18n-pending')")
        assert page.locator("h1").inner_text().strip() == PRIVACY_TITLE_FR
        page.goto(server)
        page.wait_for_function("() => !document.documentElement.hasAttribute('data-i18n-pending')")
        links = page.locator("footer .footer-legal a")
        assert [links.nth(i).inner_text().strip() for i in range(2)] == ["Mentions légales & CGV", "Confidentialité"]
        # Back to English through the switcher; the choice is remembered.
        page.goto(server + "privacy")
        page.locator('[data-lang-set="en-US"]').click()
        page.wait_for_function("() => document.documentElement.lang === 'en-US'")
        assert page.locator("h1").inner_text().strip() == PRIVACY_TITLE_EN
        assert page.evaluate("() => localStorage.getItem('markmyass-language')") == "en-US"
        # Clicking a footer link really lands on the page.
        page.locator('footer .footer-legal a[href="legal"]').click()
        page.wait_for_url(lambda u: u.rstrip("/").endswith("/legal"))
        assert page.locator("h1").inner_text().strip() == LEGAL_TITLE_EN
    finally:
        ctx.close()


@_needs_browser
@pytest.mark.parametrize("path", ["legal", "privacy"])
@pytest.mark.parametrize("locale", ["fr-FR", "en-US"])
def test_pages_stay_readable_on_mobile(server, browser, path, locale):
    ctx, page = _open(browser, server + path, locale=locale, width=400)
    try:
        assert page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 1"), "horizontal overflow"
        metrics = page.evaluate(
            """() => {
              const els = [...document.querySelectorAll('article p, article li, article h2')];
              const fs = els.map(e => parseFloat(getComputedStyle(e).fontSize));
              const wide = els.filter(e => e.getBoundingClientRect().right > window.innerWidth).length;
              const addr = document.querySelector('.legal-address');
              return {minFont: Math.min(...fs), wide, addrLines: Math.round(addr.getBoundingClientRect().height / parseFloat(getComputedStyle(addr).lineHeight)),
                      h1: parseFloat(getComputedStyle(document.querySelector('h1')).fontSize), n: els.length};
            }"""
        )
        assert metrics["n"] > 20 and metrics["wide"] == 0
        assert metrics["minFont"] >= 14 and metrics["h1"] >= 24
        assert metrics["addrLines"] == 3  # the address keeps its three lines
        assert page.locator(".lang-switch").is_visible() and page.locator("footer .footer-legal").is_visible()
    finally:
        ctx.close()
