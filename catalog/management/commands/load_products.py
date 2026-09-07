import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.core.management.base import BaseCommand

from catalog.models import Product
from catalog.spec_parser import classify_component_type, parse_specs

DATA_FILE = Path(__file__).resolve().parent.parent.parent.parent / "data" / "raw_products.json"


def to_decimal(value):
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


class Command(BaseCommand):
    help = "Carga data/raw_products.json (scrapeado de invasiongamer.com) a la base local y aplica el motor de reglas de clasificacion/specs."

    def handle(self, *args, **options):
        with open(DATA_FILE, encoding="utf-8") as f:
            raw_products = json.load(f)

        created, updated = 0, 0
        for item in raw_products:
            if not item.get("name"):
                continue

            component_type = classify_component_type(item["name"], item.get("breadcrumb") or [])
            specs = parse_specs(component_type, item["name"], item.get("description") or "")

            obj, was_created = Product.objects.update_or_create(
                source_url=item["url"],
                defaults={
                    "name": item["name"],
                    "brand": item.get("brand") or "",
                    "description": item.get("description") or "",
                    "image_url": item.get("image") or "",
                    "breadcrumb": item.get("breadcrumb") or [],
                    "raw_category": item.get("category") or "",
                    "price_low": to_decimal(item.get("price_low")),
                    "price_high": to_decimal(item.get("price_high")),
                    "currency": item.get("currency") or "CLP",
                    "in_stock": (item.get("availability") or "").endswith("InStock"),
                    "rating_value": to_decimal(item.get("rating_value")),
                    "rating_count": item.get("rating_count") or None,
                    "extraction_method": item.get("extraction_method") or "",
                    "component_type": component_type,
                    "specs": specs,
                },
            )
            created += was_created
            updated += not was_created

        self.stdout.write(self.style.SUCCESS(
            f"Listo. {created} productos creados, {updated} actualizados. Total en BD: {Product.objects.count()}"
        ))
