"""Ming Studio: servidor local que llama a OpenRouter (key pegada en la app, o ~/.env).
Uso: python server.py  ->  http://localhost:8140
"""
import base64, io, json, os, re, secrets, shutil, subprocess, sys, threading, time, urllib.request, urllib.error, zipfile
from concurrent.futures import ThreadPoolExecutor
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote
from PIL import Image
import agente, biblioteca, disenador, kits, letras, marcas, motor, series

ROOT = Path(__file__).parent
from datos import DATOS
OUT = DATOS / "salidas"
OUT.mkdir(parents=True, exist_ok=True)
ESTILOS = OUT / "estilos"  # vistas previas de "probar estilos"; fuera de la galeria
ESTILOS.mkdir(exist_ok=True)
MINI = OUT / "mini"  # miniaturas JPG de la galeria; se rehacen solas si el PNG cambia
MINI.mkdir(exist_ok=True)
Image.MAX_IMAGE_PIXELS = 60_000_000  # una imagen trampa de miles de megapixeles no tumba el server (Ming entrega ~4 MP)
MAX_BODY = 40 * 1024 * 1024  # subidas en base64: 40 MB sobra para una foto
# solo esto se sirve como archivo: las paginas y las imagenes. Nada de memoria.json, logs, .git ni codigo
PUBLICO = re.compile(r"^/(index\.html|lienzo\.html)?$|^/(salidas|marcas_logos|biblioteca)/[\w./-]+\.(png|jpe?g|webp)$")
# contra DNS rebinding: el server solo atiende si lo llaman por su nombre. En la web: MING_HOSTS=midominio.com
HOSTS = {f"127.0.0.1:{motor.PUERTO}", f"localhost:{motor.PUERTO}", *filter(None, os.environ.get("MING_HOSTS", "").split(","))}
# fila de generaciones: cada una carga recorte (rembg) + Chromium; con 7 GB de RAM, 3 a la vez + otra cosa = MemoryError.
# Las que sobran esperan su turno en vez de romperse. En un servidor con mas RAM: MING_CONCURRENCIA=4
FILA = threading.Semaphore(int(os.environ.get("MING_CONCURRENCIA", 2)))
# disenador IA (disenador.py, probado 10/10): guardado y apagado. Se prende con MING_DISENADOR_ON=1
DISENADOR = os.environ.get("MING_DISENADOR_ON") == "1"
ALLOWED = {"inclusionai/ming-image-0.1-design", "inclusionai/ming-image-0.1-design-layer"}
# formato -> (nombre Pillow, mime, necesita RGB sin alpha)
FORMATS = {
    "png": ("PNG", "image/png", False),
    "jpg": ("JPEG", "image/jpeg", True),
    "webp": ("WEBP", "image/webp", False),
    "pdf": ("PDF", "application/pdf", True),
    "tiff": ("TIFF", "image/tiff", False),
    "bmp": ("BMP", "image/bmp", True),
    "gif": ("GIF", "image/gif", False),
    "ico": ("ICO", "image/x-icon", False),
}


REPO = "365diascollaboration-prog/ming-studio"
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()


def _v(s):
    return tuple(int(x) for x in re.findall(r"\d+", s))


def version_nueva():
    """La version publicada en GitHub si es mas nueva que la instalada; None si no hay o no hay internet."""
    try:
        with urllib.request.urlopen(f"https://raw.githubusercontent.com/{REPO}/main/VERSION", timeout=5) as r:
            remota = r.read().decode().strip()
        return remota if _v(remota) > _v(VERSION) else None
    except Exception:
        return None


def actualizar():
    """git pull + dependencias. Tus datos no se tocan: viven en la carpeta de datos, no aqui."""
    pasos = [["git", "pull", "--ff-only"],
             [sys.executable, "-m", "pip", "install", "-q", "-r", "requirements.txt"],
             ["npm", "install", "--silent"]]
    for p in pasos:
        r = subprocess.run(p, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           shell=p[0] == "npm" and os.name == "nt")  # npm es .cmd en Windows
        if r.returncode:
            return {"ok": False, "error": f"Fallo '{' '.join(p[:2])}': {(r.stderr or r.stdout)[-300:]}"}
    return {"ok": True}


def api_key(from_app):
    if from_app:
        return from_app.strip()
    # ponytail: sin key en la app, cae a ~/.env
    env = Path.home() / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("OPENROUTER_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("Pega tu key de OpenRouter arriba en la app")


def kit_para(cid, kid=None, letra=None):
    """Kit resuelto con los colores de la marca con que se hizo el diseno. Sin kid/letra conserva los del diseno."""
    actual = motor.cargar(cid).get("kit") or {}
    kid = kid or actual.get("id") or "impacto"
    letra = (actual.get("letra") or {}).get("id") if letra is None else letra
    marca = agente.estado(f"{cid}.png").get("marca")
    return kits.resolver(kid, (marcas.listar().get(marca) or {}).get("colores") if marca else None, None, letra)


def mini(name):
    """Miniatura JPG 480 px en cache; la galeria carga esto en vez del PNG de 4 MB."""
    src, dst = OUT / name, MINI / f"{Path(name).stem}.jpg"
    if not dst.is_file() or dst.stat().st_mtime < src.stat().st_mtime:
        img = Image.open(src)
        img.thumbnail((480, 480))
        if img.mode != "RGB":
            bg = Image.new("RGB", img.size, "white")
            bg.paste(img.convert("RGBA"), mask=img.convert("RGBA").split()[3])
            img = bg
        img.save(dst, "JPEG", quality=82)
    return dst.read_bytes()


def _al_formato(png, ratio, forzar):
    """(png, ok). Si la proporcion no es la pedida: con forzar se recorta al centro (el fondo es solo ambiente)."""
    img = Image.open(io.BytesIO(png))
    w, h = img.size
    if abs(w / h - ratio) / ratio <= 0.08:
        return png, True
    if not forzar:
        return png, False
    nw, nh = (round(h * ratio), h) if w / h > ratio else (w, round(w / ratio))
    x, y = (w - nw) // 2, (h - nh) // 2
    buf = io.BytesIO()
    img.crop((x, y, x + nw, y + nh)).save(buf, "PNG")
    return buf.getvalue(), True


def convert(name, fmt):
    pil, mime, flat = FORMATS[fmt]
    img = Image.open(OUT / name)
    if flat and img.mode in ("RGBA", "LA", "P"):
        bg = Image.new("RGB", img.size, "white")
        bg.paste(img.convert("RGBA"), mask=img.convert("RGBA").split()[3])
        img = bg
    if fmt == "ico":
        img.thumbnail((256, 256))
    buf = io.BytesIO()
    img.save(buf, pil, **({"quality": 95} if fmt in ("jpg", "webp") else {}))
    return buf.getvalue(), mime


class H(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(ROOT), **k)

    def translate_path(self, path):
        # las imagenes del usuario viven en la carpeta de datos; las paginas, junto al codigo
        if path.startswith(("/salidas/", "/marcas_logos/", "/biblioteca/")) and ".." not in path:
            return str(DATOS / unquote(urlparse(path).path).lstrip("/"))
        return super().translate_path(path)

    def _ajeno(self):
        """True si la peticion no es de la app: Host desconocido (DNS rebinding)."""
        host = self.headers.get("Host")
        if host not in HOSTS:
            self.send_error(403)
            return True
        # ponytail: Basic Auth solo para quien entra por el tunel (MING_CLAVE); en localhost no pide nada
        clave = os.environ.get("MING_CLAVE")
        if clave and not host.startswith(("127.0.0.1:", "localhost:")):
            esperado = "Basic " + base64.b64encode(f"ming:{clave}".encode()).decode()
            if not secrets.compare_digest(self.headers.get("Authorization", ""), esperado):
                self.send_response(401)
                self.send_header("WWW-Authenticate", 'Basic realm="Ming Studio"')
                self.send_header("Content-Length", "0")
                self.end_headers()
                return True
        return False

    def do_HEAD(self):
        if not self._ajeno():
            super().do_HEAD()

    def do_GET(self):
        if self._ajeno():
            return
        u = urlparse(self.path)
        if u.path == "/api/list":
            files = sorted(OUT.glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
            return self._json(200, {"files": [{"src": f"salidas/{p.name}", **agente.estado(p.name),
                                               "disenado": (disenador.DIR / p.stem / "meta.json").is_file()} for p in files]})
        if u.path == "/api/comp":
            cid = parse_qs(u.query).get("id", [""])[0]
            try:
                d = motor.cargar(cid)
            except FileNotFoundError:
                return self.send_error(404)
            kid = parse_qs(u.query).get("kit", [""])[0]
            if kid in kits.KITS:  # vista previa con otro kit, sin tocar el diseno guardado
                d = motor.con_kit(d, kit_para(cid, kid))
            lid = parse_qs(u.query).get("letra", [""])[0]
            if lid in letras.LETRAS or lid == "kit":  # vista previa con otra letra ("kit" = la del propio kit)
                d = motor.con_kit(d, kit_para(cid, (d.get("kit") or {}).get("id"), "" if lid == "kit" else lid))
            rid = parse_qs(u.query).get("reticula", [""])[0]
            if rid in motor.RETICULAS:  # vista previa con otra reticula
                d = motor.reticula(d, rid)
            return self._json(200, d)
        if u.path == "/api/series":
            return self._json(200, {"series": series.listar()})
        if u.path == "/api/biblioteca":
            return self._json(200, {"piezas": biblioteca.listar(), "tipos": biblioteca.TIPOS})
        if u.path == "/api/marcas":
            return self._json(200, {"marcas": {k: {**v, "logo": marcas.logo_url(k)} for k, v in marcas.listar().items()}})
        if u.path == "/api/funciones":
            return self._json(200, {"disenador": DISENADOR})
        if u.path == "/api/version":
            return self._json(200, {"local": VERSION, "nueva": version_nueva()})
        if u.path == "/api/agente/info":
            m = agente.cargar()
            return self._json(200, {
                "categorias": {k: v[0] for k, v in agente.CATEGORIAS.items()},
                "lecciones": m["lecciones"],
                "total": len(m["historial"]),
            })
        if u.path == "/api/dl":
            q = parse_qs(u.query)
            name = Path(q.get("f", [""])[0]).name  # basename: nada de ../
            fmt = q.get("fmt", ["png"])[0]
            cid = Path(name).stem
            hibrido = (motor.COMP / f"{cid}.json").is_file()
            if not (OUT / name).is_file() or (fmt not in FORMATS and not (fmt == "png2x" and hibrido)):
                return self.send_error(404)
            if hibrido and fmt in ("pdf", "png2x"):
                tmp = motor.COMP / f"{cid}.export.{'pdf' if fmt == 'pdf' else 'png'}"
                motor.render(cid, tmp, "pdf" if fmt == "pdf" else "png", 2 if fmt == "png2x" else 1)
                data, mime = tmp.read_bytes(), FORMATS["pdf" if fmt == "pdf" else "png"][1]
                tmp.unlink()
                fmt = "pdf" if fmt == "pdf" else "png"
                name = f"{cid}{'-2x' if mime == 'image/png' else ''}.png"
            else:
                data, mime = convert(name, fmt)
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Disposition", f'attachment; filename="{Path(name).stem}.{fmt}"')
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            return self.wfile.write(data)
        if u.path == "/api/mini":
            name = Path(parse_qs(u.query).get("f", [""])[0]).name
            if not name.endswith(".png") or not (OUT / name).is_file():
                return self.send_error(404)
            data = mini(name)
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            return self.wfile.write(data)
        if u.path == "/api/zip":
            names = [Path(n).name for n in parse_qs(u.query).get("f", [])]
            names = [n for n in names if (OUT / n).is_file()]
            if not names:
                return self.send_error(404)
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w") as z:
                for i, n in enumerate(names, 1):
                    z.write(OUT / n, f"capa_{i:02d}.png")
            data = buf.getvalue()
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Disposition", f'attachment; filename="capas-{Path(names[0]).stem}.zip"')
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            return self.wfile.write(data)
        ruta = unquote(u.path)
        if ".." in ruta or not PUBLICO.match(ruta):
            return self.send_error(404)
        return super().do_GET()

    def _or(self, path, body):
        r = urllib.request.Request(
            f"https://openrouter.ai/api/v1/{path}",
            data=json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {api_key(self.headers.get('X-OpenRouter-Key'))}", "Content-Type": "application/json"},
        )
        # la red falla a ratos (conexion cortada, OpenRouter saturado): 3 intentos con espera creciente.
        # Un 4xx real (key mala, sin saldo) no se reintenta: el usuario tiene que verlo ya.
        for intento in range(3):
            try:
                with urllib.request.urlopen(r, timeout=240) as resp:
                    return json.loads(resp.read())
            except urllib.error.HTTPError as e:
                if e.code != 429 and e.code < 500 or intento == 2:
                    raise
            except (urllib.error.URLError, ConnectionError, TimeoutError, OSError):
                if intento == 2:
                    raise
            time.sleep(3 * 2 ** intento)

    def do_POST(self):
        if self._ajeno():
            return
        # una web cualquiera puede mandar un form a localhost (CSRF), pero no con JSON sin pasar por CORS
        if not str(self.headers.get("Content-Type", "")).startswith("application/json"):
            return self.send_error(415)
        largo = int(self.headers.get("Content-Length") or 0)
        if largo > MAX_BODY:
            return self.send_error(413)
        try:
            req = json.loads(self.rfile.read(largo))
            chat = lambda body: self._or("chat/completions", body)
            if self.path == "/api/actualizar":
                return self._json(200, actualizar())
            if self.path == "/api/agente/prompt" and req.get("hibrido") and not req.get("rgba"):
                # motor hibrido v2: arte sin texto (fondo + sujeto) y textos exactos para el motor
                marca = req.get("marca")
                recientes = [Path(h["file"]).stem for h in agente.cargar()["historial"] if h.get("marca") == marca][-biblioteca.RECIENTES:]
                r = agente.director_v2(chat, req.get("categoria"), req.get("idea", ""), req.get("formato", "auto"),
                                       req.get("estilo", "auto"), marca, req.get("lettering", True) is not False,
                                       biblioteca.catalogo(marca, req.get("formato", "auto"), recientes) if marca else None,
                                       series.obtener(req.get("serie"), marca))
                return self._json(200, r)
            if self.path == "/api/agente/prompt":
                prompt, plan, extra = agente.crear_prompt(
                    chat, req.get("categoria"), req.get("idea", ""), req.get("rgba"), req.get("formato", "auto"),
                    req.get("estilo", "auto"), req.get("marca"), bool(req.get("hibrido")), req.get("titular_ming", True),
                    bool(req.get("solo_arte")))
                return self._json(200, {"prompt": prompt, "plan": plan, "hibrido": extra or None})
            if self.path == "/api/agente/corregir":
                prompt, plan, _ = agente.corregir(chat, Path(req["file"]).name)
                return self._json(200, {"prompt": prompt, "plan": plan})
            if self.path == "/api/agente/capas":
                return self._json(200, {"prompt": agente.capas_prompt(chat, req["image"], req.get("n", 4))})
            if self.path == "/api/marcas/guardar":
                return self._json(200, {"id": marcas.guardar(req), "marcas": marcas.listar()})
            if self.path == "/api/marcas/borrar":
                marcas.borrar(req.get("id"))
                return self._json(200, {"marcas": marcas.listar()})
            if self.path == "/api/marcas/logo":
                marcas.guardar_logo(req["id"], req["image"])
                return self._json(200, {"ok": True})
            if self.path == "/api/marcas/colores":
                return self._json(200, {"colores": marcas.colores_de_logo(req["image"])})
            if self.path == "/api/series/crear":
                stem = Path(req["file"]).stem
                sid = series.crear(stem, req.get("nombre"), agente.estado(f"{stem}.png").get("marca", ""), bool(req.get("fondo_fijo")))
                return self._json(200, {"id": sid, "series": series.listar()})
            if self.path == "/api/series/borrar":
                series.borrar(req.get("id"))
                return self._json(200, {"series": series.listar()})
            if self.path.startswith("/api/biblioteca/"):
                return self._json(200, self._biblioteca(self.path.rsplit("/", 1)[1], req, chat))
            if self.path == "/api/borrar":
                # solo el archivo; el historial se queda para que el Director no olvide lo aprendido
                f = OUT / Path(req["file"]).name
                if f.suffix != ".png" or not f.is_file():
                    raise ValueError("no existe")
                f.unlink()
                for extra in (motor.BASE / f.name, motor.BASE / f"{f.stem}-sujeto.png", motor.BASE / f"{f.stem}-sujeto-crudo.png",
                              motor.COMP / f"{f.stem}.json", MINI / f"{f.stem}.jpg", motor.BASE / f"{f.stem}-titular.png", motor.BASE / f"{f.stem}-titular-crudo.png", *ESTILOS.glob(f"{f.stem}-*.png"),
                              *motor.BASE.glob(f"{f.stem}-obj*.png")):
                    extra.unlink(missing_ok=True)
                shutil.rmtree(disenador.DIR / f.stem, ignore_errors=True)
                return self._json(200, {"ok": True})
            if self.path == "/api/comp/guardar":
                # editar texto: se re-dibuja al instante, sin volver a generar el arte
                cid = Path(req["id"]).name
                d = motor.cargar(cid)
                nuevos = {i: str(t.get("texto", "")) for i, t in enumerate(req.get("textos", []))}
                for i, t in enumerate(d["textos"]):
                    if i in nuevos and t["rol"] != "logo":
                        nuevo = nuevos[i].strip()[:600]
                        if nuevo.casefold() == t["texto"].casefold():  # solo mayusculas (la caligrafia se muestra en Tipo Titulo)
                            continue
                        if t["rol"] == "titulo":  # otro texto: el lettering ya no dice eso, vuelve a la tipografia
                            t.pop("arte", None); t.pop("arte_ming", None)
                        t["texto"] = nuevo
                motor.guardar(cid, d)
                motor.render(cid, OUT / f"{cid}.png")
                return self._json(200, {"ok": True})
            if self.path == "/api/estilos":
                # mismo arte en 3 kits mas: solo re-render del lienzo, Ming no se llama (gratis)
                cid = Path(req["file"]).stem
                actual = (motor.cargar(cid).get("kit") or {}).get("id")
                vistos = set(req.get("vistos") or []) | {actual}
                elegidos = [k for k in kits.KITS if k not in vistos][:3]

                def previa(kid):
                    destino = ESTILOS / f"{cid}-{kid}.png"
                    motor.render(cid, destino, escala=0.5, kit=kid)  # mitad de tamano: rapido y liviano
                    return {"kit": kid, "nombre": kits.KITS[kid]["nombre"], "src": f"salidas/estilos/{destino.name}?v={int(time.time())}"}
                with ThreadPoolExecutor(3) as ex:
                    previas = list(ex.map(previa, elegidos))
                quedan = len([k for k in kits.KITS if k not in vistos | set(elegidos)])
                return self._json(200, {"actual": actual, "previas": previas, "quedan": quedan})
            if self.path == "/api/letras":
                # el mismo diseno con 3 letras de grupos distintos; solo re-render, gratis
                cid = Path(req["file"]).stem
                d = motor.cargar(cid)
                if not d.get("kit"):
                    raise ValueError("Este diseño es de antes de los kits: no admite letras")
                actual = (d["kit"].get("letra") or {}).get("id")
                vistos = set(req.get("vistos") or []) | {actual}
                grupo = letras.LETRAS[actual]["grupo"] if actual in letras.LETRAS else None
                elegidas = letras.variadas(vistos, 3, grupo)

                def previa_l(lid):
                    destino = ESTILOS / f"{cid}-l-{lid}.png"
                    motor.render(cid, destino, escala=0.5, letra=lid)
                    le = letras.LETRAS[lid]
                    return {"letra": lid, "nombre": le["nombre"], "grupo": letras.GRUPOS[le["grupo"]],
                            "src": f"salidas/estilos/{destino.name}?v={int(time.time())}"}
                with ThreadPoolExecutor(3) as ex:
                    previas = list(ex.map(previa_l, elegidas))
                quedan = len([k for k in letras.LETRAS if k not in vistos | set(elegidas)])
                tit = next((t for t in d["textos"] if t["rol"] == "titulo"), {})
                return self._json(200, {"actual": actual, "previas": previas, "quedan": quedan,
                                        "ming": bool(tit.get("arte_ming")), "ming_activo": bool(tit.get("arte"))})
            if self.path == "/api/letras/usar":
                cid, lid = Path(req["file"]).stem, req.get("letra")
                if lid not in letras.LETRAS and lid not in ("kit", "ming"):
                    raise ValueError("letra invalida")
                d = motor.cargar(cid)
                for t in d["textos"]:
                    if t["rol"] == "titulo":
                        if lid == "ming" and t.get("arte_ming"):
                            t["arte"] = t["arte_ming"]
                        elif lid != "ming":
                            t.pop("arte", None)
                motor.guardar(cid, d)
                if lid != "ming":
                    motor.guardar(cid, motor.con_kit(d, kit_para(cid, None, "" if lid == "kit" else lid)))
                motor.render(cid, OUT / f"{cid}.png")
                for f in ESTILOS.glob(f"{cid}-*.png"):
                    f.unlink(missing_ok=True)
                return self._json(200, {"ok": True})
            if self.path == "/api/reticulas":
                # mismo arte y sujeto reacomodados en las 5 reticulas; solo re-render, gratis
                cid = Path(req["file"]).stem
                d = motor.cargar(cid)
                motor.reticula(d, "centrado")  # valida (sujeto, titular no pintado) antes de lanzar renders

                def previa_r(rid):
                    destino = ESTILOS / f"{cid}-r-{rid}.png"
                    motor.render(cid, destino, escala=0.5, reticula=rid)
                    return {"reticula": rid, "nombre": motor.RETICULAS[rid], "src": f"salidas/estilos/{destino.name}?v={int(time.time())}"}
                with ThreadPoolExecutor(3) as ex:
                    previas = list(ex.map(previa_r, motor.RETICULAS))
                return self._json(200, {"actual": d.get("reticula"), "previas": previas, "hay_orig": bool(d.get("orig"))})
            if self.path == "/api/reticulas/usar":
                cid, rid = Path(req["file"]).stem, req.get("reticula")
                d = motor.cargar(cid)
                if rid == "original" and d.get("orig"):
                    o = d.pop("orig")
                    for t, actual in zip(o["textos"], d["textos"]):
                        t["texto"] = actual["texto"]
                    d.update(o, banda=None, marco=False, reticula=None)
                elif rid in motor.RETICULAS:
                    d = motor.reticula(d, rid)
                else:
                    raise ValueError("reticula invalida")
                motor.guardar(cid, d)
                motor.render(cid, OUT / f"{cid}.png")
                for f in ESTILOS.glob(f"{cid}-*.png"):
                    f.unlink(missing_ok=True)
                return self._json(200, {"ok": True})
            if self.path == "/api/estilos/usar":
                cid, kid = Path(req["file"]).stem, req.get("kit")
                if kid not in kits.KITS:
                    raise ValueError("kit invalido")
                motor.guardar(cid, motor.con_kit(motor.cargar(cid), kit_para(cid, kid)))
                motor.render(cid, OUT / f"{cid}.png")
                for f in ESTILOS.glob(f"{cid}-*.png"):
                    f.unlink(missing_ok=True)
                return self._json(200, {"ok": True})
            if self.path == "/api/agente/critica":
                name = Path(req["file"]).name
                return self._json(200, agente.criticar(chat, OUT / name, name))
            if self.path == "/api/agente/calificar":
                agente.calificar(chat, Path(req["file"]).name, 1 if req.get("rating") == 1 else -1, req.get("nota", "").strip())
                return self._json(200, {"ok": True})
            if self.path == "/api/disenar" and DISENADOR:
                # disenador IA: arte limpio + textos -> pieza en HTML/CSS libre. Con "desde" + "nota" retoca un diseno
                if req.get("desde"):
                    stem, meta = disenador.retocar(chat, Path(req["desde"]).stem, req.get("nota", ""))
                else:
                    arte = OUT / Path(req["file"]).name
                    if arte.suffix != ".png" or not arte.is_file():
                        raise ValueError("no existe ese arte")
                    stem, meta = disenador.disenar(chat, arte, req.get("brief", ""), req.get("marca") or "")
                agente.registrar(f"{stem}.png", "diseno", meta["brief"], "", meta["marca"])
                return self._json(200, {"files": [f"salidas/{stem}.png"], "meta": meta})
            if self.path != "/api/gen":
                return self.send_error(404)
            if req.get("model") not in ALLOWED or not req.get("prompt"):
                raise ValueError("modelo o prompt invalido")
            body = {"model": req["model"], "prompt": req["prompt"], "n": 1, "output_format": "png"}
            if req.get("image"):
                body["input_references"] = [{"type": "image_url", "image_url": {"url": req["image"]}}]
            hib, desde = req.get("hibrido"), Path(str(req.get("desde") or "")).stem
            if not hib and desde and (motor.COMP / f"{desde}.json").is_file():
                c = motor.cargar(desde)
                if c.get("prompts"):  # otra version / correccion de un diseno v2: mismos textos, arte nuevo
                    hib = {"v": 2, "sujeto": c["prompts"].get("sujeto"), "sujeto_zona": c["prompts"].get("sujeto_zona"),
                           "titular_detras": c.get("titular_detras", False), "textos": c["textos"], "fuentes": c["fuentes"],
                           "kit": c.get("kit"), "lettering": c["prompts"].get("lettering"),
                           # otra version: el plato de la biblioteca se queda (es el real), el fondo se pinta nuevo
                           "biblioteca": {"sujeto": (c["prompts"].get("biblioteca") or {}).get("sujeto")}}
                    req["hibrido"] = hib
            if hib and hib.get("v") == 2 and req["model"] == "inclusionai/ming-image-0.1-design":
                with FILA:
                    return self._gen_v2(req, hib, chat)
            if req.get("solo_arte") and req["model"] == "inclusionai/ming-image-0.1-design" and not req.get("image"):
                # arte limpio: el detector repinta si Ming cuela letras (Ming es gratis, el detector casi)
                with FILA:
                    png, colado = self._pintar_sin_texto(req["prompt"], chat)
                name = f"{time.strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(2)}.png"
                (OUT / name).write_bytes(png)
                agente.registrar(name, req.get("categoria"), req.get("idea"), req["prompt"], req.get("marca"))
                return self._json(200, {"files": [f"salidas/{name}"], "reintentos_por_texto": colado})
            data = self._or("images", body)
            files = []
            stamp = time.strftime("%Y%m%d-%H%M%S")
            for i, img in enumerate(data.get("data", []), 1):
                name = f"{stamp}-{i:02d}.png"
                png = base64.b64decode(img["b64_json"])
                hib = req.get("hibrido")
                desde = Path(str(req.get("desde") or "")).stem
                if not hib and desde and (motor.COMP / f"{desde}.json").is_file():
                    c = motor.cargar(desde)
                    hib = {"textos": c["textos"], "fuentes": c["fuentes"]}
                if hib and req["model"] == "inclusionai/ming-image-0.1-design":
                    (motor.BASE / name).write_bytes(png)
                    textos, fuentes = motor.normalizar(hib.get("textos"), hib.get("fuentes"))
                    logo = marcas.logo_url(req.get("marca")) if any(t["rol"] == "logo" for t in textos) else ""
                    motor.crear(Path(name).stem, motor.BASE / name, textos, fuentes, logo)
                    motor.render(Path(name).stem, OUT / name)
                else:
                    (OUT / name).write_bytes(png)
                agente.registrar(name, req.get("categoria"), req.get("idea"), req["prompt"], req.get("marca"))
                files.append(f"salidas/{name}")
            self._json(200, {"files": files, "usage": data.get("usage")})
        except urllib.error.HTTPError as e:
            self._json(e.code, {"error": e.read().decode(errors="replace")})
        except Exception as e:
            self._json(500, {"error": str(e)})

    def _pintar_sin_texto(self, prompt, chat, fondo=False):
        """Ming pinta; el Director revisa si colo letras y, si si, se repinta con la prohibicion reforzada.
        Maximo 3 intentos (Ming es gratis). Devuelve (png, lo_que_se_colo_en_cada_intento)."""
        try:
            prompt = json.dumps(agente._sin_texto(json.loads(prompt)), ensure_ascii=False)
        except ValueError:
            pass
        colado = []
        try:
            pedido = biblioteca.RATIOS.get(json.loads(prompt).get("canvas_settings", {}).get("aspect_ratio")) if fondo else None
        except ValueError:
            pedido = None
        for intento in range(3):
            d = self._or("images", {"model": "inclusionai/ming-image-0.1-design", "prompt": prompt, "n": 1, "output_format": "png"})
            png = base64.b64decode(d["data"][0]["b64_json"])
            if pedido:  # Ming a veces ignora el formato (se pidio 9:16 y entrego 16:9): se repinta y, si insiste, se recorta
                png, ok = _al_formato(png, pedido, intento == 2)
                if not ok:
                    colado.append(f"formato equivocado (intento {intento + 1})")
                    continue
            try:
                hay, donde = agente.detectar_texto(chat, png, fondo)
            except Exception:  # si el detector falla, no se bloquea el diseno
                hay, donde = False, ""
            if not hay or intento == 2:
                return png, colado
            colado.append(donde)
            prompt = agente.reforzar_sin_texto(prompt, fondo)

    def _pintar_titular(self, lettering, chat):
        """Ming rotula el titular; el Director lo lee. Si no dice EXACTO lo esperado, se repinta (max 3, Ming es gratis).
        Devuelve (png o None, lo que leyo en cada intento)."""
        caption, esperado, leidos = lettering["caption"], lettering["esperado"], []
        for intento in range(3):
            d = self._or("images", {"model": "inclusionai/ming-image-0.1-design", "prompt": caption, "n": 1, "output_format": "png"})
            png = base64.b64decode(d["data"][0]["b64_json"])
            try:
                leido = agente.leer_titular(chat, png)
            except Exception:  # si no se puede leer, no se arriesga: va con fuente
                return None, leidos + ["(no se pudo leer)"]
            if agente.titular_correcto(leido, esperado):
                return png, leidos
            leidos.append(leido)
            caption = agente.reforzar_lettering(lettering["caption"], esperado, leido)
        return None, leidos

    def _gen_v2(self, req, hib, chat):
        # piezas de la biblioteca: se revalidan aqui (aprobadas, de esta marca) y esas NO se pintan
        bib, marca = hib.get("biblioteca") or {}, req.get("marca") or ""
        fondo_b = biblioteca.pieza(bib.get("fondo"), "fondo", marca)
        sujeto_b = biblioteca.pieza(bib.get("sujeto"), "sujeto", marca)
        objetos_b = [(p, o["zona"]) for o in bib.get("objetos") or [] if isinstance(o, dict) and isinstance(o.get("zona"), dict)
                     and (p := biblioteca.pieza(o.get("id"), "objeto", marca))]
        piezas = {} if fondo_b else {"fondo": req["prompt"]}
        if hib.get("sujeto") and not sujeto_b:
            piezas["sujeto"] = agente.forzar_croma(hib["sujeto"])
        letrero = hib.get("lettering") if isinstance(hib.get("lettering"), dict) else None
        with ThreadPoolExecutor(3) as ex:  # fondo, sujeto y titular se pintan a la vez
            futuros = {k: ex.submit(self._pintar_sin_texto, v, chat, k == "fondo") for k, v in piezas.items()}
            f_tit = ex.submit(self._pintar_titular, letrero, chat) if letrero else None
            res = {k: f.result() for k, f in futuros.items()}
            try:
                tit_png, leidos = f_tit.result() if f_tit else (None, [])
            except Exception as e:  # el titular de Ming es un extra: si falla, el diseno sale con la fuente
                tit_png, leidos = None, [f"error: {str(e)[:120]}"]
        stem = f"{time.strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(2)}"
        name = f"{stem}.png"
        if fondo_b:
            shutil.copyfile(biblioteca.BIB / f"{fondo_b['id']}.png", motor.BASE / name)
        else:
            (motor.BASE / name).write_bytes(res["fondo"][0])
        sujeto_png = None
        if sujeto_b:  # copia: si luego borras la pieza de la biblioteca, el diseno sigue intacto
            sujeto_png = motor.BASE / f"{stem}-sujeto.png"
            shutil.copyfile(biblioteca.BIB / f"{sujeto_b['id']}.png", sujeto_png)
        elif "sujeto" in res:
            crudo = motor.BASE / f"{stem}-sujeto-crudo.png"
            crudo.write_bytes(res["sujeto"][0])
            sujeto_png = motor.recortar_sujeto(crudo, motor.BASE / f"{stem}-sujeto.png")  # el crudo se guarda para re-recortar
        titular_png = None
        if tit_png:
            crudo = motor.BASE / f"{stem}-titular-crudo.png"
            crudo.write_bytes(tit_png)
            try:
                titular_png = motor.recortar_letras(crudo, motor.BASE / f"{stem}-titular.png")
                # segunda lectura DESPUES del recorte: si las letras tenian color parecido al croma, el recorte se las
                # come y el titular queda como una mancha. Se lee sobre gris, como se veria en el diseno.
                rec = Image.open(titular_png).convert("RGBA")
                plano = Image.new("RGB", rec.size, (110, 110, 110))
                plano.paste(rec, mask=rec.getchannel("A"))
                buf = io.BytesIO()
                plano.save(buf, "PNG")
                leido = agente.leer_titular(chat, buf.getvalue())
                if not agente.titular_correcto(leido, letrero["esperado"]):
                    leidos.append(f"tras recortar se lee: {leido}")
                    titular_png = None
            except Exception as e:
                titular_png = None
                leidos.append(f"recorte: {str(e)[:120]}")
        textos, fuentes = motor.normalizar(hib.get("textos"), hib.get("fuentes"))
        logo = marcas.logo_url(req.get("marca")) if any(t["rol"] == "logo" for t in textos) else ""
        objetos = []
        for i, (p, z) in enumerate(objetos_b):
            destino = motor.BASE / f"{stem}-obj{i}.png"
            shutil.copyfile(biblioteca.BIB / f"{p['id']}.png", destino)
            objetos.append((destino, z))
        usados = {k: p["id"] for k, p in (("fondo", fondo_b), ("sujeto", sujeto_b)) if p}
        datos = motor.crear(stem, motor.BASE / name, textos, fuentes, logo, sujeto_png, hib.get("sujeto_zona"),
                            bool(hib.get("titular_detras")),
                            prompts={"fondo": req["prompt"], "sujeto": hib.get("sujeto"), "sujeto_zona": hib.get("sujeto_zona"),
                                     "lettering": letrero, "biblioteca": usados or None},
                            kit=hib.get("kit") if isinstance(hib.get("kit"), dict) else None, titular_png=titular_png, objetos=objetos)
        puestos = {Path(o["src"]).name for o in datos.get("objetos", [])}
        objetos_usados = [p for i, (p, _) in enumerate(objetos_b) if f"{stem}-obj{i}.png" in puestos]
        for i in range(len(objetos_b)):  # los que chocaban con texto no se dibujan: fuera
            if f"{stem}-obj{i}.png" not in puestos:
                (motor.BASE / f"{stem}-obj{i}.png").unlink(missing_ok=True)
        biblioteca.usar([*usados.values(), *(p["id"] for p in objetos_usados)], stem)
        motor.render(stem, OUT / name)
        antes, despues = motor.pulir(stem, OUT / name)  # el juez mide y el motor corrige el layout, gratis
        agente.registrar(name, req.get("categoria"), req.get("idea"), req["prompt"], req.get("marca"))
        colado = [d for _, c in res.values() for d in c]
        titular = None if not letrero else {"ming": bool(titular_png), "esperado": letrero["esperado"], "leidos": leidos}
        reusado = [p["nombre"] or p["tipo"] for p in (sujeto_b, fondo_b, *objetos_usados) if p]
        nuevo = [k for k in ("sujeto", "fondo") if k in res]
        return self._json(200, {"files": [f"salidas/{name}"], "reintentos_por_texto": colado, "titular": titular,
                                "biblioteca": {"reusado": reusado, "nuevo": nuevo},
                                "juez": {"corregidos": len(antes) - len(despues), "quedan": despues}})

    def _biblioteca(self, accion, req, chat):
        def con_ficha(pieza):  # el Director nombra y etiqueta; si falla (sin key, etc.) la pieza queda igual
            try:
                return biblioteca.ficha(chat, pieza["id"])
            except Exception:
                return pieza
        if accion == "estrella":  # desde la galeria: guardar fondo, sujeto o ambos de un diseno hibrido
            stem = Path(req["file"]).stem
            hay = biblioteca.de_diseno(stem)
            quiere = ["fondo", "sujeto"] if req.get("que") == "ambos" else [req.get("que")]
            faltan = [q for q in quiere if q not in hay]
            if faltan == quiere:
                raise ValueError("Este diseño no tiene " + " ni ".join(biblioteca.TIPOS.get(q, q).lower() for q in faltan) + " aparte")
            marca = agente.estado(f"{stem}.png").get("marca", "")
            piezas = []
            for q in quiere:
                if q in hay:
                    p = biblioteca.agregar(hay[q], q, marca, "ok", f"diseno:{stem}")
                    if p["estado"] != "ok":  # si venia de la bandeja "por revisar", la estrella la aprueba
                        p = biblioteca.editar(p["id"], {"estado": "ok"})
                    piezas.append(con_ficha(p))
            return {"piezas": piezas, "faltan": faltan}
        if accion == "subir":
            tipo = req.get("tipo")
            img = biblioteca.de_data_url(req["image"])
            if tipo != "fondo" and not (img.mode in ("RGBA", "LA", "P") and img.convert("RGBA").getchannel("A").getextrema()[0] < 250):
                # foto con fondo: se recorta y va a revisar para que apruebes el recorte
                biblioteca._rutas()
                crudo = biblioteca.BIB / f"subida-{secrets.token_hex(4)}.png"
                img.convert("RGB").save(crudo)
                try:
                    img = Image.open(motor.recortar_sujeto(crudo, crudo.with_suffix(".rec.png")))
                    img.load()
                finally:
                    crudo.unlink(missing_ok=True)
                    crudo.with_suffix(".rec.png").unlink(missing_ok=True)
                pieza = biblioteca.agregar(img, tipo, req.get("marca", ""), "revisar")
            else:
                pieza = biblioteca.agregar(img, tipo, req.get("marca", ""), "ok")
            return {"pieza": con_ficha(pieza)}
        if accion == "importar":
            return {"nuevas": biblioteca.importar(lambda stem: agente.estado(f"{stem}.png").get("marca", ""))}
        if accion == "editar":
            pieza = biblioteca.editar(req["id"], req)
            if pieza["estado"] == "ok" and (not pieza["nombre"] or not pieza["etiquetas"]):
                pieza = con_ficha(pieza)
            return {"pieza": pieza}
        if accion == "borrar":
            biblioteca.borrar(req["id"])
            return {"ok": True}
        raise ValueError("accion invalida")

    def _json(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)


if __name__ == "__main__":
    srv = ThreadingHTTPServer(("127.0.0.1", motor.PUERTO), H)
    url = f"http://127.0.0.1:{motor.PUERTO}"
    print(f"Ming Studio en {url}  (tus datos: {DATOS})  Cierra esta ventana para apagarlo.")
    if "--abrir" in sys.argv:  # los lanzadores abren el navegador cuando el server ya escucha
        import webbrowser
        webbrowser.open(url)
    srv.serve_forever()
