"""
Motor de compatibilidad del PC Builder por piezas. Reglas deterministas de
hardware (sin IA): socket CPU<->placa, generacion de RAM<->placa, wattage de
fuente<->consumo estimado de la GPU. Mismo input, mismo resultado, siempre.
"""
from .models import ComponentType, Product

PSU_SAFETY_MARGIN_WATTS = 100  # margen extra sobre el minimo recomendado por el fabricante de la GPU

STEPS = [
    ("cpu", ComponentType.CPU, "Procesador"),
    ("motherboard", ComponentType.MOTHERBOARD, "Placa Madre"),
    ("ram", ComponentType.RAM, "Memoria RAM"),
    ("gpu", ComponentType.GPU, "Tarjeta de Video"),
    ("psu", ComponentType.PSU, "Fuente de Poder"),
    ("case", ComponentType.CASE, "Gabinete"),
    ("storage", ComponentType.STORAGE, "Almacenamiento"),
    ("cooler", ComponentType.COOLER, "Refrigeracion"),
]


def compatible_queryset(step_key, selections: dict):
    """
    selections: dict con ids de productos ya elegidos para pasos previos,
    ej. {"cpu": 12, "motherboard": 30}
    Devuelve el queryset de productos validos para el `step_key` dado lo ya
    elegido, en stock.
    """
    ctype = dict((k, t) for k, t, _ in STEPS)[step_key]
    qs = Product.objects.filter(component_type=ctype, in_stock=True)

    cpu = _get_selected(selections, "cpu")
    motherboard = _get_selected(selections, "motherboard")
    gpu = _get_selected(selections, "gpu")

    if step_key == "motherboard" and cpu and cpu.specs.get("socket"):
        qs = [p for p in qs if p.specs.get("socket") == cpu.specs.get("socket")]
        return qs

    if step_key == "ram":
        # solo DIMM (formato escritorio); el catalogo tambien tiene SODIMM de notebook,
        # fisicamente incompatible con una placa madre de escritorio.
        qs = [p for p in qs if p.specs.get("form_factor") == "DIMM"]
        if motherboard and motherboard.specs.get("ram_type"):
            qs = [p for p in qs if p.specs.get("ram_type") == motherboard.specs.get("ram_type")]
        return qs

    if step_key == "psu" and gpu and gpu.specs.get("recommended_psu_watts"):
        min_watts = gpu.specs["recommended_psu_watts"]
        qs = [p for p in qs if (p.specs.get("watts") or 0) >= min_watts]
        return qs

    return list(qs)


def _get_selected(selections, key):
    pid = selections.get(key)
    if not pid:
        return None
    try:
        return Product.objects.get(pk=pid, component_type=dict((k, t) for k, t, _ in STEPS)[key])
    except Product.DoesNotExist:
        return None


def build_summary(selections: dict):
    """Arma el resumen del build: items, precio total, advertencias de compatibilidad."""
    items = []
    total = 0
    warnings = []

    resolved = {}
    for key, ctype, label in STEPS:
        pid = selections.get(key)
        if not pid:
            continue
        try:
            product = Product.objects.get(pk=pid, component_type=ctype)
        except Product.DoesNotExist:
            continue
        resolved[key] = product
        price = float(product.price_low or 0)
        total += price
        items.append({
            "step": key,
            "label": label,
            "name": product.name,
            "price": price,
            "url": product.source_url,
            "image": product.image_url,
        })

    cpu, mobo = resolved.get("cpu"), resolved.get("motherboard")
    if cpu and mobo and cpu.specs.get("socket") and mobo.specs.get("socket"):
        if cpu.specs["socket"] != mobo.specs["socket"]:
            warnings.append(
                f"El procesador usa socket {cpu.specs['socket']} y la placa madre es {mobo.specs['socket']}: no son compatibles."
            )

    gpu, psu = resolved.get("gpu"), resolved.get("psu")
    if gpu and psu and gpu.specs.get("recommended_psu_watts") and psu.specs.get("watts"):
        min_watts = gpu.specs["recommended_psu_watts"]
        if psu.specs["watts"] < min_watts:
            warnings.append(
                f"La {gpu.name} recomienda una fuente de {min_watts}W o más; la fuente elegida entrega {psu.specs['watts']}W."
            )

    return {"items": items, "total": total, "warnings": warnings, "complete": len(items) == len(STEPS)}
