// Applies the theme BEFORE first paint (loaded synchronously in <head>,
// ahead of the stylesheet). External file rather than inline because the
// site's CSP is script-src 'self'.
//
// Dark is MarkMyAss's canonical default: a visitor with no saved choice
// gets dark regardless of prefers-color-scheme. Only an explicit toggle
// choice (localStorage "markmyass-theme") selects light.
(function () {
  var theme = "dark";
  try {
    if (localStorage.getItem("markmyass-theme") === "light") theme = "light";
  } catch (e) {
    /* storage blocked -> default dark */
  }
  document.documentElement.setAttribute("data-theme", theme);
})();
