"""Biblioteca por marca: piezas curadas (fondos, platos/sujetos, objetos) que luego el Director reusa.
Las piezas son COPIAS: borrar un diseno de la galeria no toca la biblioteca.
Indice en biblioteca/biblioteca.json; archivos planos biblioteca/<id>.png (cambiar marca o tipo no mueve nada)."""
import base64, io, json, re, secrets, shutil, threading, time
from pathlib import Path
from PIL import Image
import agente, motor

ROOT = Path(__file__).parent
from datos import DATOS
BIB = DATOS / "biblioteca"
INDICE = BIB / "biblioteca.json"
MINI = BIB / "mini"  # miniaturas PNG 360 px (conservan transparencia)
TIPOS = {"fondo": "Fondo", "sujeto": "Plato / sujeto", "objeto": "Objeto"}
_lock = threading.Lock()


def _rutas():
    BIB.mkdir(exist_ok=True)
    MINI.mkdir(exist_ok=True)


def listar():
    return json.loads(INDICE.read_text(encoding="utf-8")) if INDICE.exists() else []


def _guardar_todo(piezas):
    tmp = INDICE.with_suffix(".tmp")
    tmp.write_text(json.dumps(piezas, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(INDICE)


def _mutar(fn):
    with _lock:
        piezas = listar()
        r = fn(piezas)
        _guardar_todo(piezas)
        return r


def _miniatura(img, destino):
    img = img.copy()
    img.thumbnail((360, 360))
    img.save(destino, optimize=True)


def agregar(img, tipo, marca="", estado="ok", origen="subida", nombre="", etiquetas=None):
    """img: Path o PIL.Image. Devuelve la pieza; si el mismo origen+tipo ya existe, devuelve esa (no duplica)."""
    if tipo not in TIPOS:
        raise ValueError("tipo invalido")
    _rutas()
    if origen != "subida":
        ya = next((p for p in listar() if p["origen"] == origen and p["tipo"] == tipo), None)
        if ya:
            return ya
    pid = f"{time.strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(3)}"
    if isinstance(img, (str, Path)) and Path(img).suffix == ".png":
        shutil.copyfile(img, BIB / f"{pid}.png")  # copia tal cual: re-codificar un PNG de 4 MB tarda ~0.3 s
        im = Image.open(img)
    else:
        im = Image.open(img) if isinstance(img, (str, Path)) else img
        im = im.convert("RGBA" if tipo != "fondo" else "RGB")
        im.save(BIB / f"{pid}.png")
    _miniatura(im, MINI / f"{pid}.png")
    pieza = {"id": pid, "tipo": tipo, "marca": marca or "", "nombre": nombre[:80], "etiquetas": list(etiquetas or [])[:8],
             "estado": estado, "origen": origen, "ancho": im.width, "alto": im.height}
    _mutar(lambda ps: ps.append(pieza))
    return pieza


def _id(pid):
    """Los ids los genera el server; cualquier otra cosa (../, rutas) se rechaza antes de tocar archivos."""
    if not re.fullmatch(r"\d{14}-[0-9a-f]{6}", str(pid)):
        raise KeyError("pieza no existe")
    return pid


def editar(pid, campos):
    _id(pid)
    def fn(ps):
        p = next((x for x in ps if x["id"] == pid), None)
        if not p:
            raise KeyError("pieza no existe")
        if "nombre" in campos:
            p["nombre"] = str(campos["nombre"]).strip()[:80]
        if "etiquetas" in campos:
            e = campos["etiquetas"]
            e = e.split(",") if isinstance(e, str) else e
            p["etiquetas"] = [str(x).strip().lower()[:30] for x in e if str(x).strip()][:8]
        if "marca" in campos:
            p["marca"] = str(campos["marca"] or "")
        if campos.get("tipo") in TIPOS:
            p["tipo"] = campos["tipo"]
        if campos.get("estado") in ("ok", "revisar"):
            p["estado"] = campos["estado"]
        return dict(p)
    return _mutar(fn)


def borrar(pid):
    _id(pid)
    _mutar(lambda ps: ps.__setitem__(slice(None), [p for p in ps if p["id"] != pid]))
    (BIB / f"{pid}.png").unlink(missing_ok=True)
    (MINI / f"{pid}.png").unlink(missing_ok=True)


def de_diseno(stem):
    """Piezas que tiene un diseno hibrido: el fondo (sin texto) y el sujeto recortado, si existen."""
    piezas = {}
    if (motor.COMP / f"{stem}.json").is_file() and (motor.BASE / f"{stem}.png").is_file():
        piezas["fondo"] = motor.BASE / f"{stem}.png"
    if (motor.BASE / f"{stem}-sujeto.png").is_file():
        piezas["sujeto"] = motor.BASE / f"{stem}-sujeto.png"
    return piezas


def importar(marca_de):
    """Los disenos viejos entran a la bandeja "por revisar", nunca directo. marca_de(stem) -> id de marca."""
    nuevas = 0
    ya = {(p["origen"], p["tipo"]) for p in listar()}
    for comp in sorted(motor.COMP.glob("*.json")):
        stem = comp.stem
        if "." in stem:  # *.export.* temporales
            continue
        for tipo, ruta in de_diseno(stem).items():
            if (f"diseno:{stem}", tipo) in ya:
                continue
            try:
                agregar(ruta, tipo, marca_de(stem), "revisar", f"diseno:{stem}")
                nuevas += 1
            except OSError:  # archivo corrupto o a medio escribir: se salta
                pass
    return nuevas


def ficha(chat, pid):
    """El Director mira la pieza y llena nombre + etiquetas de ambiente. Solo pisa lo que este vacio."""
    p = next((x for x in listar() if x["id"] == pid), None)
    if not p:
        raise KeyError("pieza no existe")
    img = Image.open(BIB / f"{pid}.png").convert("RGBA")
    img.thumbnail((768, 768))
    fondo = Image.new("RGB", img.size, (128, 128, 128))  # recortes sobre gris para que se vean
    fondo.paste(img, mask=img.getchannel("A"))
    buf = io.BytesIO()
    fondo.save(buf, "JPEG", quality=88)
    que = {"fondo": "a background / environment for a design", "sujeto": "a dish or main subject cut out",
           "objeto": "a decorative object cut out"}[p["tipo"]]
    out = agente._json_de(chat({
        "model": agente.MODEL, "temperature": 0.2, "max_tokens": 200, **agente.RAPIDO,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": (
                f"The image is {que}. Name it like a Latin American designer would catalog it, in neutral Spanish. "
                "Dishes by their real name if recognizable (mofongo, tostones, pernil...). "
                'Answer ONLY JSON: {"nombre": "2 to 5 words", "etiquetas": ["3 to 6 lowercase Spanish mood/setting tags, e.g. noche, tropical, elegante, madera"]}')},
            {"role": "user", "content": [{"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()}}]},
        ],
    }))
    campos = {}
    if not p["nombre"] and out.get("nombre"):
        campos["nombre"] = out["nombre"]
    if not p["etiquetas"] and isinstance(out.get("etiquetas"), list):
        campos["etiquetas"] = out["etiquetas"]
    return editar(pid, campos)


def de_data_url(data_url):
    return Image.open(io.BytesIO(base64.b64decode(data_url.split(",", 1)[-1])))


# ---- Paso 2: el Director mezcla con criterio ----
RECIENTES = 5  # un fondo usado en los ultimos 5 disenos de la marca no se ofrece (evita "otra vez el mismo")
RATIOS = {"1:1": 1, "4:5": 0.8, "3:4": 0.75, "2:3": 2 / 3, "9:16": 9 / 16, "16:9": 16 / 9, "16:10": 1.6}


def ratio(p):
    """Formato estandar mas cercano a la pieza."""
    r = p["ancho"] / p["alto"]
    return min(RATIOS, key=lambda k: abs(RATIOS[k] - r))


def pieza(pid, tipo, marca):
    """La pieza solo vale si existe, esta aprobada y es de esa marca y tipo (el Director puede inventar ids)."""
    p = next((x for x in listar() if x["id"] == pid), None) if pid else None
    if p and p["tipo"] == tipo and p["estado"] == "ok" and p["marca"] == (marca or "") and (BIB / f"{pid}.png").is_file():
        return p
    return None


def catalogo(marca, formato, recientes):
    """Piezas aprobadas que el Director puede usar en este encargo, y el texto que las describe."""
    ps = [p for p in listar() if p["estado"] == "ok" and p["marca"] == (marca or "") and marca]
    ps = [p for p in ps if p["tipo"] != "fondo" or (not set(p.get("usos", [])) & set(recientes)
                                                    and (formato not in RATIOS or ratio(p) == formato))]
    lineas = [f'- [{p["id"]}] {TIPOS[p["tipo"]]}: "{p["nombre"] or "sin nombre"}"'
              + (f' ({", ".join(p["etiquetas"])})' if p["etiquetas"] else "")
              + (f' formato {ratio(p)}' if p["tipo"] == "fondo" else "") for p in ps[-60:]]
    return {"piezas": {p["id"]: p for p in ps[-60:]}, "texto": "BIBLIOTECA DE LA MARCA (aprobada por el cliente):\n" + "\n".join(lineas)}


def usar(pids, stem):
    def fn(ps):
        for p in ps:
            if p["id"] in pids:
                p["usos"] = (p.get("usos", []) + [stem])[-20:]
    if pids:
        _mutar(fn)
