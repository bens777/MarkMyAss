(() => {
  "use strict";

  // Every request path here is RELATIVE (no leading slash) so it resolves
  // against the page's <base href>, which the server injects from
  // GHOSTMARK_BASE_PATH. That is what makes this page work whether it's
  // served at "/" (local `ghostmark ui`) or reverse-proxied under
  // "/ghostmark/" (the public moseisley.sh deployment) -- see
  // ghostmark.web.app._inject_base_href and DEPLOY_MOSEISLEY.md.
  const API = {
    config: "api/config",
    inspectText: "api/inspect/text",
    inspectFile: "api/inspect/file",
    clean: (id) => `api/clean/${id}`,
    verify: (id) => `api/verify/${id}`,
    download: (id) => `api/download/${id}`,
    receiptDownload: (id, format) => `api/receipt/${id}/download?format=${format}`,
    presenceHeartbeat: "api/presence/heartbeat",
    publicStats: "api/public-stats",
  };

  // Plain-language "Explain" copy for STEP 1 -- keyed by detector id. This
  // is what separates "here's a table of jargon" from actually telling a
  // non-technical user what was found.
  const EXPLANATIONS = {
    unicode: "Hidden or invisible characters were found in the text. These can be used to hide instructions or track where text came from.",
    exif: "Camera/device or export-tool metadata (EXIF) was found embedded in this image.",
    xmp: "XMP metadata was found -- structured info such as the tool or author that created this file.",
    iptc: "IPTC metadata was found -- often used for captions, keywords, or copyright info.",
    png_text: "Text embedded in this PNG's own metadata chunks was found (comments, software tags, etc).",
    comment: "A comment segment was found embedded in this file.",
    pdf_info: "This PDF's document-info fields (Title, Author, Producer, etc.) contain data.",
    pdf_xmp: "This PDF has an embedded XMP metadata stream.",
    c2pa: "A C2PA/JUMBF provenance container was found. MarkMyAss's detection here is heuristic, not a full manifest validation -- see the AI Watermark Lab for details.",
  };

  function explanationFor(detector) {
    return EXPLANATIONS[detector] || null;
  }

  const state = { mode: "text", sessionId: null, config: null };

  const el = (id) => document.getElementById(id);
  const tabText = el("tab-text");
  const tabFile = el("tab-file");
  const panelText = el("panel-text");
  const panelFile = el("panel-file");
  const textInput = el("text-input");
  const fileInput = el("file-input");
  const dropzone = el("dropzone");
  const chosenFileName = el("chosen-file-name");
  const btnInspect = el("btn-inspect");
  const btnClean = el("btn-clean");
  const btnVerify = el("btn-verify");
  const btnSave = el("btn-save");
  const inputError = el("input-error");
  const resultsSection = el("results-section");
  const cleanSection = el("clean-section");
  const verifySection = el("verify-section");
  const resultsTable = el("results-table");
  const resultsCount = el("results-count");
  const explainPanel = el("explain-panel");
  const explainList = el("explain-list");
  const cleanTable = el("clean-table");
  const verifyBeforeTable = el("verify-before-table");
  const verifyAfterTable = el("verify-after-table");
  const exiftoolPanel = el("exiftool-panel");
  const verdictPanel = el("verdict-panel");
  const cleanedTextWrap = el("cleaned-text-wrap");
  const cleanedTextOutput = el("cleaned-text-output");
  const arrow1 = el("arrow-1");
  const arrow2 = el("arrow-2");
  const arrow3 = el("arrow-3");
  const privacyNote = el("privacy-note");
  const footerPrivacy = el("footer-privacy");
  const uploadLimitHint = el("upload-limit-hint");
  const receiptDownloads = el("receipt-downloads");
  const receiptJson = el("receipt-json");
  const receiptHtml = el("receipt-html");
  const receiptTxt = el("receipt-txt");
  const labTeaser = el("lab-teaser");
  const moseisleyCta = el("moseisley-cta");

  async function loadConfig() {
    try {
      const resp = await fetch(API.config);
      const config = await resp.json();
      state.config = config;
      applyConfig(config);
    } catch {
      // Config endpoint is best-effort UI polish -- the app still works
      // with the default (local) copy if this fails.
    }
  }

  function applyConfig(config) {
    const hosted = config.mode === "hosted";
    document.querySelectorAll(".hosted-only").forEach((elm) => elm.classList.toggle("hidden", !hosted));

    if (hosted) {
      const text = "Files are processed temporarily on the MarkMyAss server and automatically deleted. We do not retain uploaded files.";
      privacyNote.textContent = text;
      footerPrivacy.textContent = `Hosted version: files are deleted automatically after processing (max ${config.session_ttl_minutes} minutes).`;
    } else {
      const text = "100% local — this copy of MarkMyAss runs on your own computer. Files never leave your device.";
      privacyNote.textContent = text;
      footerPrivacy.textContent = "Local MarkMyAss: nothing is ever uploaded anywhere.";
    }
    if (config.max_upload_mb && config.max_text_upload_mb) {
      // Both numbers come from the server (/api/config), so this copy can
      // never drift from what the backend actually enforces.
      uploadLimitHint.textContent = `Images & PDFs: up to ${config.max_upload_mb} MB · Text files: up to ${config.max_text_upload_mb} MB.`;
    } else if (config.max_upload_mb) {
      uploadLimitHint.textContent = `Maximum file size: ${config.max_upload_mb} MB.`;
    }
  }

  function showTab(mode) {
    state.mode = mode;
    tabText.classList.toggle("active", mode === "text");
    tabFile.classList.toggle("active", mode === "file");
    panelText.classList.toggle("hidden", mode !== "text");
    panelFile.classList.toggle("hidden", mode !== "file");
  }
  tabText.addEventListener("click", () => showTab("text"));
  tabFile.addEventListener("click", () => showTab("file"));

  fileInput.addEventListener("change", () => {
    const file = fileInput.files[0];
    if (file) {
      chosenFileName.textContent = `Selected: ${file.name}`;
      chosenFileName.classList.remove("hidden");
    }
  });

  ["dragover", "dragenter"].forEach((evt) =>
    dropzone.addEventListener(evt, (e) => {
      e.preventDefault();
      dropzone.classList.add("dragover");
    })
  );
  ["dragleave", "dragend"].forEach((evt) => dropzone.addEventListener(evt, () => dropzone.classList.remove("dragover")));
  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
    if (e.dataTransfer.files.length) {
      fileInput.files = e.dataTransfer.files;
      fileInput.dispatchEvent(new Event("change"));
    }
  });

  function statusLabel(status) {
    return { found: "FOUND", not_found: "NOT FOUND", unknown: "UNKNOWN" }[status] || status.toUpperCase();
  }

  // A small spectral ghost glyph, shown briefly next to a newly-detected
  // (FOUND) signal -- purely decorative, the literal status word next to
  // it is what actually conveys the result. See DESIGN_SYSTEM.md.
  const GHOST_GLYPH_SVG =
    '<svg class="ghost-glyph ghost-appear" viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" focusable="false">' +
    '<path d="M4 20V11a6 6 0 0 1 12 0v9l-2-1.6-2 1.6-2-1.6-2 1.6-2-1.6Z" fill="currentColor" opacity="0.75"/>' +
    "</svg>";

  // Same ghost glyph, but shown on a REMOVED row during cleaning -- fades
  // and shrinks out (.ghost-dissolve) rather than fading in, so a trace
  // visibly "dissolves" instead of just silently disappearing from the
  // list. Single play, not a loop.
  const GHOST_DISSOLVE_SVG =
    '<svg class="ghost-glyph ghost-dissolve" viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" focusable="false">' +
    '<path d="M4 20V11a6 6 0 0 1 12 0v9l-2-1.6-2 1.6-2-1.6-2 1.6-2-1.6Z" fill="currentColor" opacity="0.75"/>' +
    "</svg>";

  // A small wax-seal glyph for a clean verification result -- echoes
  // static/art/verify-seal.svg without an extra image request.
  const SEAL_GLYPH_SVG =
    '<svg class="verdict-icon ghost-appear" viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" focusable="false">' +
    '<circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="1.6"/>' +
    '<path d="M8 12.3l2.6 2.6L16 9.4" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>' +
    "</svg>";

  // A small fog/ghost glyph for unverified or not-applicable results --
  // "uncharted waters," but the badge text next to it always spells out
  // the literal verdict.
  const FOG_GLYPH_SVG =
    '<svg class="verdict-icon ghost-appear" viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" focusable="false">' +
    '<path d="M4 19V11a6 6 0 0 1 12 0v8l-2-1.5-2 1.5-2-1.5-2 1.5-2-1.5Z" fill="currentColor" opacity="0.6"/>' +
    "</svg>";

  function renderDetections(container, detections) {
    container.innerHTML = "";
    for (const d of detections) {
      const row = document.createElement("div");
      row.className = "signal-row";
      const label = document.createElement("span");
      label.className = "signal-label";
      if (d.status === "found") {
        label.insertAdjacentHTML("beforeend", GHOST_GLYPH_SVG);
      }
      label.appendChild(document.createTextNode(d.label));
      if (d.experimental) {
        const tag = document.createElement("span");
        tag.className = "experimental-tag";
        tag.textContent = "EXPERIMENTAL / UNVERIFIED";
        label.appendChild(tag);
      }
      const status = document.createElement("span");
      status.className = `signal-status status-${d.status}`;
      status.textContent = statusLabel(d.status);
      row.appendChild(label);
      row.appendChild(status);
      container.appendChild(row);

      // Native tag-level detail: WHAT is inside the container (author,
      // software, GPS, AI-provenance markers, ...), straight from
      // MarkMyAss's own engine -- no external tool involved.
      const fields = (d.details && d.details.fields) || [];
      if (fields.length) {
        const list = document.createElement("ul");
        list.className = "field-list";
        for (const f of fields) {
          const item = document.createElement("li");
          const cat = document.createElement("span");
          cat.className = "field-category";
          cat.textContent = f.category;
          item.appendChild(cat);
          item.appendChild(document.createTextNode(` ${f.tag}`));
          if (f.preview) {
            const val = document.createElement("span");
            val.className = "field-preview";
            val.textContent = ` — ${f.preview}`;
            item.appendChild(val);
          }
          list.appendChild(item);
        }
        container.appendChild(list);
      }
    }
  }

  function renderCleanActions(container, actions) {
    container.innerHTML = "";
    for (const a of actions) {
      const row = document.createElement("div");
      row.className = "signal-row";
      const label = document.createElement("span");
      label.className = "signal-label";
      if (a.removed) {
        label.insertAdjacentHTML("beforeend", GHOST_DISSOLVE_SVG);
      }
      label.appendChild(document.createTextNode(a.label));
      const status = document.createElement("span");
      let cls = "status-not_found";
      let text = "NOT PRESENT";
      if (a.failed) {
        cls = "status-unknown";
        text = "FAILED";
      } else if (a.removed) {
        cls = "status-removed";
        text = "REMOVED";
      } else if (a.preserved) {
        cls = "status-unverified";
        text = "PRESERVED";
      }
      status.className = `signal-status ${cls}`;
      status.textContent = text;
      row.appendChild(label);
      row.appendChild(status);
      container.appendChild(row);
    }
  }

  function renderExiftoolPanel(external, c2pa) {
    exiftoolPanel.innerHTML = "";
    const heading = document.createElement("h3");
    heading.textContent = "Independent verification";
    exiftoolPanel.appendChild(heading);

    const body = document.createElement("div");
    const lines = [];

    if (!external || !external.applicable) {
      lines.push(external && external.note ? external.note : "ExifTool: not applicable to this input.");
    } else if (!external.available) {
      lines.push("ExifTool: unavailable. MarkMyAss's own verification above still applies, but this independent cross-check could not run.");
    } else {
      const version = external.version || "unknown version";
      lines.push(`Verified with ExifTool ${version}`);
      const remaining = Object.keys((external.tags_by_origin || {}).embedded_metadata || {});
      if (remaining.length === 0) {
        lines.push("✓ No embedded metadata found");
      } else {
        lines.push(`⚠ ${remaining.length} embedded metadata tag(s) still present:`);
        remaining.slice(0, 8).forEach((k) => lines.push(`&nbsp;&nbsp;${k}`));
      }
    }

    if (c2pa && c2pa.applicable) {
      if (!c2pa.available) {
        lines.push("c2patool: unavailable (optional). See the AI Watermark Lab for install info.");
      } else {
        const version = c2pa.version || "unknown version";
        lines.push(`Verified with c2patool ${version}`);
        lines.push(c2pa.found ? "⚠ c2patool still finds a C2PA manifest" : "✓ c2patool finds no C2PA manifest");
      }
    }

    body.innerHTML = lines.join("<br>");
    exiftoolPanel.appendChild(body);
  }

  // "unverified" semantics: MarkMyAss's own native engine confirmed the
  // supported signals are gone, but no independent external verifier
  // (ExifTool/c2patool) was available to corroborate -- so the badge
  // says exactly that instead of a vague "UNVERIFIED".
  const VERDICT_TEXT = {
    verified_clean: "INDEPENDENTLY VERIFIED CLEAN",
    partial: "PARTIAL",
    unverified: "NATIVE CLEAN — NOT INDEPENDENTLY VERIFIED",
    not_applicable: "NOT APPLICABLE",
    failed: "FAILED",
  };

  function renderVerdict(summary) {
    verdictPanel.innerHTML = "";
    if (!summary) return;

    const heading = document.createElement("h3");
    heading.textContent = "Result";
    verdictPanel.appendChild(heading);

    const badge = document.createElement("span");
    badge.className = `verdict-badge verdict-${summary.verdict}`;
    const icon = summary.verdict === "verified_clean" ? SEAL_GLYPH_SVG
      : summary.verdict === "failed" ? ""
      : FOG_GLYPH_SVG;
    if (icon) badge.insertAdjacentHTML("beforeend", icon);
    badge.appendChild(document.createTextNode(VERDICT_TEXT[summary.verdict] || "UNVERIFIED"));
    verdictPanel.appendChild(badge);

    const lines = document.createElement("div");
    lines.style.marginTop = "0.75rem";
    lines.style.fontSize = "0.9rem";
    const detailLines = [`MarkMyAss native verification: ${summary.ghostmark_pass ? "PASS" : "FAIL"}`];
    for (const verifier of summary.external_verifiers || []) {
      if (verifier.passed === null || verifier.passed === undefined) {
        detailLines.push(`${verifier.label} verification: NOT AVAILABLE / NOT APPLICABLE`);
      } else {
        detailLines.push(`${verifier.label} verification: ${verifier.passed ? "PASS" : "FAIL"}`);
      }
    }
    detailLines.push(`C2PA support: ${summary.c2pa_status.toUpperCase()}`);
    lines.innerHTML = detailLines.join("<br>");
    verdictPanel.appendChild(lines);
  }

  function showError(msg) {
    inputError.textContent = msg;
    inputError.classList.remove("hidden");
  }
  function clearError() {
    inputError.classList.add("hidden");
    inputError.textContent = "";
  }

  async function safeJson(resp) {
    try {
      return await resp.json();
    } catch {
      return {};
    }
  }

  // Swaps a button's label to a loading message for the duration of an
  // async operation, then restores it -- a disabled button alone isn't
  // sufficient feedback that something is happening (ui-ux-pro-max:
  // "show feedback during async operations").
  function withLoadingLabel(button, loadingText) {
    const original = button.textContent;
    button.disabled = true;
    button.textContent = loadingText;
    return () => {
      button.disabled = false;
      button.textContent = original;
    };
  }

  async function doInspect() {
    clearError();
    resultsSection.classList.add("hidden");
    cleanSection.classList.add("hidden");
    verifySection.classList.add("hidden");
    arrow1.classList.add("hidden");
    arrow2.classList.add("hidden");
    arrow3.classList.add("hidden");
    const restoreInspect = withLoadingLabel(btnInspect, "Scanning the cargo…");
    try {
      let resp;
      if (state.mode === "text") {
        resp = await fetch(API.inspectText, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: textInput.value }),
        });
      } else {
        const file = fileInput.files[0];
        if (!file) {
          showError("Choose a file first.");
          return;
        }
        const form = new FormData();
        form.append("file", file);
        resp = await fetch(API.inspectFile, { method: "POST", body: form });
      }
      if (!resp.ok) {
        const body = await safeJson(resp);
        showError(body.detail || `Inspection failed (${resp.status}).`);
        return;
      }
      const data = await resp.json();
      state.sessionId = data.session_id;
      renderDetections(resultsTable, data.report.detections);
      const found = data.report.detections.filter((d) => d.status === "found");
      resultsCount.textContent = `${found.length} supported signal${found.length === 1 ? "" : "s"} detected`;

      explainList.innerHTML = "";
      const explanations = found.map((d) => explanationFor(d.detector)).filter(Boolean);
      if (explanations.length) {
        explanations.forEach((text) => {
          const li = document.createElement("li");
          li.textContent = text;
          explainList.appendChild(li);
        });
        explainPanel.classList.remove("hidden");
      } else {
        explainPanel.classList.add("hidden");
      }

      resultsSection.classList.remove("hidden");
      arrow1.classList.remove("hidden");
    } catch (err) {
      showError(String(err));
    } finally {
      restoreInspect();
    }
  }

  async function doClean() {
    const restoreClean = withLoadingLabel(btnClean, "Clearing the deck…");
    try {
      const resp = await fetch(API.clean(state.sessionId), { method: "POST" });
      if (!resp.ok) {
        const body = await safeJson(resp);
        showError(body.detail || `Clean failed (${resp.status}).`);
        return;
      }
      const data = await resp.json();
      renderCleanActions(cleanTable, data.actions);
      if (state.mode === "text") {
        cleanedTextOutput.value = data.cleaned_text || "";
        cleanedTextWrap.classList.remove("hidden");
      } else {
        cleanedTextWrap.classList.add("hidden");
      }
      cleanSection.classList.remove("hidden");
      arrow2.classList.remove("hidden");
    } catch (err) {
      showError(String(err));
    } finally {
      restoreClean();
    }
  }

  async function doVerify() {
    const restoreVerify = withLoadingLabel(btnVerify, "Signaling the second observer…");
    try {
      const resp = await fetch(API.verify(state.sessionId), { method: "POST" });
      if (!resp.ok) {
        const body = await safeJson(resp);
        showError(body.detail || `Verify failed (${resp.status}).`);
        return;
      }
      const data = await resp.json();
      renderDetections(verifyBeforeTable, data.before.detections);
      renderDetections(verifyAfterTable, data.after.detections);
      renderExiftoolPanel(data.external_after, data.c2pa_after);
      renderVerdict(data.verification_summary);
      verifySection.classList.remove("hidden");
      arrow3.classList.remove("hidden");
      btnSave.classList.toggle("hidden", state.mode !== "file");

      receiptJson.href = API.receiptDownload(state.sessionId, "json");
      receiptHtml.href = API.receiptDownload(state.sessionId, "html");
      receiptTxt.href = API.receiptDownload(state.sessionId, "txt");
      receiptDownloads.classList.remove("hidden");
      labTeaser.classList.remove("hidden");
      // Value first, Moseisley second: this card only appears after the
      // user already has their verified result, download and receipts.
      if (moseisleyCta) moseisleyCta.classList.remove("hidden");
    } catch (err) {
      showError(String(err));
    } finally {
      restoreVerify();
    }
  }

  function doSave() {
    window.location.href = API.download(state.sessionId);
  }

  btnInspect.addEventListener("click", doInspect);
  btnClean.addEventListener("click", doClean);
  btnVerify.addEventListener("click", doVerify);
  btnSave.addEventListener("click", doSave);

  loadConfig();

  // --- Social proof (real usage counter) -------------------------------------
  // Values come from /api/public-stats (durable aggregate counts, never
  // fabricated). The whole block stays hidden unless the endpoint answers
  // with a real lifetime total >= 1 -- on any failure, or before the first
  // real clean, nothing is shown (never a 0, never a fake number). The
  // 24h line is shown only when its real value meets a small threshold.
  const SOCIAL_PROOF_MIN_TOTAL = 1;
  const socialProof = el("social-proof");
  const socialProofCount = el("social-proof-count");

  async function loadSocialProof() {
    if (!socialProof || !socialProofCount) return;
    try {
      const resp = await fetch(API.publicStats);
      if (!resp.ok) return; // stays hidden
      const data = await resp.json();
      const total = data.files_cleaned_total;
      if (typeof total !== "number" || total < SOCIAL_PROOF_MIN_TOTAL) return; // never show 0
      socialProofCount.textContent = total.toLocaleString("en-US");
      socialProof.classList.remove("hidden");
    } catch {
      // Network/parse error -> leave the block hidden, never show fallbacks.
    }
  }

  loadSocialProof();

  // --- Theme toggle ----------------------------------------------------------
  // static/theme-init.js already applied the theme before first paint;
  // this only wires the explicit user control. Saved choice overrides
  // system preference; no saved choice means DARK (the canonical brand
  // identity).
  const themeToggle = el("theme-toggle");

  function syncThemeToggleLabel() {
    if (!themeToggle) return;
    const current = document.documentElement.getAttribute("data-theme") === "light" ? "light" : "dark";
    themeToggle.setAttribute("aria-label", current === "dark" ? "Switch to light mode" : "Switch to dark mode");
  }

  if (themeToggle) {
    syncThemeToggleLabel();
    themeToggle.addEventListener("click", () => {
      const next = document.documentElement.getAttribute("data-theme") === "light" ? "dark" : "light";
      document.documentElement.setAttribute("data-theme", next);
      try {
        localStorage.setItem("markmyass-theme", next);
      } catch {
        // Storage blocked: the choice still applies for this page view.
      }
      syncThemeToggleLabel();
    });
  }

  // --- Mobile hamburger navigation -------------------------------------------
  // Compact dropdown for the secondary nav links only; the Moseisley CTA
  // and theme toggle always stay visible in the header bar. Closes on
  // link click, Escape (focus returns to the button), and outside click.
  const navBurger = el("nav-burger");
  const navLinks = el("nav-links");

  function setMenu(open) {
    if (!navBurger || !navLinks) return;
    navLinks.classList.toggle("open", open);
    navBurger.setAttribute("aria-expanded", open ? "true" : "false");
    navBurger.setAttribute("aria-label", open ? "Close navigation" : "Open navigation");
  }

  if (navBurger && navLinks) {
    navBurger.addEventListener("click", () => {
      setMenu(!navLinks.classList.contains("open"));
    });
    navLinks.addEventListener("click", (e) => {
      if (e.target.closest("a")) setMenu(false);
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && navLinks.classList.contains("open")) {
        setMenu(false);
        navBurger.focus();
      }
    });
    document.addEventListener("click", (e) => {
      if (
        navLinks.classList.contains("open") &&
        !navLinks.contains(e.target) &&
        !navBurger.contains(e.target)
      ) {
        setMenu(false);
      }
    });
  }

  // --- Live presence ("pirates aboard") -------------------------------------
  // Real aggregate count of active visitors -- never fabricated, never
  // inflated. The session id is random, generated fresh per tab, kept only
  // in this closure (no cookie, no storage), and the server keeps it in
  // memory for at most 3 minutes. Heartbeats pause while the tab is hidden.
  const presenceLine = el("presence-line");
  const presenceText = el("presence-text");
  const PRESENCE_INTERVAL_MS = 45000;

  function presenceCopy(count, capped) {
    // `count` is verified to be a number by the caller, so interpolating
    // it into markup is safe. When the server-side registry is at its
    // hard cap, more visitors may exist than it can admit -- say "N+"
    // instead of a falsely exact number.
    const n = `<strong class="presence-count">${count}${capped ? "+" : ""}</strong>`;
    if (count === 1 && !capped) return `${n} pirate is cleaning hidden AI traces right now`;
    if (count >= 1) return `${n} pirates are cleaning hidden AI traces right now`;
    return "No pirates cleaning hidden AI traces right now — be the first aboard.";
  }

  if (presenceLine && presenceText && window.crypto && crypto.getRandomValues) {
    const bytes = new Uint8Array(16);
    crypto.getRandomValues(bytes);
    const presenceSid = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");

    async function presenceBeat() {
      try {
        const resp = await fetch(API.presenceHeartbeat, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ sid: presenceSid }),
        });
        if (!resp.ok) return;
        const data = await resp.json();
        if (typeof data.active !== "number") return;
        presenceText.innerHTML = presenceCopy(data.active, data.capped === true);
        presenceLine.classList.remove("hidden");
      } catch {
        // Presence is decoration -- never surface an error for it.
      }
    }

    presenceBeat();
    setInterval(() => {
      if (document.visibilityState === "visible") presenceBeat();
    }, PRESENCE_INTERVAL_MS);
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "visible") presenceBeat();
    });
  }
})();
