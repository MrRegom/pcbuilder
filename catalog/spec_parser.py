"""
Motor de reglas (sin IA) para estructurar el catalogo.

Jumpseller solo entrega titulo + descripcion en texto libre; ningun campo de
specs (socket, VRAM, wattage, etc.) viene estructurado. Este modulo clasifica
cada producto por tipo de componente y extrae atributos tecnicos con
expresiones regulares y tablas de referencia de hardware conocidas, para
habilitar filtros facetados y el motor de compatibilidad del PC Builder.

Es deliberadamente determinista: mismo texto de entrada -> misma salida
siempre. Nada de LLMs ni de inferencia probabilistica.
"""
import re
from .models import ComponentType

# ---------------------------------------------------------------------------
# Tablas de referencia de hardware (conocimiento general, no viene del scrape)
# ---------------------------------------------------------------------------

# socket por modelo de CPU (substring en minusculas -> socket)
CPU_SOCKET_MAP = {
    "5300g": "AM4", "5500": "AM4", "5600": "AM4", "5700x": "AM4",
    "7600x3d": "AM5", "7600x": "AM5", "7600": "AM5",
    "7700x3d": "AM5", "7700x": "AM5",
    "7800x3d": "AM5",
    "8400f": "AM5", "8500g": "AM5", "8700f": "AM5",
    "9600x": "AM5", "9700x": "AM5", "9800x3d": "AM5",
    "9900x": "AM5", "9950x3d": "AM5",
    "12400f": "LGA1700",
    "245k": "LGA1851", "245kf": "LGA1851",
}

# chipset de placa madre (substring -> (socket, generacion ram por defecto))
CHIPSET_SOCKET_MAP = {
    "a620": ("AM5", "DDR5"),
    "b650": ("AM5", "DDR5"),
    "b850": ("AM5", "DDR5"),
    "x670": ("AM5", "DDR5"),
    "x870": ("AM5", "DDR5"),
    "b550": ("AM4", "DDR4"),
    "a520": ("AM4", "DDR4"),
    "h610": ("LGA1700", "DDR4"),
    "b660": ("LGA1700", "DDR4"),
    "b760": ("LGA1700", "DDR4"),
    "z690": ("LGA1700", "DDR5"),
    "z790": ("LGA1700", "DDR5"),
}

# GPU -> wattage de fuente recomendado por el fabricante (referencial)
GPU_RECOMMENDED_PSU_WATTS = [
    (r"rtx.{0,3}5090", 1000), (r"rtx.{0,3}5080", 850),
    (r"rtx.{0,3}5070.{0,3}ti", 750), (r"rtx.{0,3}5070", 650),
    (r"rtx.{0,3}5060.{0,3}ti", 600), (r"rtx.{0,3}5060", 550),
    (r"rtx.{0,3}5050", 550), (r"rtx.{0,3}3050", 550),
    (r"rx.{0,3}9070.{0,3}xt", 750), (r"rx.{0,3}9070", 700),
    (r"rx.{0,3}9060.{0,3}xt", 650),
]

CPU_BRAND_KEYWORDS = [("amd", "AMD"), ("ryzen", "AMD"), ("intel", "Intel"), ("core ultra", "Intel")]
GPU_BRAND_KEYWORDS = [("geforce", "NVIDIA"), ("rtx", "NVIDIA"), ("radeon", "AMD"), (" rx ", "AMD")]

RAM_TYPE_RE = re.compile(r"\bddr([45])\b", re.I)
RAM_CAPACITY_RE = re.compile(r"(\d+)\s*gb\b", re.I)
WATTAGE_RE = re.compile(r"(\d{3,4})\s*w\b", re.I)
EFFICIENCY_RE = re.compile(r"80\+?\s*(bronze|gold|silver|platinum|titanium)", re.I)
VRAM_RE = re.compile(r"(\d{1,2})\s*g(?:b|ddr\d?)?\b", re.I)
CORES_RE = re.compile(r"(\d+)\s*(?:n[uú]cleos|core)", re.I)
SCREEN_SIZE_RE = re.compile(r"(\d{2}(?:\.\d)?)\s*(?:\"|pulg|inch)", re.I)
REFRESH_RATE_RE = re.compile(r"(\d{2,3})\s*hz", re.I)
STORAGE_CAPACITY_RE = re.compile(r"(\d+)\s*(gb|tb)\b", re.I)
STORAGE_TYPE_RE = re.compile(r"\b(nvme|ssd|hdd|sata)\b", re.I)

TYPE_KEYWORDS = [
    (ComponentType.PREBUILT_PC, [r"^pc gamer", r"^pc core", r"^pc prime", r"^kit invader", r"^combo gamer"]),
    (ComponentType.NOTEBOOK, [r"notebook"]),
    (ComponentType.CPU, [r"^procesador", r"^procesdor"]),
    (ComponentType.MOTHERBOARD, [r"placa madre"]),
    (ComponentType.RAM, [r"memoria ram"]),
    (ComponentType.GPU, [r"tarjeta gr[aá]fica", r"tarjeta de video"]),
    (ComponentType.PSU, [r"fuente de poder"]),
    (ComponentType.CASE, [r"^gabinete"]),
    (ComponentType.COOLER, [r"^cooler", r"watercooling", r"thermalright"]),
    (ComponentType.STORAGE, [r"^ssd", r"almacenamiento"]),
    (ComponentType.MONITOR, [r"^monitor"]),
    (ComponentType.SERVICE, [r"^servicio"]),
    (ComponentType.PERIPHERAL, [
        r"teclado", r"mouse", r"aud[ií]fono", r"mousepad", r"silla", r"escritorio",
        r"micr[oó]fono", r"consola", r"webcam", r"router", r"adaptador",
    ]),
]


def classify_component_type(name: str, breadcrumb: list[str]) -> str:
    text = name.lower()
    crumbs = " ".join(breadcrumb).lower()

    for ctype, patterns in TYPE_KEYWORDS:
        for pat in patterns:
            if re.search(pat, text):
                return ctype

    # fallback: usar el breadcrumb si el nombre no dio pistas
    if "componentes" in crumbs and "video" in crumbs:
        return ComponentType.GPU
    if "procesador" in crumbs:
        return ComponentType.CPU
    if "placas madres" in crumbs:
        return ComponentType.MOTHERBOARD
    if "memorias ram" in crumbs:
        return ComponentType.RAM
    if "monitor" in crumbs:
        return ComponentType.MONITOR
    if "desktop" in crumbs:
        return ComponentType.PREBUILT_PC
    if "notebook" in crumbs:
        return ComponentType.NOTEBOOK
    if "accesorios" in crumbs or "perifericos" in crumbs:
        return ComponentType.PERIPHERAL
    return ComponentType.OTHER


def _find_brand(text_lower, keyword_pairs, default=""):
    for kw, brand in keyword_pairs:
        if kw in text_lower:
            return brand
    return default


def _lookup_socket_by_cpu(text_lower):
    for model, socket in CPU_SOCKET_MAP.items():
        if model in text_lower:
            return socket
    return None


def _lookup_chipset(text_lower):
    for chipset, (socket, ram_gen) in CHIPSET_SOCKET_MAP.items():
        if chipset in text_lower:
            return chipset.upper(), socket, ram_gen
    return None, None, None


def _lookup_gpu_psu_watts(text_lower):
    for pattern, watts in GPU_RECOMMENDED_PSU_WATTS:
        if re.search(pattern, text_lower):
            return watts
    return None


def parse_specs(component_type: str, name: str, description: str) -> dict:
    text = f"{name} {description}".lower()
    specs = {}

    if component_type == ComponentType.CPU:
        specs["brand"] = _find_brand(text, CPU_BRAND_KEYWORDS)
        specs["socket"] = _lookup_socket_by_cpu(text)
        m = CORES_RE.search(text)
        if m:
            specs["cores"] = int(m.group(1))

    elif component_type == ComponentType.MOTHERBOARD:
        specs["brand"] = _find_brand(text, [("asus", "ASUS"), ("gigabyte", "Gigabyte"), ("msi", "MSI")])
        chipset, socket, ram_gen = _lookup_chipset(text)
        specs["chipset"] = chipset
        specs["socket"] = socket
        m = RAM_TYPE_RE.search(text)
        specs["ram_type"] = f"DDR{m.group(1)}" if m else ram_gen

    elif component_type == ComponentType.RAM:
        m = RAM_TYPE_RE.search(text)
        specs["ram_type"] = f"DDR{m.group(1)}" if m else None
        m = RAM_CAPACITY_RE.search(text)
        specs["capacity_gb"] = int(m.group(1)) if m else None
        specs["form_factor"] = "SODIMM" if "sodim" in text else "DIMM"

    elif component_type == ComponentType.GPU:
        specs["brand"] = _find_brand(text, GPU_BRAND_KEYWORDS)
        m = VRAM_RE.search(text)
        specs["vram_gb"] = int(m.group(1)) if m else None
        specs["recommended_psu_watts"] = _lookup_gpu_psu_watts(text)

    elif component_type == ComponentType.PSU:
        m = WATTAGE_RE.search(text)
        specs["watts"] = int(m.group(1)) if m else None
        m = EFFICIENCY_RE.search(text)
        specs["efficiency"] = f"80+ {m.group(1).capitalize()}" if m else None
        specs["modular"] = "full modular" in text or "semi modular" in text

    elif component_type == ComponentType.STORAGE:
        m = STORAGE_CAPACITY_RE.search(text)
        specs["capacity_gb"] = int(m.group(1)) * (1024 if m.group(2).lower() == "tb" else 1) if m else None
        m = STORAGE_TYPE_RE.search(text)
        specs["storage_type"] = m.group(1).upper() if m else None

    elif component_type == ComponentType.MONITOR:
        m = SCREEN_SIZE_RE.search(text)
        specs["size_inch"] = float(m.group(1)) if m else None
        m = REFRESH_RATE_RE.search(text)
        specs["refresh_hz"] = int(m.group(1)) if m else None
        for res in ["4k", "qhd", "fhd"]:
            if res in text:
                specs["resolution"] = res.upper()
                break

    elif component_type in (ComponentType.PREBUILT_PC, ComponentType.NOTEBOOK):
        specs["cpu_brand"] = _find_brand(text, CPU_BRAND_KEYWORDS)
        specs["gpu_brand"] = _find_brand(text, GPU_BRAND_KEYWORDS)
        gpu_models = re.findall(r"(?:rtx|rx|gtx)\s?\™?\s?(\d{4}(?:\s?ti|\s?xt)?)", text)
        specs["gpu_models"] = sorted(set(re.sub(r"\s+", "", g).upper() for g in gpu_models))
        cpu_models = re.findall(r"ryzen\s?\™?\s?[3579]\s?(\d{3,5}\w{0,3})", text)
        specs["cpu_models"] = sorted(set(re.sub(r"\s+", "", c).upper() for c in cpu_models))

    return specs
