// Locale engine for MarkMyAss. Loaded synchronously in <head> (like
// theme-init.js) so <html lang> is correct from the first paint and, for
// French, the body is held hidden until translation applies (no
// English->French flash). CSP is script-src 'self', so this is an external
// file, never inline.
//
// Only TWO locales exist: "en-US" (universal fallback) and "fr-FR". Any
// browser language starting with "fr" resolves to fr-FR; everything else
// resolves to en-US. A saved manual choice always overrides browser
// detection.
(function () {
  "use strict";

  var SUPPORTED = ["en-US", "fr-FR"];
  var STORAGE_KEY = "markmyass-language";
  var DEFAULT_LOCALE = "en-US";

  // Pure resolver -- no DOM/storage access, so it can be unit-tested
  // directly (see tests/test_i18n.py, executed via Node).
  //   savedChoice: a previously persisted manual choice (or null/invalid)
  //   navigatorLanguage: navigator.language (e.g. "fr-CA", "en-GB", "de-DE")
  function resolveLocale(navigatorLanguage, savedChoice) {
    if (savedChoice === "fr-FR" || savedChoice === "en-US") {
      return savedChoice; // a saved manual choice always wins
    }
    var nav = (navigatorLanguage || "").toLowerCase();
    if (nav.indexOf("fr") === 0) {
      return "fr-FR"; // fr-FR, fr-CA, fr-BE, fr-CH, ... -> fr-FR
    }
    return DEFAULT_LOCALE; // en-US, en-GB, de-DE, es-ES, ... -> en-US
  }

  function readSaved() {
    try {
      return localStorage.getItem(STORAGE_KEY);
    } catch (e) {
      return null; // storage blocked -> fall back to browser detection
    }
  }

  var api = {
    SUPPORTED: SUPPORTED,
    STORAGE_KEY: STORAGE_KEY,
    DEFAULT_LOCALE: DEFAULT_LOCALE,
    resolveLocale: resolveLocale,
    locale: DEFAULT_LOCALE,
    // Runtime string helper for app.js: returns the French variant when the
    // active locale is fr-FR, otherwise the English source string.
    t: function (en, fr) {
      return this.locale === "fr-FR" && typeof fr === "string" ? fr : en;
    },
    // Persist a manual choice and reload so every surface (static DOM +
    // runtime strings) renders in the chosen locale with no partial state.
    setLocale: function (loc) {
      if (SUPPORTED.indexOf(loc) === -1) return;
      try {
        localStorage.setItem(STORAGE_KEY, loc);
      } catch (e) {
        /* storage blocked: fall through and still apply for this view */
      }
      if (typeof location !== "undefined") location.reload();
    },
  };

  // Browser-only bootstrap. Guarded so `require()` in Node (tests) only gets
  // the pure resolver above and never touches document/localStorage.
  if (typeof document !== "undefined") {
    var locale = resolveLocale(
      typeof navigator !== "undefined" ? navigator.language : "",
      readSaved()
    );
    api.locale = locale;
    var root = document.documentElement;
    root.setAttribute("lang", locale);
    if (locale === "fr-FR") {
      // Hold the body hidden (see style.css) until i18n-apply.js swaps the
      // English source DOM to French, so there is no mixed-language flash.
      root.setAttribute("data-i18n-pending", "");
      // Failsafe: never leave the page permanently hidden if apply fails.
      setTimeout(function () {
        root.removeAttribute("data-i18n-pending");
      }, 1500);
    }
    window.MarkMyAss = window.MarkMyAss || {};
    for (var k in api) {
      if (Object.prototype.hasOwnProperty.call(api, k)) window.MarkMyAss[k] = api[k];
    }
  }

  if (typeof module !== "undefined" && module.exports) {
    module.exports = { resolveLocale: resolveLocale, SUPPORTED: SUPPORTED, STORAGE_KEY: STORAGE_KEY };
  }
})();
