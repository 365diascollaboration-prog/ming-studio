"""Series por marca: la receta congelada de un diseno que gusto (kit, letra, formato, layout, zona del plato y,
si se quiere, el fondo). Cada semana solo cambian el plato y el texto: "Mercado Caribe: Viernes de Salsa"."""
import json, re, threading, unicodedata
from pathlib import Path
import biblioteca, motor

ROOT = Path(__file__).parent
from datos import DATOS
ARCHIVO = DATOS / "series.json"
_lock = threading.Lock()
ESTILO = ("rol", "zona", "alinear", "color", "fuente", "peso", "mayusculas", "fondo", "vinieta")  # lo que se congela de cada texto


def listar():
    return json.loads(ARCHIVO.read_text(encoding="utf-8")) if ARCHIVO.exists() else {}


def _guardar_todo(d):
    tmp = ARCHIVO.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(ARCHIVO)


def _slug(marca, nombre):
    s = unicodedata.normalize("NFKD", f"{marca}-{nombre}").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-") or "serie"


def crear(stem, nombre, marca, fondo_fijo=False):
    """Congela el diseno `stem` tal como se ve ahora (con el kit, la letra y la reticula que tenga)."""
    nombre = str(nombre or "").strip()[:60]
    if not nombre:
        raise ValueError("Ponle nombre a la serie")
    d = motor.cargar(stem)
    if not d.get("kit"):
        raise ValueError("Este diseño es de antes de los kits: no sirve de serie")
    fondo = None
    if fondo_fijo:  # el fondo entra a la biblioteca aprobado; la serie lo usa siempre
        p = biblioteca.agregar(motor.BASE / Path(d["base"]).name, "fondo", marca, "ok", f"diseno:{stem}")
        fondo = (biblioteca.editar(p["id"], {"estado": "ok"}) if p["estado"] != "ok" else p)["id"]
    zona = (d.get("prompts") or {}).get("sujeto_zona") or (d.get("sujeto") or {}).get("zona")
    serie = {"nombre": nombre, "marca": marca or "", "desde": stem, "kit": d["kit"],
             "formato": biblioteca.ratio({"ancho": d["w"], "alto": d["h"]}),
             "textos": [{k: t[k] for k in ESTILO if k in t} for t in d["textos"]],
             "sujeto_zona": zona, "titular_detras": bool(d.get("titular_detras")), "fondo": fondo,
             "ambiente": (d.get("prompts") or {}).get("fondo") or ""}
    with _lock:
        todas = listar()
        sid = _slug(marca, nombre)
        todas[sid] = serie
        _guardar_todo(todas)
    return sid


def borrar(sid):
    with _lock:
        todas = listar()
        todas.pop(sid, None)
        _guardar_todo(todas)


def obtener(sid, marca):
    s = listar().get(sid) if sid else None
    return {**s, "id": sid} if s and s["marca"] == (marca or "") else None


def encargo(serie):
    """Lo que el Director necesita saber para escribir la entrega de esta semana."""
    roles = [t["rol"] for t in serie["textos"] if t["rol"] != "logo"]
    return (f'SERIE "{serie["nombre"]}": este diseno es una entrega mas de una serie. La cara (formato, tipografia, layout) '
            f"ya esta fija; tu escribes SOLO el contenido nuevo.\n- textos: exactamente estos roles y en este orden: {', '.join(roles)}. "
            "Mismo tono y largo parecido al de la serie.\n"
            + ("- fondo: es fijo de la serie (escribelo igual, como respaldo).\n" if serie.get("fondo") else
               "- fondo: el MISMO ambiente, luz y paleta que la serie; varia solo detalles. Referencia del fondo de la serie:\n"
               + str(serie.get("ambiente", ""))[:1200] + "\n")
            + "- sujeto: el plato o protagonista de ESTA entrega (reusa el de la biblioteca si es el mismo).")


def aplicar(textos, serie):
    """Los textos del Director toman la posicion y el estilo congelados, rol por rol en orden.
    Lo que la serie no tiene se descarta (la cara no cambia); el logo de la serie se queda tal cual."""
    libres = list(textos)
    out = []
    for p in serie["textos"]:
        if p["rol"] == "logo":
            out.append({**p, "texto": next((t["texto"] for t in textos if t["rol"] == "logo"), "")})
            continue
        t = next((t for t in libres if t["rol"] == p["rol"]), None)
        if t:
            libres.remove(t)
            out.append({**t, **p, "texto": t["texto"]})
    return out
