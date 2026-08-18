// Applies French translations to the static homepage DOM and wires the
// FR | EN language switcher. Loaded at the end of <body>, BEFORE app.js.
//
// English is the source language: the literal HTML content is en-US, so an
// en-US visitor needs zero translation work (and there is never a flash).
// For fr-FR, every element carrying a `data-i18n` / `data-i18n-attr` marker
// is swapped to its French string from window.MarkMyAss.dict (defined in
// i18n-fr.js), then the body -- held hidden by i18n.js -- is revealed.
(function () {
  "use strict";

  var MMA = window.MarkMyAss || {};
  var root = document.documentElement;

  function reveal() {
    root.removeAttribute("data-i18n-pending");
  }

  function applyFrench() {
    var dict = MMA.dict || {};

    // Text / rich-HTML content. Values are our own trusted French strings,
    // so innerHTML is safe and lets a translation include inline <strong>,
    // <em>, <a> exactly like the English source.
    document.querySelectorAll("[data-i18n]").forEach(function (node) {
      var key = node.getAttribute("data-i18n");
      if (key && Object.prototype.hasOwnProperty.call(dict, key)) {
        node.innerHTML = dict[key];
      }
    });

    // Attribute translations, e.g. data-i18n-attr="placeholder:tool.placeholder;aria-label:nav.crew.aria"
    document.querySelectorAll("[data-i18n-attr]").forEach(function (node) {
      var spec = node.getAttribute("data-i18n-attr") || "";
      spec.split(";").forEach(function (pair) {
        var bits = pair.split(":");
        if (bits.length !== 2) return;
        var attr = bits[0].trim();
        var key = bits[1].trim();
        if (attr && key && Object.prototype.hasOwnProperty.call(dict, key)) {
          node.setAttribute(attr, dict[key]);
        }
      });
    });

    if (Object.prototype.hasOwnProperty.call(dict, "meta.title")) {
      document.title = dict["meta.title"];
    }
  }

  function wireSwitcher() {
    document.querySelectorAll("[data-lang-set]").forEach(function (btn) {
      var loc = btn.getAttribute("data-lang-set");
      var isActive = loc === MMA.locale;
      btn.classList.toggle("active", isActive);
      btn.setAttribute("aria-pressed", isActive ? "true" : "false");
      btn.addEventListener("click", function () {
        if (loc !== MMA.locale && MMA.setLocale) MMA.setLocale(loc);
      });
    });
  }

  try {
    if (MMA.locale === "fr-FR") applyFrench();
  } catch (e) {
    /* translation must never break the page -- fall back to English source */
  } finally {
    reveal();
  }
  wireSwitcher();
})();
