"""Motor hibrido: Ming pinta el arte y nosotros ponemos el texto exacto con tipografia real.

Una composicion vive en salidas/comp/<id>.json:
  base    arte de Ming (salidas/base/<id>.png)
  w, h    tamano real del arte en px
  fuentes {"titulo": familia, "cuerpo": familia}  (Google Fonts)
  textos  bloques con zona normalizada, rol, estilo
  logo    ruta del logo oficial de la marca o ""
El lienzo (lienzo.html) la dibuja; Playwright (render.mjs) la exporta a PNG o PDF vectorial.
"""
import json, re, subprocess, os, threading
from pathlib import Path
import numpy as np
from scipy import ndimage
from PIL import Image, ImageFilter

ROOT = Path(__file__).parent
from datos import DATOS
OUT = DATOS / "salidas"
BASE = OUT / "base"
COMP = OUT / "comp"
BASE.mkdir(parents=True, exist_ok=True)
COMP.mkdir(parents=True, exist_ok=True)
PUERTO = int(os.environ.get("MING_PUERTO", 8140))  # otro puerto para probar sin tocar el server abierto
NODE_PATH = os.environ.get("NODE_PATH", str(Path.home() / "node_modules"))

ROLES = {"titulo", "subtitulo", "precio", "lista", "texto", "contacto", "cta", "sticker", "logo"}
# Google Fonts probadas; el Director elige de aqui (o la de la marca)
FUENTES = [
    "Anton", "Bebas Neue", "Oswald", "Archivo Black", "Montserrat", "Poppins", "Outfit", "Sora",
    "Space Grotesk", "Bricolage Grotesque", "Barlow Condensed", "Inter", "Manrope", "Work Sans",
    "DM Sans", "Nunito", "Raleway", "Playfair Display", "DM Serif Display", "Abril Fatface",
    "Cormorant Garamond", "Cinzel", "Righteous", "Lobster", "Pacifico", "Permanent Marker", "Dancing Script",
]
MINIMO = {"titulo": (0.08, 0.5), "precio": (0.1, 0.4), "sticker": (0.08, 0.12), "cta": (0.045, 0.3), "subtitulo": (0.035, 0.5)}
CONECTORES = {"con", "de", "del", "para", "en", "que", "y", "sin", "a", "al", "mientras", "por", "tu", "su"}
_ZONA = re.compile(r"cx:\s*([\d.]+)\s*,\s*cy:\s*([\d.]+)\s*,\s*w:\s*([\d.]+)\s*,\s*h:\s*([\d.]+)")
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
_FAMILIA = re.compile(r"^[A-Za-z0-9 ]{2,40}$")
_VINIETA = re.compile(r"^\s*(?:(?:[•·\-–—*✓✔▪►●○◦]|\d+[.)])\s*)+")


def parse_zona(z):
    """'cx: 0.5, cy: 0.5, w: 0.8, h: 0.1' (o el dict ya parseado) -> dict recortado dentro del lienzo."""
    if isinstance(z, dict):
        z = "cx: {cx}, cy: {cy}, w: {w}, h: {h}".format(**z)
    m = _ZONA.search(str(z))
    if not m:
        raise ValueError(f"zona invalida: {z!r}")
    cx, cy, w, h = (float(v) for v in m.groups())
    w, h = min(max(w, 0.02), 1.0), min(max(h, 0.015), 1.0)
    cx = min(max(cx, w / 2), 1 - w / 2)
    cy = min(max(cy, h / 2), 1 - h / 2)
    return {"cx": round(cx, 4), "cy": round(cy, 4), "w": round(w, 4), "h": round(h, 4)}


def _familia(f, defecto):
    f = str(f or "").strip()
    return f if _FAMILIA.match(f) else defecto


def normalizar(textos, fuentes):
    """Valida lo que devolvio el Director. Lo que no sirve se descarta, no se inventa."""
    fu = {"titulo": _familia((fuentes or {}).get("titulo"), "Montserrat"),
          "cuerpo": _familia((fuentes or {}).get("cuerpo"), "Inter")}
    out = []
    for t in textos or []:
        if not isinstance(t, dict):
            continue
        rol = t.get("rol") if t.get("rol") in ROLES else "texto"
        texto = str(t.get("texto", "")).replace("\\n", "\n").strip()
        if rol == "lista":
            texto = "\n".join(_VINIETA.sub("", l).strip() for l in texto.split("\n") if l.strip())
        # palabra clave que cruza un salto de linea ("*Horarios\nAutomaticos*"): un par de asteriscos por linea
        texto = re.sub(r"\*([^*]+)\*", lambda m: "\n".join(f"*{p}*" if p.strip() else p for p in m.group(1).split("\n")), texto)
        if texto.count("*") % 2 or rol not in ("titulo", "subtitulo"):
            texto = texto.replace("*", "")  # la palabra clave solo se marca en titulares y en pares
        if not texto and rol != "logo":
            continue
        try:
            zona = parse_zona(t.get("zona"))
        except ValueError:
            continue
        if rol in MINIMO:
            h_min, w_min = MINIMO[rol]
            zona = parse_zona({**zona, "h": max(zona["h"], h_min), "w": max(zona["w"], w_min)})
        if rol == "titulo" and "*" not in texto:
            texto = marcar_clave(texto)
        out.append({
            "rol": rol, "texto": texto[:600], "zona": zona,
            "alinear": t.get("alinear") if t.get("alinear") in ("left", "center", "right") else "center",
            "color": t["color"] if _HEX.match(str(t.get("color", ""))) else "#ffffff",
            "fuente": "titulo" if t.get("fuente") == "titulo" else "cuerpo",
            "peso": min(max(int(t.get("peso") or 400) // 100 * 100, 100), 900),
            "mayusculas": bool(t.get("mayusculas")),
            "fondo": t["fondo"] if _HEX.match(str(t.get("fondo", ""))) else "",
            "vinieta": str(t.get("vinieta", ""))[:2] if rol == "lista" else "",
            **({"pinta": "ming"} if t.get("pinta") == "ming" and rol == "titulo" else {}),
        })
    return out, fu


def marcar_clave(titulo):
    """Si el Director no marco palabra clave, la elige el motor: la frase despues del ultimo conector
    ("Agentes de *IA*"), o las ultimas 2 palabras. Un titular sin acento pierde la mitad del kit."""
    lineas = titulo.split("\n")
    palabras = " ".join(lineas).split()
    if len(palabras) < 2:
        return titulo
    if len(palabras) <= 3:
        pos = titulo.rstrip().rfind(palabras[-1])
        return titulo[:pos] + "*" + palabras[-1] + "*" + titulo[pos + len(palabras[-1]):]
    corte = len(palabras) - 2
    for i in range(len(palabras) - 2, 0, -1):
        if palabras[i].lower() in CONECTORES:
            corte = i + 1
            break
    if not 1 <= len(palabras) - corte <= 3:
        corte = len(palabras) - 2
    clave = " ".join(palabras[corte:])
    pos = titulo.rfind(clave.split()[0])
    return titulo[:pos] + "*" + titulo[pos:].rstrip() + "*" if pos >= 0 else titulo


def limpiar_caption(caption, textos):
    """Si el Director igual metio un texto exacto en el arte, lo quitamos: Ming no debe pintarlo."""
    s = json.dumps(caption, ensure_ascii=False)
    for t in textos:
        for linea in t["texto"].replace("*", "").split("\n"):
            linea = linea.strip()
            if len(linea) >= 4:
                s = s.replace(json.dumps(linea, ensure_ascii=False)[1:-1], "")
    return json.loads(s)


def guardar(cid, datos):
    if not re.fullmatch(r"[\w-]+", cid):
        raise ValueError("id invalido")
    tmp = COMP / f"{cid}.tmp"
    tmp.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(COMP / f"{cid}.json")


def cargar(cid):
    if not re.fullmatch(r"[\w-]+", cid) or not (COMP / f"{cid}.json").is_file():
        raise FileNotFoundError("composicion no existe")
    return json.loads((COMP / f"{cid}.json").read_text(encoding="utf-8"))


def mapa_ocupacion(base_png, gw=36):
    """Grilla 0..1 de cuanto 'arte' hay en cada celda: bordes, textura y distancia al tono del fondo.
    Calibrado con arte real de Ming: > 1 es objeto, 0.6-1 halo/brillo, < 0.6 espacio libre."""
    im = (base_png if isinstance(base_png, Image.Image) else Image.open(base_png)).convert("L")
    w, h = im.size
    gh, k = max(1, round(gw * h / w)), 8
    sm = im.resize((gw * k, gh * k))
    L = np.asarray(sm, dtype=np.float32) / 255
    E = np.asarray(sm.filter(ImageFilter.FIND_EDGES), dtype=np.float32) / 255
    celdas = lambda a: a.reshape(gh, k, gw, k)
    m = celdas(L).mean(axis=(1, 3))
    fondo = np.median(np.concatenate([m[0], m[-1], m[:, 0], m[:, -1]]))  # el borde casi siempre es fondo
    return np.maximum.reduce([celdas(E).mean(axis=(1, 3)) / 0.06, celdas(L).std(axis=(1, 3)) / 0.06, np.abs(m - fondo) / 0.12])


def _ocupado(mapa, z):
    """Fraccion de la zona que cae sobre arte (el halo cuenta la mitad)."""
    gh, gw = mapa.shape
    x0, x1 = int((z["cx"] - z["w"] / 2) * gw), max(int((z["cx"] - z["w"] / 2) * gw) + 1, round((z["cx"] + z["w"] / 2) * gw))
    y0, y1 = int((z["cy"] - z["h"] / 2) * gh), max(int((z["cy"] - z["h"] / 2) * gh) + 1, round((z["cy"] + z["h"] / 2) * gh))
    c = mapa[max(0, y0):y1, max(0, x0):x1]
    return float(((c > 1) * 1.0 + ((c > 0.6) & (c <= 1)) * 0.5).mean()) if c.size else 1.0


def _choca(a, b, hueco=0.012):
    return abs(a["cx"] - b["cx"]) * 2 < a["w"] + b["w"] + hueco * 2 and abs(a["cy"] - b["cy"]) * 2 < a["h"] + b["h"] + hueco * 2


MARGEN, HUECO, LIBRE, MOVER = 0.04, 0.012, 0.12, 0.08
CARGADO = 0.35  # por encima de esto el texto necesita vidrio; por debajo basta su sombra
HUECO_HEROE = 0.38  # el sujeto es el protagonista: al menos ~38% del alto


def _esquivar_logo(z, puestos):
    for lg in (p["zona"] for p in puestos if p["rol"] == "logo"):
        if not _choca(z, lg):
            continue
        # distancia desde el borde mas cercano hasta pasar el logo; se recorta igual de ambos lados
        lateral = (lg["cx"] + lg["w"] / 2 + HUECO) if lg["cx"] < 0.5 else (1 - (lg["cx"] - lg["w"] / 2) + HUECO)
        ancho = min(z["w"], 1 - 2 * lateral)
        if ancho >= 0.3 and abs(z["cx"] - 0.5) < 0.1:
            z = {**z, "cx": 0.5, "w": round(ancho, 4)}
        else:
            z = {**z, "cy": round(max(z["cy"], lg["cy"] + lg["h"] / 2 + HUECO + z["h"] / 2), 4)}
    return z


def con_margen(z, m=None):
    """La zona entera queda a `m` de los bordes (el Director a veces pide cx 0.275 + w 0.55 = pegado a x=0)."""
    m = MARGEN if m is None else m
    w, h = min(z["w"], 1 - 2 * m), min(z["h"], 1 - 2 * m)
    return {"cx": round(min(max(z["cx"], m + w / 2), 1 - m - w / 2), 4), "cy": round(min(max(z["cy"], m + h / 2), 1 - m - h / 2), 4),
            "w": round(w, 4), "h": round(h, 4)}


def acomodar(base_png: Path, textos, sujeto_png: Path = None, sujeto_zona=None, titular_detras=False):
    """Maqueta los textos sobre el arte REAL: Ming no siempre deja libres las zonas que se le piden.
    Respeta el orden de lectura del Director; cada bloque va a la posicion libre mas cercana (puede
    achicarse hasta 70%). Si el arte no deja espacio, el bloque queda en su sitio sobre un panel de vidrio,
    y los bloques con panel seguidos comparten uno solo. Devuelve (textos, paneles)."""
    for t in textos:
        if t["rol"] != "logo" and t.get("pinta") != "ming":
            t["zona"] = con_margen(t["zona"])
    mapa_fondo = mapa_ocupacion(base_png)
    mapa = _mapa_con_sujeto(base_png, sujeto_png, sujeto_zona) if sujeto_png and sujeto_zona else mapa_fondo
    orden = sorted((t for t in textos if t["rol"] not in ("logo", "sticker")), key=lambda t: t["zona"]["cy"])
    puestos = []
    # "piso" por columna: un texto solo se apila debajo de los que estan encima de el en horizontal.
    # Antes era uno global y un menu en fila (Inicio, Precios, Contacto) salia en escalera.
    def piso_de(z):
        return max([MARGEN] + [p["zona"]["cy"] + p["zona"]["h"] / 2 + HUECO for p in puestos
                               if p["rol"] != "logo" and abs(p["zona"]["cx"] - z["cx"]) * 2 < p["zona"]["w"] + z["w"]])
    # logo primero: la esquina con menos arte (arriba preferida); los textos se acomodan alrededor
    for t in (t for t in textos if t["rol"] == "logo"):
        _poner_logo(t, mapa, sujeto_zona)
        puestos.append(t)
    for t in orden:
        if t.get("pinta") == "ming":  # el titular artistico ya esta pintado en el arte: no se mueve
            puestos.append(t)
            t["panel"] = False
            continue
        z0, mejor = _esquivar_logo(t["zona"], puestos), None
        piso = piso_de(z0)
        for esc in (1.0, 0.85, 0.7):
            w, h = z0["w"] * esc, z0["h"] * esc
            desde = max(piso + h / 2, z0["cy"] - MOVER)
            for i in range(0, 60):
                cy = desde + i * 0.004
                if cy > z0["cy"] + MOVER or cy + h / 2 > 1 - MARGEN:
                    break
                z = {"cx": z0["cx"], "cy": cy, "w": w, "h": h}
                if any(_choca(z, p["zona"]) for p in puestos):
                    continue
                oc = _ocupado(mapa_fondo if (titular_detras and t["rol"] == "titulo") else mapa, z)
                costo = oc * 10 + abs(cy - z0["cy"]) * 2 + (1 - esc) * 1.5
                if oc <= LIBRE and (mejor is None or costo < mejor[0]):
                    mejor = (costo, z)
        if mejor:
            t["zona"], t["panel"] = {k: round(v, 4) for k, v in mejor[1].items()}, False
        else:
            # sin lugar libre cerca: queda en su sitio (debajo del anterior, sin encimarse) sobre vidrio
            h = z0["h"]
            cy = max(z0["cy"], piso + h / 2)
            if cy + h / 2 > 1 - MARGEN:  # no cabe: se achica lo necesario (nunca se agranda) y se apoya abajo
                falta = max(0.025, min(h, 0.04)) - (1 - MARGEN - piso)
                tapa = max((p for p in puestos if p["rol"] not in ("logo", "sticker")
                            and abs(p["zona"]["cx"] - z0["cx"]) * 2 < p["zona"]["w"] + z0["w"]),
                           key=lambda p: p["zona"]["cy"] + p["zona"]["h"] / 2, default=None)
                if falta > 0 and tapa and tapa["zona"]["h"] - falta >= 0.03:
                    # la columna se lleno: el bloque de arriba cede alto (su letra se reajusta) y deja lugar a este
                    zt = tapa["zona"]
                    tapa["zona"] = {**zt, "h": round(zt["h"] - falta, 4), "cy": round(zt["cy"] - falta / 2, 4)}
                    piso = piso_de(z0)
                h = max(0.02, min(h, 1 - MARGEN - piso))
                cy = 1 - MARGEN - h / 2
            z = {**z0, "cy": round(cy, 4), "h": round(h, 4)}
            t["zona"], t["panel"] = z, _ocupado(mapa, z) > CARGADO  # si solo faltaba espacio o el arte es suave, sin vidrio
        puestos.append(t)
    # el sello va al final: donde lo pidio el Director si no tapa nada; si no, la esquina libre mas cercana
    for t in (t for t in textos if t["rol"] == "sticker"):
        z, t["panel"] = t["zona"], False
        candidatos = [z] + [con_margen({**z, "cx": cx, "cy": cy}) for cx in (0.15, 0.85) for cy in (0.12, 0.88)]
        if sujeto_zona:  # junto a una esquina de arriba del sujeto, como sello de "NUEVO" sobre el plato
            s = sujeto_zona
            candidatos += [con_margen({**z, "cx": s["cx"] + k * s["w"] * 0.4, "cy": s["cy"] - s["h"] * 0.4}) for k in (1, -1)]
        libres = [c for c in candidatos if not any(_choca(c, p["zona"]) for p in puestos)]
        if libres:
            t["zona"] = min(libres, key=lambda c: abs(c["cx"] - z["cx"]) + abs(c["cy"] - z["cy"]))
        puestos.append(t)
        orden.append(t)
    return textos, _paneles(orden)


def _mapa_con_sujeto(base_png, sujeto_png, zona):
    comp = Image.open(base_png).convert("RGBA")
    W, H = comp.size
    suj = Image.open(sujeto_png).convert("RGBA").resize((max(1, round(zona["w"] * W)), max(1, round(zona["h"] * H))))
    comp.alpha_composite(suj, (round((zona["cx"] - zona["w"] / 2) * W), round((zona["cy"] - zona["h"] / 2) * H)))
    return mapa_ocupacion(comp)


def _poner_logo(t, mapa, sujeto_zona=None, evitar=()):
    lado = min(t["zona"]["w"], t["zona"]["h"] * 1.3, 0.16)
    opciones = []
    for cx_ in (MARGEN + lado / 2, 1 - MARGEN - lado / 2):
        for cy_, pref in ((MARGEN + lado * 0.375, 0), (1 - MARGEN - lado * 0.375, 0.15)):
            z = {"cx": cx_, "cy": cy_, "w": lado, "h": lado * 0.75}
            if (sujeto_zona and _choca(z, sujeto_zona, 0)) or any(_choca(z, e) for e in evitar):
                continue
            opciones.append((_ocupado(mapa, z) + pref, z))
    if opciones:
        t["zona"] = {k: round(v, 4) for k, v in min(opciones, key=lambda o: o[0])[1].items()}
    t["panel"] = False


def _paneles(orden):
    """Un panel de vidrio por grupo de bloques seguidos que lo necesitan."""
    paneles, grupo = [], []
    for t in orden + [None]:
        if t is not None and t.get("panel"):
            if grupo and (t["zona"]["cy"] - t["zona"]["h"] / 2) - (grupo[-1]["cy"] + grupo[-1]["h"] / 2) > 0.04:
                orden_cierre = True
            else:
                grupo.append(t["zona"])
                continue
        else:
            orden_cierre = False
        if grupo:
            pad = 0.025
            x0 = max(0.02, min(z["cx"] - z["w"] / 2 for z in grupo) - pad)
            x1 = min(0.98, max(z["cx"] + z["w"] / 2 for z in grupo) + pad)
            y0 = max(0.02, min(z["cy"] - z["h"] / 2 for z in grupo) - pad)
            y1 = min(0.98, max(z["cy"] + z["h"] / 2 for z in grupo) + pad)
            paneles.append({"cx": round((x0 + x1) / 2, 4), "cy": round((y0 + y1) / 2, 4), "w": round(x1 - x0, 4), "h": round(y1 - y0, 4)})
            grupo = []
        if t is not None and orden_cierre:
            grupo = [t["zona"]]
    return paneles


def _es_reserva(capa):
    d = str(capa.get("description", "")).lower()
    return any(k in d for k in ("no text", "reserved", "placeholder", "empty zone", "empty area", "invisible area"))


def planificar(caption, textos, ignorar=frozenset()):
    """Arregla el plano ANTES de pintar: si alguna zona de texto choca con el sujeto (personaje, producto),
    arma la maqueta clasica de flyer: textos arriba y abajo en su orden, y el sujeto reubicado y escalado
    en el hueco del medio. Ming respeta las coordenadas, asi el arte llega con el espacio correcto."""
    capas = caption.get("layers", [])
    sujetos = []
    for c in capas:
        try:
            z = parse_zona(c.get("coordinates", ""))
        except ValueError:
            continue
        if (z["w"] >= 0.95 and z["h"] >= 0.95) or _es_reserva(c):
            continue
        sujetos.append((c, z))
    orden = sorted((t for t in textos if t["rol"] != "logo"), key=lambda t: t["zona"]["cy"])
    if not sujetos or not any(_choca(t["zona"], z, 0) for t in orden if t["rol"] not in ignorar for _, z in sujetos):
        return False
    # arriba se empieza debajo del logo si esta en la mitad superior
    techo = MARGEN
    for t in textos:
        if t["rol"] == "logo" and t["zona"]["cy"] < 0.5:
            techo = max(techo, t["zona"]["cy"] + t["zona"]["h"] / 2 + HUECO)
    alto = [t["zona"]["h"] for t in orden]
    fijo = [t["rol"] == "titulo" for t in orden]  # el titular manda: nunca se compacta
    n = len(orden)
    bb = {"x0": min(z["cx"] - z["w"] / 2 for _, z in sujetos), "x1": max(z["cx"] + z["w"] / 2 for _, z in sujetos),
          "y0": min(z["cy"] - z["h"] / 2 for _, z in sujetos), "y1": max(z["cy"] + z["h"] / 2 for _, z in sujetos)}
    centro = (bb["y0"] + bb["y1"]) / 2
    f = 1.0
    for _ in range(8):  # si el hueco queda muy chico, los textos se compactan un poco (hasta 75%)
        mejor = None
        for k in range(n + 1):
            arriba = sum(a if fx else a * f for a, fx in zip(alto[:k], fijo[:k])) + HUECO * max(0, k - 1)
            abajo = sum(a if fx else a * f for a, fx in zip(alto[k:], fijo[k:])) + HUECO * max(0, n - k - 1)
            g0 = techo + arriba + (HUECO * 2 if k else 0)
            g1 = 1 - MARGEN - abajo - (HUECO * 2 if k < n else 0)
            puntaje = (g1 - g0) - abs((g0 + g1) / 2 - centro) * 0.3
            if mejor is None or puntaje > mejor[0]:
                mejor = (puntaje, k, g0, g1)
        _, k, g0, g1 = mejor
        if g1 - g0 >= HUECO_HEROE or f <= 0.7:
            break
        f -= 0.05
    y = techo
    for t in orden[:k]:
        h = t["zona"]["h"] * (1 if t["rol"] == "titulo" else f)
        t["zona"] = {**t["zona"], "cy": round(y + h / 2, 4), "h": round(h, 4)}
        y += h + HUECO
    y = 1 - MARGEN
    for t in reversed(orden[k:]):
        h = t["zona"]["h"] * (1 if t["rol"] == "titulo" else f)
        t["zona"] = {**t["zona"], "cy": round(y - h / 2, 4), "h": round(h, 4)}
        y -= h + HUECO
    # el sujeto (todas sus capas juntas, sin deformarse) va al hueco
    bw, bh = bb["x1"] - bb["x0"], bb["y1"] - bb["y0"]
    esc = min((g1 - g0) / bh, (1 - 2 * MARGEN) / bw, 1.15)
    gc = (g0 + g1) / 2
    for c, z in sujetos:
        nz = {"cx": 0.5 + (z["cx"] - (bb["x0"] + bb["x1"]) / 2) * esc, "cy": gc + (z["cy"] - (bb["y0"] + bb["y1"]) / 2) * esc,
              "w": z["w"] * esc, "h": z["h"] * esc}
        c["coordinates"] = "cx: {cx:.3f}, cy: {cy:.3f}, w: {w:.3f}, h: {h:.3f}".format(**nz)
    # las reservas viejas del Director quedan obsoletas: se regeneran con las zonas nuevas
    caption["layers"] = [c for c in capas if not _es_reserva(c)]
    return True


_rembg = None
_rembg_lock = threading.Lock()


def recortar_sujeto(png: Path, destino: Path):
    """Ming (via OpenRouter) no entrega transparencia: pinta el sujeto aislado sobre fondo liso y aqui se recorta
    con rembg (isnet). Se ajusta al contorno real del sujeto para que la maqueta sea exacta."""
    global _rembg
    from rembg import remove, new_session
    with _rembg_lock:  # un modelo en memoria, un recorte a la vez
        if _rembg is None:
            _rembg = new_session("isnet-general-use")
        out = remove(Image.open(png).convert("RGB"), session=_rembg, post_process_mask=True)
    out = _refinar(out, Image.open(png).convert("RGB"))
    caja = out.getchannel("A").point(lambda a: 255 if a > 12 else 0).getbbox()
    if not caja:
        raise RuntimeError("no se pudo recortar el sujeto")
    out.crop(caja).save(destino)
    return destino


def recortar_letras(png: Path, destino: Path):
    """Lettering de Ming sobre croma: la llave de color es exacta y no se come trazos finos (rembg si los rompe).
    Si Ming no respeto el croma, cae a rembg igual que el sujeto."""
    original = Image.open(png).convert("RGB")
    out = _croma(None, original)
    if out is None:
        return recortar_sujeto(png, destino)
    caja = out.getchannel("A").point(lambda a: 255 if a > 40 else 0).getbbox()
    if not caja:
        raise RuntimeError("no se pudo recortar el titular")
    out.crop(caja).save(destino)
    return destino


def _croma(recorte, original):
    """Si Ming pinto el sujeto sobre fondo croma (verde/magenta puro), se quita tambien el fondo atrapado en
    huecos (entre brazo y cuerpo) que rembg deja, y se limpia el halo de color de los bordes (despill).
    Solo actua si el borde de la imagen es realmente croma: con otro fondo no toca nada."""
    rgb = np.asarray(original, dtype=np.float32)
    H, W = rgb.shape[:2]
    # el sujeto puede tocar una orilla (un plato que se sale por abajo): vale si buena parte del borde es croma puro.
    # Ming a veces deja un marco blanco alrededor del croma: se mira tambien un anillo un poco hacia adentro.
    mejor, clave = 0.0, None
    for f in (0, 0.03, 0.07, 0.12, 0.18, 0.25):
        y, x = int(H * f), int(W * f)
        borde = np.concatenate([rgb[y, x:W - x], rgb[H - 1 - y, x:W - x], rgb[y:H - y, x], rgb[y:H - y, W - 1 - x]])
        for c in ((255, 0, 255), (0, 255, 0)):
            # croma puro, o croma apagado/en degradado reconocido por tono (magenta oscuro 156,52,136 tambien vale)
            tono = (np.minimum(borde[:, 0], borde[:, 2]) - borde[:, 1]) if c[0] else (borde[:, 1] - np.maximum(borde[:, 0], borde[:, 2]))
            cerca_c = (np.linalg.norm(borde - np.array(c, np.float32), axis=1) < 90) | (tono > 55)
            if cerca_c.mean() > mejor:
                mejor, clave = cerca_c.mean(), np.median(borde[cerca_c], axis=0)
    if mejor < 0.2:  # no es un fondo croma (una foto normal no tiene croma puro en el borde)
        return recorte  # (None si lo pidio recortar_letras: ahi se usa rembg)
    dist = np.linalg.norm(rgb - clave, axis=2)
    # con fondo croma real, la llave de color es exacta: todo lo que no es croma es sujeto. rembg a veces se
    # come partes claras del sujeto (el borde blanco de un plato) y la llave las devuelve.
    a = np.clip((dist - 70) / 60, 0, 1) * 255
    # Ming a veces pinta el croma en degradado (magenta claro -> morado oscuro): la distancia a un solo color no
    # alcanza. Por tono: cuanto le sobra al croma sobre los otros canales. Las letras blancas o celestes dan ~0.
    R0, G0, B0 = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    tono = (np.minimum(R0, B0) - G0) if clave[0] > clave[1] else (G0 - np.maximum(R0, B0))
    a = np.minimum(a, np.clip((60 - tono) / 30, 0, 1) * 255)
    # despill cerca del borde: se quita el tinte del croma que rebota en el sujeto
    cerca = dist < 220
    R, G, B = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    if clave[1] > clave[0] and clave[1] > clave[2]:  # verde: G no puede superar al mayor de R/B
        rgb[..., 1] = np.where(cerca, np.minimum(G, np.maximum(R, B)), G)
    else:  # magenta: lo que R y B tengan en comun por encima de G es derrame
        derrame = np.clip(np.minimum(R, B) - G, 0, None) * cerca
        rgb[..., 0], rgb[..., 2] = R - derrame, B - derrame
    # marco que Ming pinto alrededor del croma (blanco, por ejemplo): todo lo que queda fuera del rectangulo donde
    # hay croma es marco. Sin marco, el rectangulo es la imagen entera y no se toca nada.
    es_croma = dist < 70
    filas, cols = np.where(es_croma.mean(axis=1) > 0.05)[0], np.where(es_croma.mean(axis=0) > 0.05)[0]
    if len(filas) and len(cols):
        # solo es marco una franja de color PAREJO (el marco blanco de Ming). Un croma en degradado deja una franja
        # oscura que no pasa la llave, y ahi puede haber letras: eso no se toca
        for franja in (np.s_[:filas[0]], np.s_[filas[-1] + 1:], np.s_[:, :cols[0]], np.s_[:, cols[-1] + 1:]):
            px = rgb[franja].reshape(-1, 3)
            if len(px) and px.std(axis=0).max() < 12:
                a[franja] = 0
    out = np.dstack([rgb, a]).clip(0, 255).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def _refinar(recorte, original):
    """Corrige los dos errores tipicos de rembg sin hacerlo lento (< 1 s):
    1. Fondo croma real -> la llave de color decide sola (exacta).
    2. Fondo plano (aunque no sea croma) -> se devuelve lo que rembg se comio junto al sujeto si su color es
       muy distinto al fondo (el borde blanco de un plato sobre fondo oscuro).
    3. Huecos cerrados dentro del sujeto: si NO se parecen al fondo son parte del sujeto (salsa oscura) y se
       rellenan; si se parecen al fondo (hueco entre brazo y cuerpo) quedan transparentes."""
    croma = _croma(None, original)
    if croma is not None:
        return croma
    rgb = np.asarray(original, dtype=np.float32)
    borde = np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]])
    fondo = np.median(borde, axis=0)
    plano = borde.std(axis=0).max() <= 25
    a = np.asarray(recorte.getchannel("A"), dtype=np.float32)
    a0 = a.copy()  # lo que dijo rembg, antes de corregir
    dist = np.linalg.norm(rgb - fondo, axis=2)
    solido = a > 128
    if plano and solido.any():
        cerca = ndimage.binary_dilation(solido, iterations=max(3, round(min(a.shape) * 0.02)))
        llave = np.clip((dist - 80) / 40, 0, 1) * 255  # solo lo claramente distinto al fondo; sombras y viñeta no vuelven
        a = np.where(cerca, np.maximum(a, llave), a)
        # sombra proyectada que rembg dejo pegada: pixeles con color de fondo conectados con el exterior se pelan.
        # Lo encerrado dentro del sujeto (una pantalla oscura entre las manos) no se toca.
        luz = rgb.mean(axis=2)
        sombra = (dist < 35) | ((luz < fondo.mean() + 8) & (rgb.max(axis=2) - rgb.min(axis=2) < 35))  # fondo, o mas oscuro y sin color
        comp_ext, _ = ndimage.label((a <= 128) | sombra)
        tocan = np.unique(np.concatenate([comp_ext[0], comp_ext[-1], comp_ext[:, 0], comp_ext[:, -1]]))
        pelar = np.isin(comp_ext, tocan[tocan > 0]) & sombra
        # una sombra proyectada es una franja chica; una chaqueta negra que toca el borde de abajo (persona cortada
        # a la cintura) es oscura y sin color igual, pero es medio cuerpo: lo solido grande no se pela
        solido_pelado = pelar & (a0 >= 200) & (dist >= 35)
        filas = np.where((a0 > 128).any(axis=1))[0]
        if len(filas):  # una sombra proyectada cae abajo del objeto: arriba (la tapa negra de un frasco) nunca se pela
            mitad = (filas[0] + filas[-1]) // 2
            pelar[:mitad] &= ~solido_pelado[:mitad]
            solido_pelado[:mitad] = False
        if solido_pelado.sum() > 0.25 * max(1, (a0 > 128).sum()):
            pelar &= ~solido_pelado
        a = np.where(pelar, 0, a)
        solido = a > 128
    huecos, n = ndimage.label(ndimage.binary_fill_holes(solido) & ~solido)
    if n:
        medias = ndimage.mean(dist, huecos, index=np.arange(1, n + 1))
        # rembg marca a medias una etiqueta blanca sobre fondo blanco; el aire entre brazo y cuerpo lo deja en ~0
        dudas = ndimage.mean(a0, huecos, index=np.arange(1, n + 1))
        # una etiqueta blanca de frasco sobre fondo blanco es un hueco casi RECTANGULAR; el aire entre brazo y
        # cuerpo es una franja irregular. Lo rectangular y no diminuto es parte del sujeto.
        cajas = ndimage.find_objects(huecos)
        tam = ndimage.sum(np.ones_like(a), huecos, index=np.arange(1, n + 1))
        rect = np.array([t / ((c[0].stop - c[0].start) * (c[1].stop - c[1].start)) > 0.85 and t > 0.01 * max(1, solido.sum())
                         for t, c in zip(tam, cajas)])
        de_sujeto = np.concatenate([[False], (np.asarray(medias) > 45) | (np.asarray(dudas) > 40) | rect])
        a = np.where(de_sujeto[huecos], 255, a)
    # contorno: se cierran mellas chicas (borde sombreado de un plato) sin rellenar huecos de fondo real,
    # y se suaviza 1 px para que no parezca recortado con tijera
    solido = a > 128
    r = max(2, round(min(a.shape) * 0.006))
    cerrado = ndimage.binary_closing(solido, structure=np.ones((3, 3)), iterations=r)
    a = np.where(cerrado & ~solido & (dist > 30), 255, a)
    a = ndimage.gaussian_filter(a, 0.8)
    # el color sale SIEMPRE del original: rembg pone en negro lo que descarta, y lo recuperado saldria negro
    return Image.fromarray(np.dstack([rgb, a]).clip(0, 255).astype(np.uint8), "RGBA")


def encajar(zona, ancho, alto, W, H):
    """El sujeto entra en su zona sin deformarse (contain), apoyado abajo y centrado."""
    zw, zh = zona["w"] * W, zona["h"] * H
    e = min(zw / ancho, zh / alto)
    w, h = ancho * e / W, alto * e / H
    return {"cx": zona["cx"], "cy": round(zona["cy"] + zona["h"] / 2 - h / 2, 4), "w": round(w, 4), "h": round(h, 4)}


def heroe_en_hueco(textos, zona, ignorar=frozenset()):
    """El sujeto es el protagonista: ocupa la franja libre mas grande entre los textos (no solo cuando choca).
    Si la zona del Director ya es casi del alto del hueco, se respeta."""
    ocupado = sorted(((t["zona"]["cy"] - t["zona"]["h"] / 2, t["zona"]["cy"] + t["zona"]["h"] / 2)
                      for t in textos if t["rol"] not in ("logo", "sticker") and t["rol"] not in ignorar))
    huecos, y = [], MARGEN
    for y0, y1 in ocupado:
        if y0 > y:
            huecos.append((y, y0))
        y = max(y, y1)
    if y < 1 - MARGEN:
        huecos.append((y, 1 - MARGEN))
    if not huecos:
        return zona
    g0, g1 = max(huecos, key=lambda g: g[1] - g[0])
    alto = g1 - g0 - 2 * HUECO
    if alto < 0.2 or zona["h"] >= alto * 0.9:
        return zona
    return {"cx": 0.5, "cy": round((g0 + g1) / 2, 4), "w": 0.9, "h": round(alto, 4)}


def objetos_libres(objetos, textos):
    """Los objetos decoran: el que choque con un texto se quita (nunca tapan lo que hay que leer)."""
    return [o for o in objetos or [] if not any(_choca(o["zona"], t["zona"], 0) for t in textos)]


def crear(cid, base_png: Path, textos, fuentes, logo="", sujeto_png: Path = None, sujeto_zona=None,
          titular_detras=False, prompts=None, kit=None, titular_png: Path = None, objetos=None):
    """objetos: [(png, zona)] piezas decorativas de la biblioteca; van debajo del sujeto y nunca sobre texto."""
    w, h = Image.open(base_png).size
    sujeto = None
    if sujeto_png and sujeto_zona:
        sw, sh = Image.open(sujeto_png).size
        sujeto = {"src": f"salidas/base/{sujeto_png.name}", "zona": encajar(parse_zona(sujeto_zona), sw, sh, w, h)}
    textos, paneles = acomodar(base_png, textos, sujeto_png, sujeto and sujeto["zona"], titular_detras)
    if titular_png:  # lettering de Ming: el titular se dibuja con esa imagen (arte_ming queda para volver a el)
        for t in textos:
            if t["rol"] == "titulo":
                t["arte"] = t["arte_ming"] = f"salidas/base/{titular_png.name}"
    datos = {"base": f"salidas/base/{base_png.name}", "w": w, "h": h, "fuentes": fuentes, "textos": textos,
             "paneles": paneles, "logo": logo}
    if sujeto:
        datos.update(v=2, sujeto=sujeto, titular_detras=titular_detras)
    if objetos:
        puestos = [{"src": f"salidas/base/{png.name}", "zona": encajar(z, *Image.open(png).size, w, h)} for png, z in objetos]
        datos["objetos"] = objetos_libres(puestos, textos)
    if prompts:
        datos["prompts"] = prompts
    if kit:  # el kit tipografico manda sobre las fuentes que haya elegido el Director
        datos["kit"] = kit
        datos["fuentes"] = {"titulo": kit["fuentes"]["titulo"], "cuerpo": kit["fuentes"]["cuerpo"]}
    guardar(cid, datos)
    return datos


# ponytail: un Chromium por render (~2s). Si se vuelve cuello de botella, un worker node persistente.
_sem = threading.Semaphore(2)  # como mucho 2 Chromium a la vez: la PC tiene poca RAM


# ---- reticulas: el mismo arte reacomodado en layouts de diseñador (el fondo es solo ambiente y el sujeto
# viene recortado, asi que ambos se pueden mover sin volver a pintar) ----
RETICULAS = {"centrado": "Héroe centrado", "dividido": "Dividido", "gigante": "Titular gigante",
             "banda": "Banda inferior", "editorial": "Marco editorial"}
CABEZA, PIE = ("titulo", "subtitulo"), ("cta", "contacto")


def _apilar(ts, x0, x1, y0, y1, alinear="center", va="center", maxf=1.4):
    """Apila bloques en la caja (x0..x1, y0..y1) conservando su proporcion de alto."""
    if not ts:
        return
    huecos = HUECO * 2 * (len(ts) - 1)
    total = sum(t["zona"]["h"] for t in ts)
    f = min(maxf, (y1 - y0 - huecos) / total)
    usado = total * f + huecos
    y = {"top": y0, "center": y0 + (y1 - y0 - usado) / 2, "bottom": y1 - usado}[va]
    for t in ts:
        h = t["zona"]["h"] * f
        t["zona"] = {"cx": round((x0 + x1) / 2, 4), "cy": round(y + h / 2, 4), "w": round(x1 - x0, 4), "h": round(h, 4)}
        t["alinear"] = alinear
        y += h + HUECO * 2


def reticula(d, rid):
    """Composicion `d` reacomodada con la reticula `rid` (sin guardar). Parte siempre del plano original."""
    if rid not in RETICULAS or not d.get("sujeto"):
        raise ValueError("reticula invalida o diseno sin sujeto")
    o = d.get("orig") or d
    textos = json.loads(json.dumps(o["textos"]))
    for t, actual in zip(textos, d["textos"]):  # lo que se edito a mano despues se conserva
        t["texto"] = actual["texto"]
        t["panel"] = False  # el vidrio del plano viejo no vale en la posicion nueva: se recalcula abajo
    if any(t.get("pinta") == "ming" for t in textos):
        raise ValueError("el titular esta pintado en el arte: no se puede mover")
    orden = sorted((t for t in textos if t["rol"] != "logo"), key=lambda t: t["zona"]["cy"])
    cabeza = [t for t in orden if t["rol"] in CABEZA]
    pie = [t for t in orden if t["rol"] in PIE]
    cuerpo = [t for t in orden if t["rol"] not in CABEZA + PIE + ("sticker",)]
    logo = next((t for t in textos if t["rol"] == "logo"), None)
    techo = 0.13 if logo else MARGEN  # el logo va arriba en una esquina: los textos centrados empiezan debajo
    M = MARGEN + 0.01
    extra = {"titular_detras": False, "banda": None, "marco": False}
    # la zona de textos crece con cuantos bloques hay (lista + precio + cta + contacto no caben en una franja fija)
    alto = lambda ts: sum(t["zona"]["h"] for t in ts) + HUECO * 2 * max(0, len(ts) - 1)
    if rid == "centrado":
        _apilar(cabeza, M, 1 - M, techo, 0.34, va="top")
        _apilar(cuerpo + pie, M + 0.04, 1 - M - 0.04, max(0.55, 1 - M - alto(cuerpo + pie)), 1 - M, va="bottom", maxf=1.1)
        arriba = max((t["zona"]["cy"] + t["zona"]["h"] / 2 for t in cabeza), default=techo)
        abajo = min((t["zona"]["cy"] - t["zona"]["h"] / 2 for t in cuerpo + pie), default=1 - M)
        zona = {"x0": 0.08, "x1": 0.92, "y0": arriba + HUECO * 2, "y1": abajo - HUECO * 2}
    elif rid == "dividido":
        _apilar(cabeza + cuerpo + pie, M, 0.48, techo, 1 - M, alinear="left")
        zona = {"x0": 0.52, "x1": 1 - MARGEN, "y0": 0.08, "y1": 1 - MARGEN}
    elif rid == "gigante":
        cuerpo, cabeza = [t for t in cabeza if t["rol"] != "titulo"] + cuerpo, [t for t in cabeza if t["rol"] == "titulo"]
        for t in cabeza[:1]:
            t["zona"]["h"] = max(t["zona"]["h"], 0.22)
        _apilar(cabeza, 0.03, 0.97, techo, 0.45, va="top", maxf=2.5)
        _apilar(cuerpo + pie, M + 0.04, 1 - M - 0.04, max(0.6, 1 - M - alto(cuerpo + pie)), 1 - M, va="bottom", maxf=1.0)
        abajo = min((t["zona"]["cy"] - t["zona"]["h"] / 2 for t in cuerpo + pie), default=1 - M)
        tz = cabeza[0]["zona"] if cabeza else {"cy": 0.2, "h": 0.1}
        # el sujeto roza solo la base del titular (efecto revista): las palabras se siguen leyendo
        zona = {"x0": 0.1, "x1": 0.9, "y0": tz["cy"] + tz["h"] * 0.4, "y1": abajo - HUECO}
        extra["titular_detras"] = True
    elif rid == "banda":
        b0 = max(0.46, min(0.62, 1 - M - alto(cabeza + cuerpo + pie) - 0.03))
        _apilar(cabeza + cuerpo + pie, M, 1 - M, b0 + 0.025, 1 - M)
        for t in cabeza + cuerpo + pie:
            t["panel"] = True  # sobre la banda solida: el contraste se mide contra ella
        zona = {"x0": 0.1, "x1": 0.9, "y0": techo, "y1": b0 - 0.02}
        extra["banda"] = {"cx": 0.5, "cy": round((b0 + 1) / 2, 4), "w": 1.0, "h": round(1 - b0, 4)}
    else:  # editorial: marco fino, sujeto arriba, textos abajo alineados a la izquierda
        y0 = max(0.5, 0.93 - alto(cabeza + cuerpo + pie))
        _apilar(cabeza + cuerpo + pie, 0.1, 0.9, y0, 0.93, alinear="left", va="bottom", maxf=1.2)
        zona = {"x0": 0.12, "x1": 0.88, "y0": 0.09 if not logo else 0.13, "y1": y0 - 0.02}
        extra["marco"] = True
    zona = {"cx": (zona["x0"] + zona["x1"]) / 2, "cy": (zona["y0"] + zona["y1"]) / 2,
            "w": zona["x1"] - zona["x0"], "h": max(0.1, zona["y1"] - zona["y0"])}
    base, suj_png = DATOS / d["base"], DATOS / d["sujeto"]["src"]
    sw, sh = Image.open(suj_png).size
    sz = encajar(zona, sw, sh, d["w"], d["h"])
    if rid == "dividido":  # a la derecha, centrado en su columna
        sz["cy"] = round(zona["cy"], 4)
    for t in orden:
        if t["rol"] == "sticker":  # sello en la esquina superior del sujeto
            t["zona"] = parse_zona({"cx": sz["cx"] + sz["w"] * 0.32, "cy": sz["cy"] - sz["h"] * 0.32, "w": 0.22, "h": 0.12})
    mapa = _mapa_con_sujeto(base, suj_png, sz)
    if logo:
        _poner_logo(logo, mapa, sz, [t["zona"] for t in orden])
    for t in orden:
        if t["rol"] != "sticker" and not t.get("panel"):
            if logo:
                t["zona"] = _esquivar_logo(t["zona"], [logo])
            # el boton (cta con kit) ya trae su fondo solido: vidrio solo para texto suelto sobre arte cargado
            boton = t["rol"] == "cta" and d.get("kit") and d["kit"]["cta"].get("estilo") != "contorno"
            detras = extra["titular_detras"] and t["rol"] == "titulo"  # vidrio + sujeto encima se ve sucio
            t["panel"] = not boton and not detras and _ocupado(mapa, t["zona"]) > CARGADO
    paneles = _paneles([t for t in orden if not extra["banda"]])
    return {**d, "textos": textos, "paneles": paneles, "sujeto": {**d["sujeto"], "zona": sz}, **extra, "reticula": rid,
            "objetos": objetos_libres(o.get("objetos"), textos),
            "orig": o if d.get("orig") else {k: d.get(k) for k in ("textos", "paneles", "sujeto", "titular_detras", "objetos")}}


def con_kit(d, kit):
    """La misma composicion vestida con otro kit (sin guardar): el arte y las zonas no cambian."""
    return {**d, "kit": kit, "fuentes": {"titulo": kit["fuentes"]["titulo"], "cuerpo": kit["fuentes"]["cuerpo"]}}


ULTIMO_JUEZ = {}  # cid -> informe del juez del ultimo render (lo arma el lienzo, ver juzgar())
PESO = {"ilegible": 3, "encimados": 3, "titular_tapado": 3, "sobre_sujeto": 2, "borde": 1}
MIN_LETRA = 0.017  # igual que en lienzo.html juzgar()


def gravedad(juez):
    return sum(PESO.get(p["tipo"], 1) for p in (juez or {}).get("problemas", []))


def pulir(cid, destino: Path, intentos=2):
    """Auto-correccion gratis (sin Ming): el juez mide el diseno armado; los textos ilegibles reciben mas espacio y
    todo se re-acomoda sobre el arte real. Un cambio solo se queda si el juez da menos problemas.
    Devuelve (problemas_antes, problemas_despues). Llamar justo despues de render(cid, destino)."""
    antes = ULTIMO_JUEZ.get(cid) or {"problemas": []}
    mejor = (gravedad(antes), cargar(cid), antes)
    for _ in range(intentos):
        if not mejor[2]["problemas"]:
            break
        d = json.loads(json.dumps(mejor[1]))
        if any(pr["tipo"] == "titular_tapado" for pr in mejor[2]["problemas"]):
            d["titular_detras"] = False  # el efecto revista solo vale si el titular se sigue leyendo
        for pr in mejor[2]["problemas"]:
            if pr["tipo"] != "ilegible":
                continue
            t = next((t for t in d["textos"] if t["rol"] == pr["rol"] and t["texto"].replace("*", "").startswith(pr["texto"][:20])), None)
            if not t:
                continue
            f = min(3.0, MIN_LETRA * 1.25 / max(pr["letra"], 0.002))  # cuanto mas grande tiene que ser la letra
            z = t["zona"]
            w = min(1 - 2 * MARGEN, z["w"] * f)
            h = min(0.3, z["h"] * min(1.6, max(1.0, f * f / (w / z["w"]))))  # la letra crece ~ con la raiz del area
            t["zona"] = con_margen({**z, "w": w, "h": h})
        for pr in mejor[2]["problemas"]:
            if pr["tipo"] != "encimados":
                continue
            # la tinta de uno pisa al otro (el precio heroe se sale un poco de su zona): ambos un 15% mas chicos
            for rol, txt in ((pr["rol"], pr["texto"]), (pr.get("con"), pr.get("texto2") or "")):
                t = next((t for t in d["textos"] if t["rol"] == rol and t["texto"].replace("*", "").startswith(txt[:20])), None)
                if t and rol not in ("logo", "sticker"):
                    t["zona"] = {**t["zona"], "h": round(t["zona"]["h"] * 0.85, 4), "w": round(t["zona"]["w"] * 0.92, 4)}
        suj = d.get("sujeto")
        for pr in mejor[2]["problemas"]:
            if pr["tipo"] != "sobre_sujeto" or not suj:
                continue
            t = next((t for t in d["textos"] if t["rol"] == pr["rol"] and t["texto"].replace("*", "").startswith(pr["texto"][:20])), None)
            if not t:
                continue
            # se saca de encima del sujeto: justo arriba o justo abajo de el, lo que quede libre y mas cerca
            z, s = t["zona"], suj["zona"]
            otros = [o["zona"] for o in d["textos"] if o is not t]
            for esc in (1.0, 0.8, 0.65):
                h = min(z["h"], 0.14) * esc  # una caja deformada (bug viejo) no se arrastra
                opciones = [con_margen({**z, "h": h, "cy": s["cy"] - s["h"] / 2 - HUECO - h / 2}),
                            con_margen({**z, "h": h, "cy": s["cy"] + s["h"] / 2 + HUECO + h / 2})]
                libres = [o for o in opciones if not _choca(o, s, 0) and not any(_choca(o, x) for x in otros)]
                if libres:
                    t["zona"] = min(libres, key=lambda o: abs(o["cy"] - z["cy"]))
                    break
        d["textos"], d["paneles"] = acomodar(DATOS / d["base"], d["textos"], DATOS / suj["src"] if suj else None,
                                             suj["zona"] if suj else None, bool(d.get("titular_detras")))
        guardar(cid, d)
        render(cid, destino)
        juez = ULTIMO_JUEZ.get(cid) or {"problemas": []}
        if gravedad(juez) >= mejor[0]:
            break
        mejor = (gravedad(juez), d, juez)
    if cargar(cid) != mejor[1]:  # el ultimo intento empeoro: se vuelve al mejor
        guardar(cid, mejor[1])
        render(cid, destino)
    return antes["problemas"], mejor[2]["problemas"]


def render(cid, destino: Path, fmt="png", escala=1, kit="", reticula="", letra=""):
    d = cargar(cid)
    url = (f"http://127.0.0.1:{PUERTO}/lienzo.html?id={cid}&export=1" + (f"&kit={kit}" if kit else "")
           + (f"&reticula={reticula}" if reticula else "") + (f"&letra={letra}" if letra else ""))
    args = ["node", str(ROOT / "render.mjs"), url, str(destino), fmt, str(d["w"]), str(d["h"]), str(escala)]
    with _sem:
        r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
                           env={**os.environ, "NODE_PATH": NODE_PATH})
    if r.returncode != 0:
        raise RuntimeError("render fallo: " + (r.stderr or r.stdout)[-400:])
    linea = next((l for l in r.stdout.splitlines() if l.startswith("JUEZ ")), "JUEZ null")
    ULTIMO_JUEZ[cid] = json.loads(linea[5:]) or {"problemas": [], "piezas": []}
    return destino
