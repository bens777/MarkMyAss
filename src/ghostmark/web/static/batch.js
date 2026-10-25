// Paid batch page (/batch). Four views on one page:
//   - buy:    present the offer, pay (no file picker before payment)
//   - verify: ?session_id=cs_... (Stripe's success redirect) -> server asks Stripe
//   - lot:    pick the files once, run each through the pipeline, build the ZIP
//   - done:   lot finalized -> download the ZIP
// The Stripe session id is the temporary proof of payment; it travels in a
// request header (never a URL the server logs).
//
// The lot can be reopened with the same URL for 24 hours after the Stripe
// payment (the server measures it from Stripe's own session time); results
// still on the server are listed again, otherwise files are simply selected
// again. Past the window every lot call answers 410 and the page says so.
//
// Per-file pipeline, one request per step so the row shows real progress:
//   upload+clean -> verify -> [deep clean -> verify again] -> done
// The server decides whether the deep clean is needed (from the structured
// verifier result); the browser only follows the `stage` it is told.
//
// Localisation reuses the site's single system: every static text is an
// English data-i18n marker in batch.html translated by i18n-apply.js from
// the shared dictionary (i18n-fr.js); runtime strings use MarkMyAss.t(en, fr)
// exactly like app.js; API errors carry an X-Batch-Error code that maps to
// dict["batch.err.<code>"]. Price and limits are filled into
// <span class="offer-*"> placeholders from /api/batch/offer, never typed here.
(function () {
  "use strict";

  const MMA = window.MarkMyAss || {};
  const t = (en, fr) => (MMA.t ? MMA.t(en, fr) : en);
  const el = (id) => document.getElementById(id);
  const isFr = MMA.locale === "fr-FR";
  const dict = MMA.dict || {};
  const API = {
    offer: "api/batch/offer",
    checkout: "api/batch/checkout",
    verify: "api/batch/verify",
    files: "api/batch/files",
    fileVerify: (key) => `api/batch/files/${key}/verify`,
    fileDeep: (key) => `api/batch/files/${key}/deep-clean`,
    fileRemove: (key) => `api/batch/files/${key}`,
    finalize: "api/batch/finalize",
    zip: "api/batch/zip",
  };
  const ALLOWED = /\.(pdf|png|jpe?g|webp)$/i;

  let offer = { price_cents: 199, currency: "eur", min_files: 2, max_files: 50, max_upload_mb: 10, max_total_mb: 64, window_hours: 24, zip_hours: 1 };
  let sessionId = null;
  // key -> {name, status} for finished files; drives counts and the finalize button.
  const results = new Map();

  // Per-file statuses (progress and final), FR/EN through the site's t().
  const STATUS = {
    cleaning: () => t("Cleaning…", "Nettoyage…"),
    verifying: () => t("Verifying…", "Vérification…"),
    deep: () => t("Deep cleaning…", "Nettoyage profond…"),
    reverifying: () => t("Verifying again…", "Nouvelle vérification…"),
    verified: () => t("Cleaned and verified", "Nettoyé et vérifié"),
    incomplete: () => t("Cleaned — verification incomplete", "Nettoyé — vérification incomplète"),
    failed: () => t("Processing failed", "Échec du traitement"),
  };

  function show(view) {
    for (const v of ["buy", "verify", "lot", "done"]) el(`view-${v}`).classList.toggle("hidden", v !== view);
  }

  function showError(node, msg) {
    node.textContent = msg;
    node.classList.remove("hidden");
  }

  function fmtPrice() {
    return new Intl.NumberFormat(isFr ? "fr-FR" : "en-US", { style: "currency", currency: offer.currency.toUpperCase() }).format(offer.price_cents / 100);
  }

  async function safeJson(resp) {
    try {
      return await resp.json();
    } catch {
      return {};
    }
  }

  // Server errors: French from the shared dictionary via the error code,
  // otherwise the server's English detail, otherwise a generic fallback.
  function errText(resp, data, fallback) {
    const code = resp && resp.headers ? resp.headers.get("x-batch-error") : null;
    if (isFr && code && Object.prototype.hasOwnProperty.call(dict, `batch.err.${code}`)) return dict[`batch.err.${code}`];
    return (data && data.detail) || fallback;
  }

  function sessionHeaders(extra) {
    return Object.assign({ "X-Batch-Session": sessionId }, extra || {});
  }

  function fillOffer() {
    const set = (cls, value) => document.querySelectorAll(`.${cls}`).forEach((n) => { n.textContent = value; });
    set("offer-range", `${offer.min_files} ${t("to", "à")} ${offer.max_files}`);
    set("offer-price", fmtPrice());
    set("offer-max-file", String(offer.max_upload_mb));
    set("offer-max-total", String(offer.max_total_mb));
    set("offer-window", String(offer.window_hours));
    set("offer-zip-hours", String(offer.zip_hours));
  }

  // --- buy ------------------------------------------------------------------------
  async function loadOffer() {
    try {
      offer = Object.assign(offer, await (await fetch(API.offer)).json());
    } catch {
      /* defaults above match the server defaults */
    }
    fillOffer();
  }

  async function buy() {
    const btn = el("btn-buy");
    btn.disabled = true;
    try {
      const resp = await fetch(API.checkout, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ locale: isFr ? "fr" : "en" }),
      });
      if (!resp.ok) {
        showError(el("buy-error"), errText(resp, await safeJson(resp), t("Payment service unavailable.", "Service de paiement indisponible.")));
        btn.disabled = false;
        return;
      }
      window.location.href = (await resp.json()).url;
    } catch (err) {
      showError(el("buy-error"), t(`Network error: ${err}`, `Erreur réseau : ${err}`));
      btn.disabled = false;
    }
  }

  // --- verify ---------------------------------------------------------------------
  async function verify(id) {
    show("verify");
    for (let attempt = 0; attempt < 5; attempt++) {
      let resp;
      try {
        resp = await fetch(API.verify, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ session_id: id }),
        });
      } catch (err) {
        showError(el("verify-error"), t(`Network error: ${err}`, `Erreur réseau : ${err}`));
        el("verify-back").classList.remove("hidden");
        return;
      }
      if (resp.status === 402 && attempt < 4) {
        await new Promise((r) => setTimeout(r, 2000)); // payment still settling
        continue;
      }
      const data = await safeJson(resp);
      if (resp.status === 409 && resp.headers.get("x-batch-error") === "already_used") {
        sessionId = id;
        el("done-lead").classList.add("hidden");
        el("done-used").classList.remove("hidden");
        show("done");
        return;
      }
      if (!resp.ok) {
        showError(el("verify-error"), errText(resp, data, t("Could not confirm the payment.", "Impossible de confirmer le paiement.")));
        el("verify-back").classList.remove("hidden");
        return;
      }
      sessionId = id;
      openLot(data);
      return;
    }
  }

  // --- lot ------------------------------------------------------------------------
  function openLot(lot) {
    show("lot");
    el("file-rows").innerHTML = "";
    results.clear();
    for (const r of lot.results || []) {
      results.set(r.key, { name: r.name, status: r.status });
      addRow(r.name, r.status, r);
    }
    updateCount();
  }

  function updateCount() {
    let verified = 0;
    let incomplete = 0;
    for (const r of results.values()) {
      if (r.status === "verified") verified += 1;
      else if (r.status === "incomplete") incomplete += 1;
    }
    el("lot-count").textContent = t(
      `${verified} verified · ${incomplete} with incomplete verification.`,
      `${verified} vérifié${verified === 1 ? "" : "s"} · ${incomplete} avec vérification incomplète.`
    );
    el("btn-finalize").disabled = results.size < 1;
  }

  // One row per file. `status` is a STATUS key; `info` carries the server's
  // final description (warnings, deep_used, verdicts) for finished files.
  function addRow(name, status, info) {
    const row = document.createElement("div");
    row.className = "signal-row";
    const label = document.createElement("span");
    label.className = "signal-label";
    label.textContent = name;
    const right = document.createElement("span");
    row.appendChild(label);
    row.appendChild(right);
    el("file-rows").prepend(row);
    setRow(row, status, info);
    return row;
  }

  function setRow(row, status, info) {
    const right = row.lastElementChild;
    right.className = "signal-status " + (status === "verified" ? "status-clean" : status === "incomplete" ? "status-unverified" : status === "failed" ? "status-found" : "status-unverified");
    right.textContent = (STATUS[status] || (() => status))();
    right.title = "";
    if (info && info.warnings && info.warnings.length) right.title = info.warnings.join("\n");
    if (info && info.detail) right.title = info.detail;
    if (info && info.deep_clean_failed) right.textContent += t(" · deep clean failed, standard clean kept", " · nettoyage profond échoué, nettoyage standard conservé");
    else if (info && info.deep_used) right.textContent += t(" · deep clean used", " · nettoyage profond utilisé");
    if (status === "incomplete" && info && info.key) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "btn secondary";
      btn.style.marginLeft = "0.6rem";
      btn.textContent = t("Remove", "Retirer");
      btn.title = t("Remove this file so you can replace or retry it", "Retirer ce fichier pour le remplacer ou le réessayer");
      btn.addEventListener("click", () => removeFile(info.key, row));
      right.appendChild(btn);
    }
  }

  async function removeFile(key, row) {
    try {
      const resp = await fetch(API.fileRemove(key), { method: "DELETE", headers: sessionHeaders() });
      if (!resp.ok) {
        showError(el("lot-error"), errText(resp, await safeJson(resp), t("Could not remove this file.", "Impossible de retirer ce fichier.")));
        return;
      }
      results.delete(key);
      row.remove();
      updateCount();
    } catch (err) {
      showError(el("lot-error"), t(`Network error: ${err}`, `Erreur réseau : ${err}`));
    }
  }

  function checkSelection(files) {
    const list = Array.from(files);
    const names = (xs) => xs.map((f) => f.name).join(", ");
    const bad = list.filter((f) => !ALLOWED.test(f.name));
    const tooBig = list.filter((f) => f.size > offer.max_upload_mb * 1024 * 1024);
    const total = list.reduce((n, f) => n + f.size, 0);
    if (bad.length) return t(`Not supported: ${names(bad)}`, `Non pris en charge : ${names(bad)}`);
    if (tooBig.length) return t(`Over ${offer.max_upload_mb} MB: ${names(tooBig)}`, `Plus de ${offer.max_upload_mb} Mo : ${names(tooBig)}`);
    if (results.size === 0 && list.length < offer.min_files) {
      return t(
        `Select at least ${offer.min_files} files (or use the free single-file cleaner).`,
        `Sélectionnez au moins ${offer.min_files} fichiers (ou utilisez le nettoyeur gratuit fichier par fichier).`
      );
    }
    if (results.size + list.length > offer.max_files) return t(`At most ${offer.max_files} files per lot.`, `Au maximum ${offer.max_files} fichiers par lot.`);
    if (total > offer.max_total_mb * 1024 * 1024) return t(`A lot is limited to ${offer.max_total_mb} MB in total.`, `Un lot est limité à ${offer.max_total_mb} Mo au total.`);
    return null;
  }

  // A step call: returns {resp, data}; throws on network failure.
  async function step(url, init) {
    const resp = await fetch(url, Object.assign({ headers: sessionHeaders() }, init || {}));
    return { resp, data: await safeJson(resp) };
  }

  // Runs the whole pipeline for one file, updating its row at every stage.
  // Returns "stop" when the lot itself can no longer accept work.
  async function processOne(file) {
    const row = addRow(file.name, "cleaning");
    const fail = (resp, data) => {
      setRow(row, "failed", { detail: errText(resp, data, "") });
      if (resp && resp.status === 410) {
        // The 24 hours after payment ran out mid-lot: nothing more can be processed.
        showError(el("lot-error"), errText(resp, data, t("This payment has expired.", "Ce paiement a expiré.")));
        return "stop";
      }
      return resp && (resp.status === 409 || resp.status === 402) && resp.headers.get("x-batch-error") !== "lot_full" ? "stop" : "next";
    };
    try {
      const form = new FormData();
      form.append("file", file);
      let { resp, data } = await step(API.files, { method: "POST", body: form });
      if (!resp.ok) return fail(resp, data);
      const key = data.key;

      setRow(row, "verifying");
      ({ resp, data } = await step(API.fileVerify(key), { method: "POST" }));
      if (!resp.ok) return fail(resp, data);

      if (data.stage === "needs_deep_clean") {
        setRow(row, "deep");
        ({ resp, data } = await step(API.fileDeep(key), { method: "POST" }));
        if (!resp.ok) return fail(resp, data);
        if (data.stage !== "done") {
          // Deep clean ran: verify its output. (When the deep clean itself
          // failed, the server already finished the file as "incomplete"
          // with the standard clean output kept -- nothing more to verify.)
          setRow(row, "reverifying");
          ({ resp, data } = await step(API.fileVerify(key), { method: "POST" }));
          if (!resp.ok) return fail(resp, data);
        }
      }
      // data.stage === "done": status is verified | incomplete, decided by the server.
      results.set(key, { name: data.name, status: data.status });
      setRow(row, data.status, data);
      return "next";
    } catch (err) {
      setRow(row, "failed", { detail: String(err) });
      showError(el("lot-error"), t(`Network error: ${err}`, `Erreur réseau : ${err}`));
      return "stop";
    }
  }

  async function processFiles(fileList) {
    el("lot-error").classList.add("hidden");
    const files = Array.from(fileList);
    if (!files.length) return;
    const problem = checkSelection(files);
    if (problem) {
      showError(el("lot-error"), problem);
      el("lot-input").value = "";
      return;
    }
    el("lot-input").disabled = true;
    el("btn-finalize").disabled = true;
    for (const file of files) {
      const outcome = await processOne(file);
      if (outcome === "stop") break;
    }
    el("lot-input").disabled = false;
    el("lot-input").value = "";
    updateCount();
  }

  async function finalize() {
    el("lot-error").classList.add("hidden");
    const btn = el("btn-finalize");
    btn.disabled = true;
    try {
      const { resp, data } = await step(API.finalize, { method: "POST" });
      if (!resp.ok) {
        showError(el("lot-error"), errText(resp, data, t("Could not build the ZIP. Please try again.", "Impossible de créer le ZIP. Réessayez.")));
        btn.disabled = false;
        return;
      }
      show("done");
    } catch (err) {
      showError(el("lot-error"), t(`Network error: ${err}`, `Erreur réseau : ${err}`));
      btn.disabled = false;
    }
  }

  async function downloadZip() {
    el("done-error").classList.add("hidden");
    let resp;
    try {
      resp = await fetch(API.zip, { headers: sessionHeaders() });
    } catch (err) {
      showError(el("done-error"), t(`Network error: ${err}`, `Erreur réseau : ${err}`));
      return;
    }
    if (!resp.ok) {
      showError(el("done-error"), errText(resp, await safeJson(resp), t("Download failed.", "Téléchargement impossible.")));
      return;
    }
    const m = /filename="([^"]+)"/.exec(resp.headers.get("content-disposition") || "");
    const blob = await resp.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = (m && m[1]) || "markmyass-batch.zip";
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 10000);
  }

  // --- boot -----------------------------------------------------------------------
  function wireDropzone(zone, input, handler) {
    input.addEventListener("change", (e) => handler(e.target.files));
    ["dragenter", "dragover"].forEach((ev) => zone.addEventListener(ev, (e) => { e.preventDefault(); zone.classList.add("dragover"); }));
    ["dragleave", "drop"].forEach((ev) => zone.addEventListener(ev, (e) => { e.preventDefault(); zone.classList.remove("dragover"); }));
    zone.addEventListener("drop", (e) => { if (e.dataTransfer && e.dataTransfer.files.length) handler(e.dataTransfer.files); });
  }
  wireDropzone(el("lot-dropzone"), el("lot-input"), processFiles);
  el("btn-buy").addEventListener("click", buy);
  el("btn-finalize").addEventListener("click", finalize);
  el("btn-zip").addEventListener("click", downloadZip);

  const params = new URLSearchParams(location.search);
  loadOffer().then(() => {
    if (params.get("session_id")) verify(params.get("session_id"));
    else show("buy");
  });
})();
