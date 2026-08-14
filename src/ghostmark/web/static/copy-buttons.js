// Adds a Copy button to every fenced code block on the page (used by
// the /skill installation guide). Same-origin script: the site's CSP
// (script-src 'self') forbids inline JS.
(function () {
  "use strict";

  document.querySelectorAll("article pre").forEach(function (pre) {
    var code = pre.querySelector("code");
    if (!code) return;

    var wrap = document.createElement("div");
    wrap.className = "copy-wrap";
    pre.parentNode.insertBefore(wrap, pre);
    wrap.appendChild(pre);

    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "copy-btn";
    btn.textContent = "Copy";
    btn.setAttribute("aria-label", "Copy command to clipboard");
    wrap.appendChild(btn);

    btn.addEventListener("click", function () {
      var text = code.textContent.replace(/\n+$/, "");
      navigator.clipboard.writeText(text).then(
        function () {
          btn.textContent = "Copied!";
          btn.classList.add("copied");
          setTimeout(function () {
            btn.textContent = "Copy";
            btn.classList.remove("copied");
          }, 1600);
        },
        function () {
          btn.textContent = "Press Ctrl+C";
          var range = document.createRange();
          range.selectNodeContents(code);
          var sel = window.getSelection();
          sel.removeAllRanges();
          sel.addRange(range);
        }
      );
    });
  });
})();
