from django.db.models import Count, Max, Min, Q
from django.http import JsonResponse
from django.shortcuts import render

from . import compat, nlp_rules
from .models import ComponentType, Product

PAGE_SIZE = 24

SEARCHABLE_TYPES = [
    (ComponentType.PREBUILT_PC, "PCs Armados"),
    (ComponentType.NOTEBOOK, "Notebooks"),
    (ComponentType.CPU, "Procesadores"),
    (ComponentType.MOTHERBOARD, "Placas Madre"),
    (ComponentType.RAM, "Memorias RAM"),
    (ComponentType.GPU, "Tarjetas de Video"),
    (ComponentType.PSU, "Fuentes de Poder"),
    (ComponentType.CASE, "Gabinetes"),
    (ComponentType.COOLER, "Refrigeracion"),
    (ComponentType.STORAGE, "Almacenamiento"),
    (ComponentType.MONITOR, "Monitores"),
    (ComponentType.PERIPHERAL, "Accesorios y Perifericos"),
]


def _apply_filters(qs, params):
    q = params.get("q", "").strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(brand__icontains=q) | Q(description__icontains=q))

    ctype = params.get("tipo")
    if ctype:
        qs = qs.filter(component_type=ctype)

    brand = params.get("marca")
    if brand:
        qs = qs.filter(brand__iexact=brand)

    price_min = params.get("precio_min")
    if price_min:
        qs = qs.filter(price_low__gte=price_min)

    price_max = params.get("precio_max")
    if price_max:
        qs = qs.filter(price_low__lte=price_max)

    if params.get("stock") == "1":
        qs = qs.filter(in_stock=True)

    sort = params.get("orden", "relevancia")
    sort_map = {
        "precio_asc": "price_low",
        "precio_desc": "-price_low",
        "nombre": "name",
    }
    if sort in sort_map:
        qs = qs.order_by(sort_map[sort])
    else:
        qs = qs.order_by("-rating_value", "name")

    return qs


def search(request):
    price_bounds = Product.objects.aggregate(min=Min("price_low"), max=Max("price_low"))
    raw_brands = Product.objects.exclude(brand="").values_list("brand", flat=True).distinct()
    # el catalogo trae la misma marca escrita de varias formas (ej. "Gigabyte" / "GIGABYTE" /
    # "Royal Kludge" / "Royal Klugde"); se deduplica por texto normalizado para el filtro,
    # eligiendo la variante mas frecuente como forma a mostrar. El filtro en si sigue siendo
    # case-insensitive (brand__iexact), asi que cualquier variante elegida matchea igual.
    seen = {}
    for b in raw_brands:
        key = b.strip().lower()
        seen.setdefault(key, b.strip())
    brands = sorted(seen.values(), key=str.lower)

    context = {
        "types": SEARCHABLE_TYPES,
        "brands": brands,
        "price_min": price_bounds["min"] or 0,
        "price_max": price_bounds["max"] or 0,
    }
    return render(request, "catalog/search.html", context)


def api_products(request):
    qs = _apply_filters(Product.objects.all(), request.GET)
    total = qs.count()

    try:
        page = max(1, int(request.GET.get("page", 1)))
    except ValueError:
        page = 1
    start = (page - 1) * PAGE_SIZE
    items = qs[start:start + PAGE_SIZE]

    facets = list(
        Product.objects.values("component_type").annotate(n=Count("id")).order_by("-n")
    )

    return JsonResponse({
        "total": total,
        "page": page,
        "page_size": PAGE_SIZE,
        "has_next": start + PAGE_SIZE < total,
        "facets": facets,
        "results": [_serialize(p) for p in items],
    })


def _serialize(p: Product):
    return {
        "id": p.id,
        "name": p.name,
        "brand": p.brand,
        "component_type": p.component_type,
        "component_type_label": p.get_component_type_display(),
        "price_low": float(p.price_low) if p.price_low is not None else None,
        "price_high": float(p.price_high) if p.price_high is not None else None,
        "discount_pct": p.discount_pct,
        "in_stock": p.in_stock,
        "image_url": p.image_url,
        "url": p.source_url,
        "specs": p.specs,
        "rating_value": float(p.rating_value) if p.rating_value is not None else None,
        "rating_count": p.rating_count,
    }


def builder(request):
    steps = [{"key": k, "label": label} for k, _, label in compat.STEPS]
    return render(request, "catalog/builder.html", {"steps": steps})


def api_builder_options(request):
    step_key = request.GET.get("step")
    valid_keys = {k for k, _, _ in compat.STEPS}
    if step_key not in valid_keys:
        return JsonResponse({"error": "step invalido"}, status=400)

    selections = {k: request.GET.get(k) for k, _, _ in compat.STEPS if request.GET.get(k)}
    options = compat.compatible_queryset(step_key, selections)
    return JsonResponse({"step": step_key, "options": [_serialize(p) for p in options]})


def api_builder_summary(request):
    selections = {k: request.GET.get(k) for k, _, _ in compat.STEPS if request.GET.get(k)}
    return JsonResponse(compat.build_summary(selections))


USE_CASE_GPU_HINTS = {
    "oficina": [],
    "gaming_1080p": ["5050", "5060", "3050", "9060"],
    "gaming_1440p": ["5060ti", "5070", "9070"],
    "gaming_4k": ["5070ti", "5080", "5090", "9070xt"],
}


def _rank_prebuilt(budget, use_case, limit=3):
    qs = Product.objects.filter(component_type=ComponentType.PREBUILT_PC, in_stock=True)
    candidates = list(qs)

    def score(p):
        price = float(p.price_low or 0)
        if price <= 0:
            return -1e9
        if budget:
            price_fit = -abs(price - budget)
        elif use_case == "oficina":
            # sin GPU que priorizar y sin presupuesto declarado: la opción más
            # barata que sirva es la recomendación por defecto mas razonable
            price_fit = -price
        else:
            price_fit = 0
        gpu_models = [g.lower() for g in (p.specs.get("gpu_models") or [])]
        hint_bonus = 0
        for hint in USE_CASE_GPU_HINTS.get(use_case, []):
            if any(hint in g for g in gpu_models):
                hint_bonus = 200000
                break
        over_budget_penalty = -500000 if budget and price > budget * 1.15 else 0
        return price_fit + hint_bonus + over_budget_penalty

    ranked = sorted(candidates, key=score, reverse=True)[:limit]

    results = []
    for p in ranked:
        price = float(p.price_low or 0)
        reasons = []
        if budget:
            diff = price - budget
            if abs(diff) <= budget * 0.1:
                reasons.append("su precio calza con tu presupuesto")
            elif diff < 0:
                reasons.append("queda bajo tu presupuesto, dejando margen para accesorios")
            else:
                reasons.append("se pasa un poco de tu presupuesto pero rinde mejor")
        elif use_case == "oficina":
            reasons.append("es de las opciones más económicas en stock: para oficina no hace falta pagar por una GPU gamer")

        gpu_models = p.specs.get("gpu_models") or []
        if gpu_models and use_case != "oficina":
            reasons.append(f"trae {', '.join(gpu_models)}, acorde a {use_case.replace('_', ' ')}")
        item = _serialize(p)
        item["reason"] = "; ".join(reasons) if reasons else "buena relación precio/rendimiento disponible en stock"
        results.append(item)
    return results


def api_recommend(request):
    try:
        budget = float(request.GET.get("presupuesto", 0))
    except ValueError:
        budget = 0
    use_case = request.GET.get("uso", "gaming_1080p")

    results = _rank_prebuilt(budget, use_case)
    return JsonResponse({"results": results, "budget": budget, "use_case": use_case})


def api_recommend_text(request):
    """
    Recomendador por texto libre (ej: 'quiero jugar fortnite, tengo 500 lucas').
    Sigue sin ser IA: nlp_rules.interpret() detecta juego/presupuesto por
    diccionario y regex, no por un modelo de lenguaje. El resultado explica
    exactamente que detecto para que no sea una caja negra.
    """
    text = request.GET.get("texto", "").strip()
    if not text:
        return JsonResponse({"error": "texto vacío"}, status=400)

    interpretation = nlp_rules.interpret(text)
    budget = interpretation["budget"] or 0
    use_case = interpretation["use_case"]

    results = _rank_prebuilt(budget, use_case)
    return JsonResponse({
        "results": results,
        "budget": budget,
        "use_case": use_case,
        "game": interpretation["game"],
        "notes": interpretation["notes"],
    })
