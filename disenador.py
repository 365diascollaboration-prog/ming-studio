"""Disenador IA: un modelo fuerte con vision mira el arte limpio de Ming y escribe la pieza en HTML/CSS libre,
como lo haria un disenador senior (sin plantillas, sin kits). Despues mira su propio render y lo corrige.
Cada diseno vive en salidas/disenos/<stem>/ (index.html + arte + logo + meta.json) para poder retocarlo con notas.
"""
import base64, io, json, os, re, secrets, shutil, subprocess, time
from pathlib import Path
from PIL import Image
import marcas, motor

MODEL = os.environ.get("MING_DISENADOR", "qwen/qwen3.8-flash")
DIR = motor.OUT / "disenos"
DIR.mkdir(exist_ok=True)
ANCHO = 1080  # px CSS del lienzo; se renderiza a 2x (2160 px de ancho)
RONDAS = int(os.environ.get("MING_DISENADOR_RONDAS", 1))  # revisiones del propio render despues del primer borrador

SISTEMA = """Eres un director de arte senior de LATAM que disena flyers y posts que venden (nightlife, restaurantes, marcas).
Te dan un ARTE LIMPIO (sin texto) pintado por IA y un encargo. Tu trabajo: escribir UNA pagina HTML+CSS que ponga
encima los textos con criterio de disenador profesional. El arte ya es bueno: tu aportas tipografia, jerarquia y acabado.

Como trabajas:
1. LEE el arte antes de escribir: donde esta el sujeto, donde hay aire (zonas oscuras/limpias), de donde viene la luz,
   que colores dominan. Los textos van en el aire, NUNCA tapando la parte importante del sujeto.
2. Si el aire no alcanza, lo creas: degradados oscuros (scrims) arriba/abajo, o mueves el arte un poco
   (top negativo, scale leve). Nunca recortes la parte importante del sujeto.
3. Jerarquia clara que se lea en un celular: UN titular protagonista enorme, un acento (script, neon o color),
   un bloque de info, precios grandes si hay precios, un llamado a la accion (pastilla/boton) y un pie con contacto.
4. Tipografia: maximo 3 familias de Google Fonts que combinen (display + script/acento + sans legible).
   Nada de Arial/Times. Tamanos con intencion: el titular puede pasar de 150px; el pie no baja de 15px.
5. Acabado: degradados de texto (background-clip:text, ej. oro), text-shadow de neon, drop-shadow para separar
   del fondo, divisores finos, pastillas con borde, letter-spacing en mayusculas pequenas. Que se sienta caro, no de plantilla.
6. Color: usa los colores de la marca como acentos; contraste alto siempre (texto claro sobre zona oscura o viceversa).
7. Logo (si te lo dan): visible, sin deformar (solo height o width, nunca ambos), con drop-shadow si hace falta.
8. Ritmo: aire generoso entre bloques (minimo 32px entre un bloque y el siguiente; nada pegado a una pastilla o divisor).
   Agrupa lo que va junto (precio con su etiqueta, hora con su CTA) y separa los grupos.

Reglas duras:
- Lienzo EXACTO: body de {w}px x {h}px, overflow:hidden, position:relative. Todo con position:absolute.
  Margen de seguridad de 40px: nada cortado ni pegado al borde.
- El arte es el archivo "{arte}" (fondo de todo el lienzo, background-size:cover o <img> con object-fit:cover).
  El logo es "logo.png" (solo si se indica que hay logo). NO uses ninguna otra imagen ni URL externa,
  excepto la hoja de estilos de Google Fonts (<link href="https://fonts.googleapis.com/css2?...">).
- Textos: copia los del encargo LETRA POR LETRA, con ortografia y tildes perfectas. No quites palabras ("Reserva por
  DM o al 787..." se queda completo) y NO agregues ninguna palabra que no este en el encargo (nada de "desde las",
  "hoy", "no te lo pierdas", eslogans ni etiquetas inventadas). Puedes partir lineas y cambiar mayusculas/minusculas.
- Cada dato aparece UNA sola vez: no repitas el telefono, la marca ni la hora en un segundo pie.
- El contacto de la marca ("datos") va solo si el encargo no trae ya un telefono.
- Sin JavaScript. Sin animaciones.
- Responde SOLO con el HTML completo dentro de un bloque ```html ... ```.

Ejemplo de NIVEL (arte de botella en hielo + hookah, marca negro/oro/rojo; lienzo 1080x1350):
```html
<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@600;800;900&family=Pinyon+Script&family=Montserrat:wght@500;700;800&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{width:1080px;height:1350px;background:#050505;overflow:hidden;position:relative;font-family:Montserrat,sans-serif}
.foto{position:absolute;left:0;top:-110px;width:1080px;height:1350px;background:url(arte.png) center/cover}
.sombra-top{position:absolute;inset:0 0 auto 0;height:470px;background:linear-gradient(#050505 0%,rgba(5,5,5,.85) 45%,rgba(5,5,5,0))}
.sombra-bot{position:absolute;inset:auto 0 0 0;height:420px;background:linear-gradient(rgba(5,5,5,0),rgba(5,5,5,.88) 30%,#050505 55%)}
.oro{background:linear-gradient(180deg,#fff3c4 0%,#f1c95a 28%,#b8860b 55%,#f6d77a 72%,#8a5a12 100%);-webkit-background-clip:text;background-clip:text;color:transparent}
.c{position:absolute;left:0;right:0;text-align:center}
.logo{top:26px;left:50%;transform:translateX(-50%);position:absolute;height:118px;filter:drop-shadow(0 4px 14px rgba(0,0,0,.8))}
.los{top:160px;font:800 26px Cinzel;letter-spacing:14px}
.viernes{top:180px;font:900 168px/1 Cinzel;letter-spacing:4px;filter:drop-shadow(0 6px 0 #3a1200) drop-shadow(0 10px 24px rgba(0,0,0,.9))}
.son{top:300px;font:400 84px/1 'Pinyon Script';color:#fff;text-shadow:0 0 18px rgba(214,24,36,.95),0 0 40px rgba(214,24,36,.6),0 4px 10px #000}
.dj{top:1018px;font:800 42px Cinzel;letter-spacing:6px}
.dj small{display:block;font:700 15px Montserrat;letter-spacing:9px;color:#e8c46a;margin-top:2px}
.precios{position:absolute;top:1100px;left:70px;right:70px;display:flex;align-items:center}
.p{flex:1;text-align:center}
.p b{display:block;font:700 19px Montserrat;letter-spacing:6px;color:#fff}
.p span{display:block;font:900 80px/1 Cinzel;margin-top:4px;filter:drop-shadow(0 4px 10px rgba(0,0,0,.9))}
.p span sup{font-size:.5em;vertical-align:.7em}
.div{width:2px;height:96px;background:linear-gradient(transparent,#c29c0f,transparent)}
.vip{position:absolute;top:1232px;left:50%;transform:translateX(-50%);white-space:nowrap;padding:10px 30px;border:2px solid #c29c0f;border-radius:40px;background:linear-gradient(90deg,#7a0a10,#b3121b,#7a0a10);box-shadow:0 0 24px rgba(179,18,27,.6);color:#fff;font:700 21px Montserrat;letter-spacing:2px}
.vip em{font:900 25px Cinzel;font-style:normal;color:#ffe08a;margin:0 8px}
.pie{top:1306px;font:600 16px Montserrat;letter-spacing:3px;color:#d9c08a}
.pie i{font-style:normal;color:#b3121b;margin:0 10px}
</style></head><body>
<div class="foto"></div><div class="sombra-top"></div><div class="sombra-bot"></div>
<img class="logo" src="logo.png">
<div class="c los oro">LOS</div>
<div class="c viernes oro">VIERNES</div>
<div class="c son">son de la casa</div>
<div class="c dj oro">DJ INVITADO<small>EN CABINA</small></div>
<div class="precios">
 <div class="p"><b>OPEN BAR</b><span class="oro"><sup>$</sup>30</span></div>
 <div class="div"></div>
 <div class="p"><b>OPEN HOOKAH</b><span class="oro"><sup>$</sup>30</span></div>
</div>
<div class="vip">VIP <em>$120</em> BOTELLA + HOOKAH TODA LA NOCHE</div>
<div class="c pie">DESDE LAS 9:00 PM<i>◆</i>AVE. PRINCIPAL 123<i>◆</i>555-0123</div>
</body></html>
```
Ese es el nivel minimo. No copies su estilo: cada arte y cada marca piden su propia tipografia y composicion."""

REVISION = """Eres el mismo director de arte. Arriba esta el RENDER REAL de tu HTML. Revisalo con ojo de cliente exigente:
Te paso el render completo y despues sus dos mitades con zoom: revisa los detalles en las mitades.
- Algun texto cortado, fuera del lienzo, pegado al borde (<40px), encimado con otro, o PEGADO a otro bloque sin aire (<32px)?
- Algun texto tapando la cara, el producto o la parte importante del sujeto?
- Algo ilegible en un celular (muy chico, poco contraste con lo que tiene detras)?
- Compara cada texto visible contra el encargo: falta alguna palabra? sobra alguna palabra que NO esta en el encargo
  (ej. "desde las", "hoy", un pie extra)? algun dato repetido dos veces? Todo eso es error: corrigelo.
- La jerarquia funciona (un protagonista claro)? Se ve profesional y caro, o de plantilla?
- El logo se ve bien y sin deformar? Alguna fuente que no cargo (se ve como letra del sistema)?
Si esta impecable responde SOLO: OK
Si no, responde con el HTML COMPLETO corregido en un bloque ```html ... ``` (mismas reglas de siempre)."""


def _data_url(path, lado=1024):
    img = Image.open(path).convert("RGB")
    img.thumbnail((lado, lado))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def _vistas(png):
    """Render completo + mitad de arriba y de abajo con zoom: a 1200 px un 9:16 esconde los detalles (bloques pegados)."""
    img = Image.open(png).convert("RGB")
    w, h = img.size
    partes = [img, img.crop((0, 0, w, h // 2 + h // 20)), img.crop((0, h // 2 - h // 20, w, h))]
    out = []
    for i, p in enumerate(partes):
        p.thumbnail((1000, 1000) if i == 0 else (1300, 1300))
        buf = io.BytesIO()
        p.save(buf, "JPEG", quality=85)
        out.append({"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()}})
    return out


def _html_de(texto):
    m = re.search(r"```html\s*(.*?)```", texto, re.S) or re.search(r"(<!doctype html.*</html>)", texto, re.S | re.I)
    if not m:
        raise ValueError("el disenador no devolvio HTML")
    return m.group(1).strip()


def _limpio(html):
    """Sin scripts del modelo; se agrega solo la senal de 'listo' que espera render.mjs (fuentes + imagenes cargadas)."""
    # ponytail: limpieza por regex suficiente en local; en la web el render va en sandbox sin red salvo Google Fonts
    html = re.sub(r"<script\b.*?</script\s*>", "", html, flags=re.S | re.I)
    html = re.sub(r"\son\w+\s*=\s*(\"[^\"]*\"|'[^']*')", "", html, flags=re.I)
    listo = ("<script>document.fonts.ready.then(()=>Promise.all([...document.images].map(i=>i.decode().catch(()=>0))))"
             ".then(()=>window.__listo=true)</script>")
    return re.sub(r"</body\s*>", listo + "</body>", html, flags=re.I) if re.search(r"</body\s*>", html, re.I) else html + listo


def _pedir(chat, mensajes, gasto, bitacora=None):
    # qwen piensa ~6800 tokens por llamada (~150 s por diseno, effort low no lo baja). Sin razonamiento tarda 37 s
    # pero disena mucho peor (probado 10/10): se deja pensar.
    extra = {}
    t0 = time.time()
    r = chat({"model": MODEL, "temperature": 0.6, "max_tokens": 12000, "messages": mensajes, "usage": {"include": True}, **extra})
    gasto.append(float((r.get("usage") or {}).get("cost") or 0))
    texto = r["choices"][0]["message"]["content"] or ""
    if bitacora:  # lo que respondio el modelo, para depurar cuando algo sale raro
        with open(bitacora, "a", encoding="utf-8") as f:
            fin = r["choices"][0].get("finish_reason")
            f.write(f"\n===== {MODEL} {round(time.time() - t0)}s fin={fin} uso={r.get('usage')}\n{texto}\n")
    return texto


def _render(carpeta, w, h):
    destino = carpeta / "render.png"
    args = ["node", str(motor.ROOT / "render.mjs"), (carpeta / "index.html").as_uri(), str(destino), "png", str(w), str(h), "2"]
    with motor._sem:
        r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
                           env={**os.environ, "NODE_PATH": motor.NODE_PATH})
    if r.returncode != 0:
        raise RuntimeError("render fallo: " + (r.stderr or r.stdout)[-400:])
    return destino


def _encargo(brief, marca, w, h, arte, hay_logo):
    m = marcas.listar().get(marca) or {}
    datos = {k: m.get(k) for k in ("nombre", "rubro", "tono", "estilo", "datos", "colores", "tipografias", "evitar") if m.get(k)}
    logo = 'si, "logo.png"' if hay_logo else "no hay logo"
    return (f"Lienzo: {w}x{h}px. Arte: \"{arte}\". Logo: {logo}.\n"
            f"Marca: {json.dumps(datos, ensure_ascii=False) if datos else 'sin marca'}\n"
            f"(\"datos\" de la marca es su contacto: telefono/redes; usalo en el pie si cabe.)\n\n"
            f"ENCARGO (los textos que lleva la pieza):\n{brief.strip()}")


def _bucle(chat, carpeta, mensajes, w, h, gasto):
    """Borrador -> render -> el modelo mira su render y corrige (RONDAS veces o hasta que diga OK)."""
    log = carpeta / "respuestas.txt"
    resp = _pedir(chat, mensajes, gasto, log)
    try:
        html = _limpio(_html_de(resp))
    except ValueError:  # a veces se va en explicaciones: se le pide una vez mas, solo el HTML
        resp = _pedir(chat, mensajes + [{"role": "assistant", "content": resp},
                                        {"role": "user", "content": "Responde SOLO con el HTML completo en un bloque ```html```."}], gasto, log)
        html = _limpio(_html_de(resp))
    (carpeta / "index.html").write_text(html, encoding="utf-8")
    png = _render(carpeta, w, h)
    rondas = 0
    for _ in range(RONDAS):
        mensajes = mensajes + [{"role": "assistant", "content": f"```html\n{html}\n```"},
                               {"role": "user", "content": [*_vistas(png), {"type": "text", "text": REVISION}]}]
        resp = _pedir(chat, mensajes, gasto, log)
        if resp.strip().upper().startswith("OK") and "```" not in resp:
            break
        try:
            html = _limpio(_html_de(resp))
        except ValueError:  # la revision vino sin HTML usable: se queda el borrador que ya renderizo bien
            break
        (carpeta / "index.html").write_text(html, encoding="utf-8")
        png = _render(carpeta, w, h)
        rondas += 1
    return png, rondas


def disenar(chat, arte_path: Path, brief, marca=""):
    """Diseno nuevo sobre un arte. Devuelve (stem, meta). El PNG final queda en salidas/<stem>.png."""
    if not brief.strip():
        raise ValueError("Escribe los textos que lleva la pieza")
    t0, gasto = time.time(), []
    stem = f"{time.strftime('%Y%m%d-%H%M%S')}-d{secrets.token_hex(2)}"
    carpeta = DIR / stem
    carpeta.mkdir()
    arte = "arte" + arte_path.suffix.lower()
    shutil.copyfile(arte_path, carpeta / arte)
    logo = marcas.logo_url(marca)
    if logo:
        shutil.copyfile(motor.DATOS / logo, carpeta / "logo.png")
    aw, ah = Image.open(arte_path).size
    w, h = ANCHO, round(ANCHO * ah / aw)
    mensajes = [{"role": "system", "content": SISTEMA.replace("{w}", str(w)).replace("{h}", str(h)).replace("{arte}", arte)},
                {"role": "user", "content": [{"type": "image_url", "image_url": {"url": _data_url(arte_path)}},
                                             {"type": "text", "text": _encargo(brief, marca, w, h, arte, bool(logo))}]}]
    png, rondas = _bucle(chat, carpeta, mensajes, w, h, gasto)
    shutil.copyfile(png, motor.OUT / f"{stem}.png")
    meta = {"desde": arte_path.name, "brief": brief, "marca": marca, "modelo": MODEL, "w": w, "h": h, "arte": arte,
            "revisiones": rondas, "costo": round(sum(gasto), 4), "segundos": round(time.time() - t0)}
    (carpeta / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return stem, meta


def retocar(chat, stem_previo, nota):
    """Nueva version de un diseno con la nota del usuario ("titular mas grande", "quita el precio"...)."""
    previo = DIR / Path(stem_previo).stem
    meta = json.loads((previo / "meta.json").read_text(encoding="utf-8"))
    t0, gasto = time.time(), []
    stem = f"{time.strftime('%Y%m%d-%H%M%S')}-d{secrets.token_hex(2)}"
    carpeta = DIR / stem
    shutil.copytree(previo, carpeta)
    w, h, arte = meta["w"], meta["h"], meta["arte"]
    html = (previo / "index.html").read_text(encoding="utf-8")
    mensajes = [{"role": "system", "content": SISTEMA.replace("{w}", str(w)).replace("{h}", str(h)).replace("{arte}", arte)},
                {"role": "user", "content": [{"type": "image_url", "image_url": {"url": _data_url(carpeta / arte)}},
                                             {"type": "text", "text": _encargo(meta["brief"], meta["marca"], w, h, arte, (carpeta / "logo.png").is_file())}]},
                {"role": "assistant", "content": f"```html\n{html}\n```"},
                {"role": "user", "content": [*_vistas(previo / "render.png"),
                                             {"type": "text", "text": f"Este es el render (completo y en dos mitades). El cliente pide este cambio:\n{nota.strip()}\n\n"
                                                                      "Aplicalo sin romper lo que ya funcionaba. Responde con el HTML COMPLETO en ```html```."}]}]
    png, rondas = _bucle(chat, carpeta, mensajes, w, h, gasto)
    shutil.copyfile(png, motor.OUT / f"{stem}.png")
    meta = {**meta, "previo": previo.name, "nota": nota, "modelo": MODEL, "revisiones": rondas,
            "costo": round(sum(gasto), 4), "segundos": round(time.time() - t0)}
    (carpeta / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return stem, meta
