import requests
import xml.etree.ElementTree as ET
from collections import Counter
import json

NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"

resp = requests.get("https://invasiongamer.com/sitemap_1.xml", timeout=30)
root = ET.fromstring(resp.content)

urls = []
for url_el in root.findall(f"{NS}url"):
    loc = url_el.findtext(f"{NS}loc")
    priority = url_el.findtext(f"{NS}priority")
    changefreq = url_el.findtext(f"{NS}changefreq")
    lastmod = url_el.findtext(f"{NS}lastmod")
    urls.append({"loc": loc, "priority": priority, "changefreq": changefreq, "lastmod": lastmod})

with open("data/sitemap_urls.json", "w", encoding="utf-8") as f:
    json.dump(urls, f, ensure_ascii=False, indent=2)

print(f"Total URLs: {len(urls)}")
print(Counter(u["priority"] for u in urls))
print("Saved to data/sitemap_urls.json")
