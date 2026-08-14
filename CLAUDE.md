# Project instructions for Claude Code

## Browser automation / visual QA — HARD RULE

**Never connect to, automate, terminate, restart, or close the user's
personal Chrome browser or Chrome profile. All browser automation and
visual QA must use a separate isolated Playwright Chromium instance
launched by the project.**

Concretely:

- NEVER run `taskkill` / `Stop-Process` / `pkill` / `killall` against
  `chrome.exe` or any process-name pattern — killing by image name
  sweeps up the user's personal browser and destroys their open tabs.
  Terminate ONLY the exact process you launched, via the automation
  API (`browser.close()` on your own instance) or its specific PID.
- NEVER attach to an existing Chrome via CDP/`connect_over_cdp`, and
  never reuse a debugging port you did not open yourself.
- NEVER use a real Chrome profile (`%LOCALAPPDATA%\Google\Chrome\User
  Data`, `Default`, `Profile N`, or equivalents).
- Use Playwright's bundled Chromium (headless preferred) with its own
  isolated context or a throwaway profile directory (e.g.
  `.tmp/markmyass-playwright-profile/` or a temp dir). Example:

  ```python
  from playwright.sync_api import sync_playwright
  with sync_playwright() as p:
      browser = p.chromium.launch()          # isolated, project-owned
      page = browser.new_page(viewport={"width": 1400, "height": 900})
      page.goto("http://127.0.0.1:<port>/")
      page.screenshot(path="shot.png", full_page=True)
      browser.close()                        # closes ONLY this instance
  ```

- When a dev server must be stopped, kill it by ITS specific PID (from
  launch output or the port's owning PID), never by image name.

## Environment quirks worth knowing

- Headless Chromium in this environment defaults to
  `prefers-color-scheme: dark` AND `prefers-reduced-motion: reduce`;
  force them explicitly when testing light mode or animations
  (Playwright: `color_scheme="light"`, `reduced_motion="no-preference"`
  on the context).
- The web app caches `index.html` and rendered article pages at server
  startup — restart the server (fresh port) after editing them.
