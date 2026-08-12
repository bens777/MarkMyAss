(() => {
  "use strict";

  const state = { mode: "text", sessionId: null };

  const el = (id) => document.getElementById(id);
  const tabText = el("tab-text");
  const tabFile = el("tab-file");
  const panelText = el("panel-text");
  const panelFile = el("panel-file");
  const textInput = el("text-input");
  const fileInput = el("file-input");
  const btnInspect = el("btn-inspect");
  const btnClean = el("btn-clean");
  const btnVerify = el("btn-verify");
  const btnSave = el("btn-save");
  const inputError = el("input-error");
  const resultsSection = el("results-section");
  const cleanSection = el("clean-section");
  const verifySection = el("verify-section");
  const resultsTable = el("results-table");
  const cleanTable = el("clean-table");
  const verifyTable = el("verify-table");
  const verifySummary = el("verify-summary");
  const cleanedTextWrap = el("cleaned-text-wrap");
  const cleanedTextOutput = el("cleaned-text-output");

  function showTab(mode) {
    state.mode = mode;
    tabText.classList.toggle("active", mode === "text");
    tabFile.classList.toggle("active", mode === "file");
    panelText.classList.toggle("hidden", mode !== "text");
    panelFile.classList.toggle("hidden", mode !== "file");
  }
  tabText.addEventListener("click", () => showTab("text"));
  tabFile.addEventListener("click", () => showTab("file"));

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
      let text = "PRESERVED";
      if (a.failed) {
        cls = "status-unknown";
        text = "FAILED";
      } else if (a.removed) {
        cls = "status-removed";
        text = "REMOVED";
      }
      status.className = `signal-status ${cls}`;
      status.textContent = text;
      row.appendChild(label);
      row.appendChild(status);
      container.appendChild(row);
    }
  }

  function renderVerify(result) {
    verifyTable.innerHTML = "";
    const seen = new Set();
    for (const d of result.after.detections) {
      seen.add(d.detector);
      const row = document.createElement("div");
      row.className = "signal-row";
      const label = document.createElement("span");
      label.className = "signal-label";
      label.textContent = d.label;
      const status = document.createElement("span");
      let cls = "status-unknown";
      let text = "UNVERIFIED";
      if (d.status === "unknown") {
        cls = "status-unknown";
        text = "UNVERIFIED";
      } else if (result.resolved.includes(d.detector)) {
        cls = "status-removed";
        text = "REMOVED";
      } else if (result.remaining.includes(d.detector)) {
        cls = "status-found";
        text = "REMAINS";
      } else if (d.status === "not_found") {
        cls = "status-not_found";
        text = "NOT PRESENT";
      }
      status.className = `signal-status ${cls}`;
      status.textContent = text;
      row.appendChild(label);
      row.appendChild(status);
      verifyTable.appendChild(row);
    }
    verifySummary.textContent = result.summary;
  }

  function showError(msg) {
    inputError.textContent = msg;
    inputError.classList.remove("hidden");
  }
  function clearError() {
    inputError.classList.add("hidden");
    inputError.textContent = "";
  }

  async function doInspect() {
    clearError();
    resultsSection.classList.add("hidden");
    cleanSection.classList.add("hidden");
    verifySection.classList.add("hidden");
    btnInspect.disabled = true;
    try {
      let resp;
      if (state.mode === "text") {
        resp = await fetch("/api/inspect/text", {
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
        resp = await fetch("/api/inspect/file", { method: "POST", body: form });
      }
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        showError(body.detail || `Inspection failed (${resp.status}).`);
        return;
      }
      const data = await resp.json();
      state.sessionId = data.session_id;
      renderDetections(resultsTable, data.report.detections);
      resultsSection.classList.remove("hidden");
    } catch (err) {
      showError(String(err));
    } finally {
      btnInspect.disabled = false;
    }
  }

  async function doClean() {
    btnClean.disabled = true;
    try {
      const resp = await fetch(`/api/clean/${state.sessionId}`, { method: "POST" });
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
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
    } catch (err) {
      showError(String(err));
    } finally {
      btnClean.disabled = false;
    }
  }

  async function doVerify() {
    btnVerify.disabled = true;
    try {
      const resp = await fetch(`/api/verify/${state.sessionId}`, { method: "POST" });
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        showError(body.detail || `Verify failed (${resp.status}).`);
        return;
      }
      const data = await resp.json();
      renderVerify(data);
      verifySection.classList.remove("hidden");
      btnSave.classList.toggle("hidden", state.mode !== "file");
    } catch (err) {
      showError(String(err));
    } finally {
      btnVerify.disabled = false;
    }
  }

  function doSave() {
    window.location.href = `/api/download/${state.sessionId}`;
  }

  btnInspect.addEventListener("click", doInspect);
  btnClean.addEventListener("click", doClean);
  btnVerify.addEventListener("click", doVerify);
  btnSave.addEventListener("click", doSave);
})();
