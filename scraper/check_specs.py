"""Chequeo rapido de cobertura del motor de reglas contra el catalogo real ya cargado en la BD."""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
import django
django.setup()

from catalog.models import ComponentType, Product

for ctype, label in ComponentType.choices:
    qs = Product.objects.filter(component_type=ctype)
    if not qs.exists():
        continue
    print(f"\n=== {label} ({qs.count()}) ===")
    for p in qs:
        print(f"  {p.name[:65]:65s} specs={p.specs}")
