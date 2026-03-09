"""
Stealth mode: launch args and init script to reduce automation detection.
Used when controller.start(stealth=True).
"""

# Launch args to disable common automation indicators (Chromium)
STEALTH_LAUNCH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-automation",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-infobars",
    "--window-size=1920,1080",
]

# Init script run before any page script: mask navigator.webdriver and common checks.
# Runs in browser context; must be valid JS.
STEALTH_INIT_SCRIPT = """
(() => {
  try {
    Object.defineProperty(navigator, 'webdriver', {
      get: () => undefined,
      configurable: true,
      enumerable: true
    });
  } catch (e) {}
  try {
    if (window.chrome && window.chrome.runtime) {} else {
      window.chrome = { runtime: {} };
    }
  } catch (e) {}
  try {
    if (!navigator.plugins || navigator.plugins.length === 0) {
    }
  } catch (e) {}
})();
"""

# Realistic Chrome UA (Windows, recent Chromium)
DEFAULT_STEALTH_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
