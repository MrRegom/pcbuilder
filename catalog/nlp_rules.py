"""
Interprete de texto libre para el armador ("quiero jugar fortnite, que pc tienes?").

Sigue siendo sin IA: no hay modelo de lenguaje ni llamada a ningun proveedor.
Es deteccion de patrones sobre un diccionario grande de juegos/usos conocidos +
parsing de montos en modismos chilenos (lucas, palos, kk) + tolerancia a typos
via coincidencia difusa de texto (difflib, libreria estandar de Python, no IA).

Todo el resultado es explicable: se le muestra al usuario exactamente que
detecto el sistema antes de recomendar, para que quede claro que no es una
caja negra ni puede "alucinar" specs que no existen en el catalogo real.
"""
import difflib
import re

# ---------------------------------------------------------------------------
# Catalogo de juegos conocidos. Cada entrada tiene un tier (mapea a los hints
# de GPU que ya usa la maquina de recomendacion) y una nota corta y honesta
# sobre que tan exigente es. Se agrupan por alias para no repetir el mismo
# juego muchas veces al escalar el diccionario.
# ---------------------------------------------------------------------------
GAME_CATALOG = [
    {"aliases": ["fortnite", "fornite", "fortnait", "fortnite battle royale"], "display": "Fortnite", "tier": "gaming_1080p",
     "note": "pide bastante CPU para FPS altos en modo competitivo, pero cualquier PC gamer actual lo mueve fluido"},
    {"aliases": ["valorant", "valornt", "valorants"], "display": "Valorant", "tier": "gaming_1080p",
     "note": "es muy liviano, cualquier PC gamer actual pasa los 240 FPS"},
    {"aliases": ["lol", "league of legends", "leage of legends"], "display": "League of Legends", "tier": "gaming_1080p",
     "note": "muy liviano, no necesita una GPU cara"},
    {"aliases": ["csgo", "cs go", "cs2", "cs 2", "counter strike", "counter"], "display": "Counter-Strike 2", "tier": "gaming_1080p",
     "note": "corre muy fluido, prioriza CPU rápido"},
    {"aliases": ["gta v", "gta 5", "gta5", "gta online", "grand theft auto v"], "display": "GTA V", "tier": "gaming_1440p",
     "note": "exigente en mundo abierto con detalles altos"},
    {"aliases": ["gta 6", "gta6", "gta vi"], "display": "GTA VI", "tier": "gaming_4k",
     "note": "se espera muy exigente gráfico, conviene ir arriba desde ya"},
    {"aliases": ["minecraft", "minecraf", "mine craft"], "display": "Minecraft", "tier": "gaming_1080p",
     "note": "liviano salvo con shaders o mods pesados"},
    {"aliases": ["cyberpunk", "cyberpunk 2077", "ciberpunk", "cyber punk"], "display": "Cyberpunk 2077", "tier": "gaming_4k",
     "note": "uno de los más exigentes gráficamente"},
    {"aliases": ["call of duty", "cod", "call of duty warzone", "warzone", "modern warfare", "black ops"],
     "display": "Call of Duty", "tier": "gaming_1440p", "note": "exigente, se beneficia de una GPU potente"},
    {"aliases": ["apex legends", "apex"], "display": "Apex Legends", "tier": "gaming_1080p", "note": "corre bien en gama media-alta"},
    {"aliases": ["elden ring", "eldenring"], "display": "Elden Ring", "tier": "gaming_1440p", "note": "exigente en mundo abierto"},
    {"aliases": ["red dead redemption 2", "red dead redemption", "rdr2", "rdr 2"], "display": "Red Dead Redemption 2",
     "tier": "gaming_4k", "note": "muy exigente gráfico"},
    {"aliases": ["fifa", "fc 24", "fc24", "fc 25", "fc25", "ea fc"], "display": "FIFA / EA FC", "tier": "gaming_1080p",
     "note": "liviano, corre bien en cualquier PC gamer"},
    {"aliases": ["roblox", "robux"], "display": "Roblox", "tier": "gaming_1080p", "note": "muy liviano, sirve casi cualquier equipo"},
    {"aliases": ["free fire", "freefire"], "display": "Free Fire", "tier": "gaming_1080p", "note": "muy liviano"},
    {"aliases": ["genshin impact", "genshin"], "display": "Genshin Impact", "tier": "gaming_1080p",
     "note": "moderado, corre bien en gama media"},
    {"aliases": ["honkai star rail", "honkai", "zenless zone zero", "zzz"], "display": "Honkai / Genshin-like gacha",
     "tier": "gaming_1080p", "note": "moderado, corre bien en gama media"},
    {"aliases": ["pubg", "pub g", "playerunknown"], "display": "PUBG", "tier": "gaming_1440p",
     "note": "exigente, se beneficia de una GPU potente"},
    {"aliases": ["dota 2", "dota"], "display": "Dota 2", "tier": "gaming_1080p", "note": "liviano"},
    {"aliases": ["overwatch", "overwatch 2", "ow2"], "display": "Overwatch 2", "tier": "gaming_1080p", "note": "liviano-moderado"},
    {"aliases": ["the sims", "los sims", "sims 4"], "display": "The Sims", "tier": "gaming_1080p", "note": "liviano"},
    {"aliases": ["among us"], "display": "Among Us", "tier": "gaming_1080p", "note": "muy liviano"},
    {"aliases": ["rainbow six", "rainbow six siege", "r6", "r6 siege"], "display": "Rainbow Six Siege", "tier": "gaming_1080p",
     "note": "liviano-moderado, prioriza FPS altos"},
    {"aliases": ["rocket league"], "display": "Rocket League", "tier": "gaming_1080p", "note": "muy liviano"},
    {"aliases": ["world of warcraft", "wow"], "display": "World of Warcraft", "tier": "gaming_1080p", "note": "moderado"},
    {"aliases": ["diablo 4", "diablo iv", "diablo"], "display": "Diablo IV", "tier": "gaming_1440p", "note": "moderado-exigente"},
    {"aliases": ["baldurs gate 3", "baldur's gate 3", "bg3"], "display": "Baldur's Gate 3", "tier": "gaming_1440p",
     "note": "exigente en escenas con muchos personajes"},
    {"aliases": ["hogwarts legacy", "hogwarts"], "display": "Hogwarts Legacy", "tier": "gaming_1440p", "note": "exigente gráfico"},
    {"aliases": ["helldivers 2", "helldivers"], "display": "Helldivers 2", "tier": "gaming_1440p", "note": "exigente en batallas grandes"},
    {"aliases": ["palworld"], "display": "Palworld", "tier": "gaming_1440p", "note": "moderado-exigente"},
    {"aliases": ["sea of thieves"], "display": "Sea of Thieves", "tier": "gaming_1440p", "note": "moderado"},
    {"aliases": ["terraria"], "display": "Terraria", "tier": "gaming_1080p", "note": "muy liviano"},
    {"aliases": ["stardew valley", "stardew"], "display": "Stardew Valley", "tier": "gaming_1080p", "note": "muy liviano"},
    {"aliases": ["ark survival", "ark"], "display": "ARK: Survival", "tier": "gaming_4k", "note": "muy exigente gráfico"},
    {"aliases": ["rust"], "display": "Rust", "tier": "gaming_1440p", "note": "exigente, sobre todo en CPU"},
    {"aliases": ["escape from tarkov", "tarkov"], "display": "Escape from Tarkov", "tier": "gaming_1440p", "note": "exigente en CPU"},
    {"aliases": ["star citizen"], "display": "Star Citizen", "tier": "gaming_4k", "note": "de los juegos más exigentes que existen"},
    {"aliases": ["marvel rivals"], "display": "Marvel Rivals", "tier": "gaming_1440p", "note": "moderado-exigente"},
    {"aliases": ["the finals"], "display": "The Finals", "tier": "gaming_1440p", "note": "exigente, escenarios destructibles"},
    {"aliases": ["naraka bladepoint", "naraka"], "display": "Naraka: Bladepoint", "tier": "gaming_1080p", "note": "moderado"},
    {"aliases": ["destiny 2", "destiny"], "display": "Destiny 2", "tier": "gaming_1440p", "note": "moderado-exigente"},
    {"aliases": ["halo infinite", "halo"], "display": "Halo Infinite", "tier": "gaming_1440p", "note": "moderado-exigente"},
    {"aliases": ["microsoft flight simulator", "flight simulator", "msfs"], "display": "Microsoft Flight Simulator",
     "tier": "gaming_4k", "note": "de los más exigentes en CPU y GPU"},
    {"aliases": ["cities skylines 2", "cities skylines"], "display": "Cities: Skylines", "tier": "gaming_1440p",
     "note": "exigente en CPU con ciudades grandes"},
    {"aliases": ["football manager", "fm24", "fm25"], "display": "Football Manager", "tier": "gaming_1080p",
     "note": "liviano gráfico, exigente en CPU con bases grandes"},
    {"aliases": ["age of empires", "aoe"], "display": "Age of Empires", "tier": "gaming_1080p", "note": "liviano-moderado"},
    {"aliases": ["starcraft", "starcraft 2"], "display": "StarCraft II", "tier": "gaming_1080p", "note": "liviano"},
    {"aliases": ["hearthstone"], "display": "Hearthstone", "tier": "gaming_1080p", "note": "muy liviano"},
    {"aliases": ["brawlhalla"], "display": "Brawlhalla", "tier": "gaming_1080p", "note": "muy liviano"},
    {"aliases": ["smite"], "display": "Smite", "tier": "gaming_1080p", "note": "liviano"},
    {"aliases": ["fall guys"], "display": "Fall Guys", "tier": "gaming_1080p", "note": "muy liviano"},
    {"aliases": ["it takes two"], "display": "It Takes Two", "tier": "gaming_1440p", "note": "moderado"},
    {"aliases": ["squad"], "display": "Squad", "tier": "gaming_1440p", "note": "exigente en CPU con muchos jugadores"},
    {"aliases": ["dayz"], "display": "DayZ", "tier": "gaming_1440p", "note": "exigente, sobre todo en CPU"},
    {"aliases": ["7 days to die"], "display": "7 Days to Die", "tier": "gaming_1080p", "note": "moderado"},
    {"aliases": ["valheim"], "display": "Valheim", "tier": "gaming_1080p", "note": "liviano-moderado"},
    {"aliases": ["lethal company"], "display": "Lethal Company", "tier": "gaming_1080p", "note": "muy liviano"},
    {"aliases": ["phasmophobia"], "display": "Phasmophobia", "tier": "gaming_1080p", "note": "liviano"},
    {"aliases": ["dead by daylight", "dbd"], "display": "Dead by Daylight", "tier": "gaming_1080p", "note": "moderado"},
    {"aliases": ["sons of the forest"], "display": "Sons of the Forest", "tier": "gaming_1440p", "note": "exigente gráfico"},
    {"aliases": ["subnautica"], "display": "Subnautica", "tier": "gaming_1080p", "note": "moderado"},
    {"aliases": ["no mans sky", "no man's sky"], "display": "No Man's Sky", "tier": "gaming_1440p", "note": "moderado-exigente"},
    {"aliases": ["satisfactory"], "display": "Satisfactory", "tier": "gaming_1440p", "note": "exigente con fábricas grandes"},
    {"aliases": ["factorio"], "display": "Factorio", "tier": "gaming_1080p", "note": "exigente en CPU, liviano en GPU"},
    {"aliases": ["witcher 3", "the witcher 3", "the witcher"], "display": "The Witcher 3", "tier": "gaming_1440p", "note": "moderado-exigente"},
    {"aliases": ["hades", "hades 2"], "display": "Hades", "tier": "gaming_1080p", "note": "muy liviano"},
    {"aliases": ["vampire survivors"], "display": "Vampire Survivors", "tier": "gaming_1080p", "note": "muy liviano"},
    {"aliases": ["balatro"], "display": "Balatro", "tier": "gaming_1080p", "note": "extremadamente liviano"},
    {"aliases": ["black myth wukong", "wukong"], "display": "Black Myth: Wukong", "tier": "gaming_4k", "note": "muy exigente gráfico"},
    {"aliases": ["silent hill 2"], "display": "Silent Hill 2 Remake", "tier": "gaming_1440p", "note": "exigente gráfico"},
    {"aliases": ["resident evil", "re4", "resident evil 4"], "display": "Resident Evil", "tier": "gaming_1440p", "note": "moderado-exigente"},
    {"aliases": ["forza horizon", "forza"], "display": "Forza Horizon", "tier": "gaming_1440p", "note": "exigente gráfico"},
    {"aliases": ["assassins creed", "assassin's creed", "ac valhalla", "ac shadows"], "display": "Assassin's Creed",
     "tier": "gaming_1440p", "note": "exigente gráfico"},
    {"aliases": ["nba 2k", "nba2k"], "display": "NBA 2K", "tier": "gaming_1080p", "note": "moderado"},
    {"aliases": ["wuthering waves"], "display": "Wuthering Waves", "tier": "gaming_1080p", "note": "moderado"},
    {"aliases": ["path of exile 2", "path of exile", "poe", "poe2"], "display": "Path of Exile", "tier": "gaming_1440p",
     "note": "exigente en CPU con muchos efectos en pantalla"},
]

_ALIAS_TO_GAME = {alias: game for game in GAME_CATALOG for alias in game["aliases"]}
_SORTED_GAME_ALIASES = sorted(_ALIAS_TO_GAME.keys(), key=len, reverse=True)

# usos no-gaming: se mapean al tier de recomendacion mas parecido en exigencia
USE_CASE_KEYWORDS = {
    "oficina": [
        "oficina", "trabajo", "trabajar", "estudiar", "estudio", "excel", "word", "powerpoint",
        "universidad", "colegio", "escuela", "tareas", "contabilidad", "ventas", "teletrabajo",
        "home office", "navegar", "netflix", "ver peliculas", "ver series", "programar", "codigo",
        "developer", "desarrollador", "python", "java", "javascript",
    ],
    "gaming_1440p": [
        "diseño", "diseno", "photoshop", "illustrator", "premiere", "davinci", "edicion de video",
        "editar video", "youtuber", "streamer", "streaming", "twitch", "obs", "autocad", "blender",
        "render", "arquitectura", "diseño 3d", "modelado 3d", "produccion musical", "ableton", "fl studio",
        # chilenismos de "algo bueno/potente" sin pedir explicitamente el tope de gama
        "pulento", "pulenta", "bakan", "bacan", "bacán", "la raja", "brigido", "brígido",
        "una maquina", "una máquina", "de show", "cuatico", "cuático", "que vuele",
        "potente", "buena maquina", "buena máquina", "que rinda", "para que no se pegue",
        "que no se cuelgue", "categoria", "categoría",
    ],
    "gaming_4k": [
        "4k", "maxima calidad", "máxima calidad", "maximo rendimiento", "máximo rendimiento",
        "lo mejor que tengas", "lo mas potente", "lo más potente", "gama alta", "el mejor que tengas",
        "el mas caro", "el más caro", "sin limite de precio", "sin límite de precio", "plata no es problema",
    ],
}

_ALL_USE_CASE_KEYWORDS = [(kw, uc) for uc, kws in USE_CASE_KEYWORDS.items() for kw in kws]
_SORTED_USE_CASE_KEYWORDS = sorted(_ALL_USE_CASE_KEYWORDS, key=lambda pair: len(pair[0]), reverse=True)

_UNIT_WORDS_TO_CLP = {
    "lucas": 1_000, "luca": 1_000, "luka": 1_000, "lukas": 1_000,
    "mil": 1_000, "k": 1_000,
    "palos": 1_000_000, "palo": 1_000_000, "millones": 1_000_000, "millon": 1_000_000,
    "kk": 1_000_000, "palitos": 1_000_000, "palito": 1_000_000,
}

# si despues de "<numero> mil/lucas/palos..." viene una de estas palabras, no es plata:
# es una cantidad de otra cosa ("30 mil columnas", "500 mil personas", "2 mil kilometros").
_NON_MONEY_FOLLOWERS = {
    "columnas", "filas", "celdas", "hojas", "paginas", "registros", "lineas", "datos",
    "productos", "personas", "usuarios", "clientes", "empleados", "trabajadores",
    "unidades", "dias", "horas", "veces", "años", "meses", "semanas", "kilometros",
    "km", "gramos", "kilos", "habitantes", "seguidores", "vistas", "visitas",
}


def _next_word_after(text, end_pos):
    m = re.match(r"\s*([a-záéíóúñ]+)", text[end_pos:end_pos + 30])
    return m.group(1) if m else ""


def _parse_amount_token(number_str, unit):
    number = float(number_str.replace(".", "").replace(",", ".")) if "," in number_str and "." in number_str \
        else float(number_str.replace(",", "."))
    return number * _UNIT_WORDS_TO_CLP.get(unit, 1)


def parse_budget(text: str):
    """
    Detecta montos en modismos chilenos: '500 lucas', '1 palo', '1.5 palos',
    '700k', '2kk', 'medio millón', 'entre 500 y 700 lucas', '$800.000', '800000 pesos'.
    Devuelve el monto en CLP (float) o None si no encuentra nada.

    Es deliberadamente cauto con "mil": si la palabra siguiente es "columnas",
    "personas", "kilometros", etc., NO es un monto de dinero (ej: "excel de 30 mil
    columnas" no es un presupuesto de $30.000) y se descarta el match.
    """
    t = text.lower()

    m = re.search(
        r"entre\s+(\d+(?:[.,]\d+)?)\s*(lucas?|palos?|millon(?:es)?|mil|k|kk)?\s+y\s+(\d+(?:[.,]\d+)?)\s*(lucas?|palos?|millon(?:es)?|mil|k|kk)?",
        t,
    )
    if m and _next_word_after(t, m.end()) not in _NON_MONEY_FOLLOWERS:
        unit_a = m.group(2) or m.group(4) or ""
        unit_b = m.group(4) or m.group(2) or ""
        low = _parse_amount_token(m.group(1), unit_a)
        high = _parse_amount_token(m.group(3), unit_b)
        return (low + high) / 2

    m = re.search(r"\b(medio)\s+mill[oó]n\b", t)
    if m:
        return 500_000.0

    m = re.search(r"\b(un|una)\s+mill[oó]n\b", t)
    if m:
        return 1_000_000.0

    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(lucas?|luka|lukas|palos?|millon(?:es)?|mil|kk)\b", t)
    if m and _next_word_after(t, m.end()) not in _NON_MONEY_FOLLOWERS:
        return _parse_amount_token(m.group(1), m.group(2))

    m = re.search(r"(\d+(?:[.,]\d+)?)\s*k\b", t)
    if m and _next_word_after(t, m.end()) not in _NON_MONEY_FOLLOWERS:
        return _parse_amount_token(m.group(1), "k")

    m = re.search(r"\$\s*([\d.,]+)", t)
    if m:
        digits = re.sub(r"[.,]", "", m.group(1))
        if digits:
            return float(digits)

    m = re.search(r"(\d[\d.,]{4,})\s*(pesos|clp)?\b", t)
    if m and _next_word_after(t, m.end()) not in _NON_MONEY_FOLLOWERS:
        digits = re.sub(r"[.,]", "", m.group(1))
        if digits:
            return float(digits)

    return None


def parse_game(text: str):
    t = text.lower()
    for alias in _SORTED_GAME_ALIASES:
        if re.search(r"\b" + re.escape(alias) + r"\b", t):
            return alias, _ALIAS_TO_GAME[alias]

    # tolerancia a typos: si no hubo match exacto, se busca el alias mas
    # parecido por similitud de texto (difflib, stdlib, no es IA) sobre cada
    # ventana de 1-3 palabras del mensaje.
    words = re.findall(r"[a-záéíóúñ0-9]+", t)
    windows = set(words)
    for n in (2, 3):
        windows.update(" ".join(words[i:i + n]) for i in range(len(words) - n + 1))

    best_alias, best_ratio = None, 0.0
    for window in windows:
        if len(window) < 4:
            continue
        match = difflib.get_close_matches(window, _SORTED_GAME_ALIASES, n=1, cutoff=0.8)
        if match:
            ratio = difflib.SequenceMatcher(None, window, match[0]).ratio()
            if ratio > best_ratio:
                best_alias, best_ratio = match[0], ratio

    if best_alias:
        return best_alias, _ALIAS_TO_GAME[best_alias]
    return None, None


_QUALITY_SLANG = {
    "pulento", "pulenta", "bakan", "bacan", "bacán", "la raja", "brigido", "brígido",
    "una maquina", "una máquina", "de show", "cuatico", "cuático", "que vuele",
    "potente", "buena maquina", "buena máquina", "que rinda", "para que no se pegue",
    "que no se cuelgue", "categoria", "categoría",
}
_TOP_TIER_SLANG = {
    "gama alta", "el mejor que tengas", "el mas caro", "el más caro",
    "sin limite de precio", "sin límite de precio", "plata no es problema",
}


def parse_use_case(text: str):
    """Devuelve (use_case, keyword) -- el keyword sirve para armar una nota precisa."""
    t = text.lower()
    for kw, use_case in _SORTED_USE_CASE_KEYWORDS:
        if re.search(r"\b" + re.escape(kw) + r"\b", t):
            return use_case, kw
    return None, None


def interpret(text: str) -> dict:
    """
    Devuelve un dict explicable: nunca 'adivina' silenciosamente, siempre dice
    que regla disparo cada dato para que el usuario pueda verificarlo.
    """
    budget = parse_budget(text)
    game_key, game_info = parse_game(text)
    use_case_tier, use_case_kw = parse_use_case(text)

    if game_info:
        use_case = game_info["tier"]
    elif use_case_tier:
        use_case = use_case_tier
    else:
        use_case = "gaming_1080p"

    notes = []
    if game_info:
        notes.append(f"Detecté que quieres jugar {game_info['display']}: {game_info['note']}.")
    elif use_case_tier == "oficina":
        notes.append("Detecté que es para oficina, estudio o uso general, no para gaming exigente.")
    elif use_case_tier == "gaming_1440p" and use_case_kw in _QUALITY_SLANG:
        notes.append(f'Detecté "{use_case_kw}" como "quiero algo bueno/potente", así que prioricé equipos de gama media-alta (no necesariamente el más caro).')
    elif use_case_tier == "gaming_1440p":
        notes.append("Detecté que es para diseño, edición o creación de contenido, así que prioricé equipos con buena GPU.")
    elif use_case_tier == "gaming_4k" and use_case_kw in _TOP_TIER_SLANG:
        notes.append(f'Detecté "{use_case_kw}": me pediste explícitamente el tope de gama, así que prioricé lo más potente sin importar precio.')
    elif use_case_tier == "gaming_4k":
        notes.append("Detecté que quieres el máximo rendimiento, así que prioricé los equipos más potentes.")
    else:
        notes.append("No reconocí un juego o uso específico en tu mensaje, así que te muestro opciones generales de gaming 1080p.")

    if budget:
        notes.append(f"Presupuesto detectado: ${budget:,.0f}".replace(",", "."))
    else:
        notes.append("No detecté un presupuesto en tu mensaje, así que te muestro opciones de distintos precios.")

    return {"budget": budget, "use_case": use_case, "game": game_info["display"] if game_info else None, "notes": notes}
