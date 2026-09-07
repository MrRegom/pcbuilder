"""
Scraper respetuoso para invasiongamer.com (Jumpseller store).
Fuente de URLs: sitemap_1.xml (permitido por robots.txt).
Extrae el JSON-LD (schema.org Product) embebido en cada ficha de producto:
no se parsea HTML visual, solo datos estructurados que la propia tienda publica
para buscadores/agentes.
"""
import html
import json
import re
import sys
import time
from pathlib import Path

import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HEADERS = {
    "User-Agent": "InvasionGamerCatalogDemo/1.0 (+demo interno para propuesta de mejora de sitio; contacto: mr.reinaldo.g@gmail.com)"
}
DELAY_SECONDS = 0.6  # scraping respetuoso: no golpear el servidor

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SITEMAP_FILE = DATA_DIR / "sitemap_urls.json"
OUTPUT_FILE = DATA_DIR / "raw_products.json"

EXCLUDE_PATH_KEYWORDS = [
    "politica-de-", "terminos-y-condiciones", "sobre-nosotros", "blog",
    "garantia-swop", "servicios$",
]


def is_product_url(entry):
    return entry["priority"] == "0.8"


def extract_ldjson_objects(page_html):
    objs = []
    for m in re.finditer(r'<script type="application/ld\+json">([\s\S]*?)</script>', page_html):
        raw = m.group(1).strip()
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, list):
            objs.extend(parsed)
        else:
            objs.append(parsed)
    return objs


def meta_content(page_html, attr_name, attr_value):
    m = re.search(
        rf'<meta[^>]+{attr_name}=["\']' + re.escape(attr_value) + r'["\'][^>]+content=["\']([^"\']*)["\']',
        page_html,
    )
    return html.unescape(m.group(1)) if m else None


def scrape_via_meta_fallback(url, page_html):
    """
    Algunos productos (monitores, notebooks) traen un caracter de comilla (") sin
    escapar dentro del nombre (ej: 27") porque Jumpseller no lo sanitiza al generar
    el JSON-LD -> el bloque queda invalido. Es un bug real del sitio (afecta rich
    snippets de Google Shopping para esos productos). Como respaldo, se usan los
    meta tags Open Graph / product:*, que si sanean el HTML correctamente.
    """
    images = re.findall(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']*)["\']', page_html)
    price = meta_content(page_html, "property", "product:price:amount")
    original_price = meta_content(page_html, "property", "product:original_price:amount")
    availability = meta_content(page_html, "property", "product:availability")

    return {
        "url": url,
        "name": meta_content(page_html, "property", "og:title"),
        "image": images[0] if images else None,
        "description": meta_content(page_html, "name", "description"),
        "brand": None,
        "category": None,
        "breadcrumb": [],
        "price_low": price,
        "price_high": original_price or price,
        "currency": meta_content(page_html, "property", "product:price:currency") or "CLP",
        "availability": "http://schema.org/InStock" if availability == "instock" else availability,
        "rating_value": None,
        "rating_count": None,
        "extraction_method": "meta_fallback",
    }


def scrape_product(url):
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    page_html = resp.text
    objs = extract_ldjson_objects(page_html)

    product = next((o for o in objs if o.get("@type") == "Product"), None)
    breadcrumb = next((o for o in objs if o.get("@type") == "BreadcrumbList"), None)

    if not product:
        fallback = scrape_via_meta_fallback(url, page_html)
        return fallback if fallback["name"] else None

    crumbs = []
    if breadcrumb:
        items = sorted(breadcrumb.get("itemListElement", []), key=lambda i: i.get("position", 0))
        crumbs = [i["item"]["name"] for i in items if "item" in i and "name" in i["item"]]

    offers = product.get("offers", {}) or {}

    return {
        "url": url,
        "name": html.unescape(product.get("name") or ""),
        "image": product.get("image"),
        "description": html.unescape(product.get("description") or ""),
        "brand": (product.get("brand") or {}).get("name"),
        "category": product.get("category"),
        "breadcrumb": crumbs,
        "price_low": offers.get("lowPrice") or offers.get("price"),
        "price_high": offers.get("highPrice") or offers.get("price"),
        "currency": offers.get("priceCurrency"),
        "availability": offers.get("availability"),
        "rating_value": (product.get("aggregateRating") or {}).get("ratingValue"),
        "rating_count": (product.get("aggregateRating") or {}).get("reviewCount"),
        "extraction_method": "ld+json",
    }


def main():
    with open(SITEMAP_FILE, encoding="utf-8") as f:
        entries = json.load(f)

    product_entries = [e for e in entries if is_product_url(e)]
    print(f"Encontradas {len(product_entries)} URLs de producto (priority=0.8)")

    results = []
    errors = []
    for i, entry in enumerate(product_entries, 1):
        url = entry["loc"]
        try:
            data = scrape_product(url)
            if data:
                results.append(data)
                print(f"[{i}/{len(product_entries)}] OK  {data['name'][:70]}")
            else:
                errors.append(url)
                print(f"[{i}/{len(product_entries)}] SIN JSON-LD Product: {url}")
        except Exception as exc:
            errors.append(url)
            print(f"[{i}/{len(product_entries)}] ERROR {url}: {exc}")
        time.sleep(DELAY_SECONDS)

    DATA_DIR.mkdir(exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\nGuardados {len(results)} productos en {OUTPUT_FILE}")
    if errors:
        print(f"{len(errors)} URLs fallaron: {errors}")


if __name__ == "__main__":
    main()
