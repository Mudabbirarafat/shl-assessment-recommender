"""
Scraper for the SHL Product Catalog (Individual Test Solutions only).

This script is meant to be run in an environment with normal internet access
(it was authored in a sandbox without outbound network access, so it has not
been executed end-to-end here — run it locally / in CI before relying on it).

The catalog page (https://www.shl.com/solutions/products/product-catalog/) is
paginated and filtered with query params:
  - type=1  -> Individual Test Solutions   (what we want)
  - type=2  -> Pre-packaged Job Solutions  (out of scope per the task)
  - start=N -> pagination offset, 12 results per page

Because the table is rendered with some client-side JS, prefer Playwright
(handles JS) over plain requests if results look incomplete; a requests/
BeautifulSoup fallback is included for speed when it works.

Usage:
    pip install requests beautifulsoup4 playwright
    playwright install chromium
    python scrape_catalog.py --out ../data/catalog.json
"""

import argparse
import json
import re
import time
from urllib.parse import urljoin

BASE = "https://www.shl.com"
CATALOG_URL = "https://www.shl.com/solutions/products/product-catalog/"

TEST_TYPE_LABELS = {
    "A": "Ability & Aptitude",
    "B": "Biodata & Situational Judgement",
    "C": "Competencies",
    "D": "Development & 360",
    "E": "Assessment Exercises",
    "K": "Knowledge & Skills",
    "P": "Personality & Behavior",
    "S": "Simulations",
}


def scrape_with_playwright(max_pages: int = 60):
    """Drive a headless browser so client-side pagination/filtering renders."""
    from playwright.sync_api import sync_playwright

    items = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        start = 0
        while start < max_pages * 12:
            url = f"{CATALOG_URL}?start={start}&type=1"
            page.goto(url, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(800)
            rows = page.query_selector_all("table tr, .product-catalogue__row")
            if not rows:
                break
            found_this_page = 0
            for row in rows:
                link_el = row.query_selector("a")
                if not link_el:
                    continue
                href = link_el.get_attribute("href")
                name = link_el.inner_text().strip()
                if not href or not name:
                    continue
                full_url = urljoin(BASE, href)
                type_cells = row.query_selector_all(".catalogue__circle, .product-catalogue__key")
                type_codes = sorted({c.inner_text().strip() for c in type_cells if c.inner_text().strip()})
                items.append({
                    "name": name,
                    "url": full_url,
                    "test_type": type_codes,
                })
                found_this_page += 1
            if found_this_page == 0:
                break
            start += 12
            time.sleep(0.5)
        browser.close()
    return _dedupe(items)


def scrape_with_requests(max_pages: int = 60):
    """Fallback path; only works if the listing is present in static HTML."""
    import requests
    from bs4 import BeautifulSoup

    items = []
    for page_idx in range(max_pages):
        start = page_idx * 12
        url = f"{CATALOG_URL}?start={start}&type=1"
        resp = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code != 200:
            break
        soup = BeautifulSoup(resp.text, "html.parser")
        rows = soup.select("table tr") or soup.select(".product-catalogue__row")
        if not rows:
            break
        found_this_page = 0
        for row in rows:
            a = row.find("a")
            if not a or not a.get("href"):
                continue
            name = a.get_text(strip=True)
            if not name:
                continue
            full_url = urljoin(BASE, a["href"])
            items.append({"name": name, "url": full_url, "test_type": []})
            found_this_page += 1
        if found_this_page == 0:
            break
        time.sleep(0.3)
    return _dedupe(items)


def _dedupe(items):
    seen = set()
    out = []
    for item in items:
        if item["url"] in seen:
            continue
        seen.add(item["url"])
        out.append(item)
    return out


def enrich_descriptions(items):
    """Optionally visit each product page to pull description / duration /
    job level metadata. Skipped by default since it is slow (one request per
    item); enable with --enrich.
    """
    import requests
    from bs4 import BeautifulSoup

    for item in items:
        try:
            resp = requests.get(item["url"], timeout=20, headers={"User-Agent": "Mozilla/5.0"})
            soup = BeautifulSoup(resp.text, "html.parser")
            desc_el = soup.select_one(".product-catalogue-detail__description, main p")
            if desc_el:
                item["description"] = desc_el.get_text(strip=True)
            duration_match = re.search(r"(\d+)\s*minutes", soup.get_text())
            if duration_match:
                item["duration_minutes"] = int(duration_match.group(1))
            time.sleep(0.3)
        except Exception as e:
            print(f"  ! failed to enrich {item['url']}: {e}")
    return items


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="../data/catalog.json")
    parser.add_argument("--enrich", action="store_true", help="Fetch each product page for description/duration")
    parser.add_argument("--engine", choices=["playwright", "requests"], default="playwright")
    args = parser.parse_args()

    print(f"Scraping SHL catalog (Individual Test Solutions, type=1) via {args.engine}...")
    if args.engine == "playwright":
        items = scrape_with_playwright()
    else:
        items = scrape_with_requests()

    print(f"Found {len(items)} individual test solutions.")

    if args.enrich:
        print("Enriching with descriptions/duration (this is slow)...")
        items = enrich_descriptions(items)

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2, ensure_ascii=False)
    print(f"Wrote {len(items)} items to {args.out}")


if __name__ == "__main__":
    main()
