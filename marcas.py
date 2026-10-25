"""Kits de marca: identidad de cada negocio que el Director aplica en cada diseno."""
import base64, io, json, re, threading, unicodedata
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).parent
from datos import DATOS
ARCHIVO = DATOS / "marcas.json"
LOGOS = DATOS / "marcas_logos"
_lock = threading.Lock()
CAMPOS = ("nombre", "rubro", "colores", "tipografias", "tono", "estilo", "datos", "evitar")
HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def listar():
    return json.loads(ARCHIVO.read_text(encoding="utf-8")) if ARCHIVO.exists() else {}


def _guardar_todo(d):
    tmp = ARCHIVO.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(ARCHIVO)


def _slug(nombre):
    s = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-") or "marca"


def guardar(m):
    nombre = str(m.get("nombre", "")).strip()
    if not nombre:
        raise ValueError("La marca necesita un nombre")
    limpio = {k: str(m.get(k, "")).strip()[:600] for k in CAMPOS if k != "colores"}
    limpio["nombre"] = nombre[:80]
    limpio["colores"] = [c.lower() for c in m.get("colores", []) if isinstance(c, str) and HEX.match(c)][:6]
    with _lock:
        d = listar()
        mid = m.get("id") if m.get("id") in d else _slug(nombre)
        d[mid] = limpio
        _guardar_todo(d)
    return mid


def borrar(mid):
    with _lock:
        d = listar()
        d.pop(mid, None)
        _guardar_todo(d)
    if re.fullmatch(r"[a-z0-9-]+", str(mid)):
        (LOGOS / f"{mid}.png").unlink(missing_ok=True)


def guardar_logo(mid, data_url):
    """Logo oficial: se guarda como PNG conservando la transparencia, maximo 1024px."""
    if mid not in listar():
        raise ValueError("marca no existe")
    img = Image.open(io.BytesIO(base64.b64decode(data_url.split(",", 1)[1]))).convert("RGBA")
    img.thumbnail((1024, 1024))
    LOGOS.mkdir(exist_ok=True)
    img.save(LOGOS / f"{mid}.png")


def logo_url(mid):
    return f"marcas_logos/{mid}.png" if mid and re.fullmatch(r"[a-z0-9-]+", mid) and (LOGOS / f"{mid}.png").is_file() else ""


def colores_de_logo(data_url, n=5):
    """Colores dominantes del logo, sin IA: Pillow cuantiza y descarta transparente y casi blanco/negro puro."""
    img = Image.open(io.BytesIO(base64.b64decode(data_url.split(",", 1)[1]))).convert("RGBA")
    img.thumbnail((200, 200))
    px = [p[:3] for p in img.get_flattened_data() if p[3] > 128]
    if not px:
        return []
    plano = Image.new("RGB", (len(px), 1))
    plano.putdata(px)
    q = plano.quantize(colors=12)
    pal = q.getpalette()
    out = []
    for cuenta, i in sorted(q.getcolors(), reverse=True):
        r, g, b = pal[i * 3:i * 3 + 3]
        if min(r, g, b) > 235 or max(r, g, b) < 20:  # fondo blanco o negro puro
            continue
        # ponytail: distancia RGB simple para no repetir tonos casi iguales; Lab si hace falta mas precision
        if any(abs(r - a) + abs(g - b2) + abs(b - c) < 60 for a, b2, c in out):
            continue
        out.append((r, g, b))
        if len(out) == n:
            break
    return [f"#{r:02x}{g:02x}{b:02x}" for r, g, b in out]


def bloque_director(mid):
    """Texto que se le agrega al encargo del Director."""
    m = listar().get(mid)
    if not m:
        return ""
    lineas = [f"KIT DE MARCA OBLIGATORIO: {m['nombre']}. Aplica esta identidad en todo el diseno."]
    etiquetas = {"rubro": "A que se dedica", "tipografias": "Tipografias de la marca", "tono": "Tono de voz",
                 "estilo": "Estilo visual", "datos": "Datos fijos (usalos solo si la pieza lleva contacto)", "evitar": "Nunca usar"}
    if m.get("colores"):
        lineas.append(f"- Paleta oficial (usa estos hex exactos como colores dominantes y de acento): {', '.join(m['colores'])}")
    for k, t in etiquetas.items():
        if m.get(k):
            lineas.append(f"- {t}: {m[k]}")
    if logo_url(mid):
        lineas.append("- La marca TIENE LOGO OFICIAL: reserva un bloque rol \"logo\" (texto vacio) en `textos` y no dibujes ningun logo en el arte.")
    lineas.append(f"- El nombre de la marca se escribe exactamente \"{m['nombre']}\" cuando aparezca.")
    return "\n".join(lineas)


if __name__ == "__main__":
    import tempfile
    ARCHIVO = Path(tempfile.mkdtemp()) / "marcas.json"
    mid = guardar({"nombre": "Mercado Caribe", "colores": ["#0F8B8D", "rojo", "#FF6B4A"], "tono": "alegre"})
    assert mid == "mercado-caribe" and listar()[mid]["colores"] == ["#0f8b8d", "#ff6b4a"]
    assert "#0f8b8d" in bloque_director(mid) and "alegre" in bloque_director(mid)
    buf = io.BytesIO()
    logo = Image.new("RGBA", (100, 100), (255, 255, 255, 0))
    logo.paste((200, 30, 30, 255), (0, 0, 50, 100))
    logo.paste((20, 120, 200, 255), (50, 0, 100, 100))
    logo.save(buf, "PNG")
    cols = colores_de_logo("data:image/png;base64," + base64.b64encode(buf.getvalue()).decode())
    assert len(cols) == 2, cols
    borrar(mid)
    assert listar() == {}
    print("ok")
