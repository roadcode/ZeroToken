"""
Adaptive element locating: fingerprint extraction and similarity-based relocation.
"""

from typing import Any, Dict, Optional

# Script run in browser to build fingerprint from an element
_FINGERPRINT_SCRIPT = """
(el) => {
  if (!el || !el.tagName) return null;
  const parent = el.parentElement;
  const parentData = parent ? {
    tag: (parent.tagName || '').toLowerCase(),
    attrs: Object.fromEntries([...parent.attributes].map(a => [a.name, a.value])),
    text: (parent.textContent || '').trim().slice(0, 500)
  } : { tag: '', attrs: {}, text: '' };
  const selfData = {
    tag: (el.tagName || '').toLowerCase(),
    attrs: Object.fromEntries([...el.attributes].map(a => [a.name, a.value])),
    text: (el.textContent || '').trim().slice(0, 500),
    siblings: parent ? [...parent.children].filter(c => c !== el).map(c => (c.tagName || '').toLowerCase()) : [],
    path: (() => {
      const p = [];
      let n = el;
      while (n && n !== document.body) {
        p.unshift((n.tagName || '').toLowerCase());
        n = n.parentElement;
      }
      return p;
    })()
  };
  return { parent: parentData, self: selfData };
}
"""


async def extract_fingerprint(element_handle: Any, page: Any) -> Optional[Dict[str, Any]]:
    """
    Extract a fingerprint dict from a Playwright ElementHandle.
    Uses in-page JS to read parent/self tag, attrs, text, siblings, path.
    Returns None if evaluation fails or element is invalid.
    """
    try:
        result = await element_handle.evaluate(_FINGERPRINT_SCRIPT)
        return result
    except Exception:
        return None
