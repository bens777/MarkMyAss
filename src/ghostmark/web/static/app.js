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
  };

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
      const text = "Files are processed temporarily on the GhostMark server and automatically deleted. We do not retain uploaded files.";
      privacyNote.textContent = text;
      footerPrivacy.textContent = `Hosted version: files are deleted automatically after processing (max ${config.session_ttl_minutes} minutes).`;
    } else {
      const text = "100% local — this copy of GhostMark runs on your own computer. Files never leave your device.";
      privacyNote.textContent = text;
      footerPrivacy.textContent = "Local GhostMark: nothing is ever uploaded anywhere.";
    }
    if (config.max_upload_mb) {
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

  function renderDetections(container, detections) {
    container.innerHTML = "";
    for (const d of detections) {
      const row = document.createElement("div");
      row.className = "signal-row";
      const label = document.createElement("span");
      label.className = "signal-label";
      label.textContent = d.label;
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
    }
  }

  function renderCleanActions(container, actions) {
    container.innerHTML = "";
    for (const a of actions) {
      const row = document.createElement("div");
      row.className = "signal-row";
      const label = document.createElement("span");
      label.className = "signal-label";
      label.textContent = a.label;
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

  function renderExiftoolPanel(external) {
    exiftoolPanel.innerHTML = "";
    const heading = document.createElement("h3");
    heading.textContent = "Independent verification";
    exiftoolPanel.appendChild(heading);

    const body = document.createElement("div");
    if (!external || !external.applicable) {
      body.textContent = external && external.note ? external.note : "Independent verification is not applicable to this input.";
    } else if (!external.available) {
      body.innerHTML =
        "Independent verification unavailable.<br>GhostMark internal verification passed, but independent ExifTool verification could not be performed.";
    } else {
      const version = external.version || "unknown version";
      const lines = [`Verified with ExifTool ${version}`];
      const remaining = Object.keys(external.tags_by_origin.embedded_metadata || {});
      if (remaining.length === 0) {
        lines.push("✓ No embedded metadata found");
      } else {
        lines.push(`⚠ ${remaining.length} embedded metadata tag(s) still present:`);
        remaining.slice(0, 8).forEach((k) => lines.push(`&nbsp;&nbsp;${k}`));
      }
      body.innerHTML = lines.join("<br>");
    }
    exiftoolPanel.appendChild(body);
  }

  function renderVerdict(summary) {
    verdictPanel.innerHTML = "";
    if (!summary) return;

    const heading = document.createElement("h3");
    heading.textContent = "Result";
    verdictPanel.appendChild(heading);

    const badge = document.createElement("span");
    const verdictText = { verified_clean: "VERIFIED CLEAN", partial: "PARTIAL", unverified: "UNVERIFIED" }[summary.verdict] || "UNVERIFIED";
    badge.className = `verdict-badge verdict-${summary.verdict}`;
    badge.textContent = verdictText;
    verdictPanel.appendChild(badge);

    const lines = document.createElement("div");
    lines.style.marginTop = "0.75rem";
    lines.style.fontSize = "0.9rem";
    const ghostmarkLine = `GhostMark verification: ${summary.ghostmark_pass ? "PASS" : "FAIL"}`;
    let exiftoolLine;
    if (summary.exiftool_pass === null || summary.exiftool_pass === undefined) {
      exiftoolLine = "ExifTool verification: NOT AVAILABLE / NOT APPLICABLE";
    } else {
      exiftoolLine = `ExifTool verification: ${summary.exiftool_pass ? "PASS" : "FAIL"}`;
    }
    const c2paLine = `C2PA support: ${summary.c2pa_status.toUpperCase()}`;
    lines.innerHTML = [ghostmarkLine, exiftoolLine, c2paLine].join("<br>");
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

  async function doInspect() {
    clearError();
    resultsSection.classList.add("hidden");
    cleanSection.classList.add("hidden");
    verifySection.classList.add("hidden");
    arrow1.classList.add("hidden");
    arrow2.classList.add("hidden");
    arrow3.classList.add("hidden");
    btnInspect.disabled = true;
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
      resultsSection.classList.remove("hidden");
      arrow1.classList.remove("hidden");
    } catch (err) {
      showError(String(err));
    } finally {
      btnInspect.disabled = false;
    }
  }

  async function doClean() {
    btnClean.disabled = true;
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
      btnClean.disabled = false;
    }
  }

  async function doVerify() {
    btnVerify.disabled = true;
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
      renderExiftoolPanel(data.external_after);
      renderVerdict(data.verification_summary);
      verifySection.classList.remove("hidden");
      arrow3.classList.remove("hidden");
      btnSave.classList.toggle("hidden", state.mode !== "file");
    } catch (err) {
      showError(String(err));
    } finally {
      btnVerify.disabled = false;
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
})();
