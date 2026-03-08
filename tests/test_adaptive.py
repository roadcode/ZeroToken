"""Tests for adaptive fingerprint extraction."""

import pytest

from zerotoken.adaptive import extract_fingerprint

# Minimal HTML for fingerprint extraction
SAMPLE_HTML = """
<!DOCTYPE html>
<html><body>
<div class="container">
  <section class="products">
    <article class="product" id="p1" data-id="1">
      <h3>Product 1</h3>
      <p class="description">Description 1</p>
    </article>
  </section>
</div>
</body></html>
"""


@pytest.mark.asyncio
async def test_extract_fingerprint_structure():
    """Extract fingerprint from a real element and assert structure."""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.set_content(SAMPLE_HTML)
        el = await page.query_selector("#p1")
        assert el is not None

        fp = await extract_fingerprint(el, page)
        await browser.close()

    assert fp is not None
    assert "parent" in fp
    assert "self" in fp
    assert fp["parent"]["tag"] == "section"
    assert fp["self"]["tag"] == "article"
    assert fp["self"]["attrs"].get("id") == "p1"
    assert "Product 1" in (fp["self"]["text"] or "")
    assert isinstance(fp["self"]["siblings"], list)
    assert isinstance(fp["self"]["path"], list)
    assert "article" in fp["self"]["path"]
