"""Agente de prompts: qwen3.7-flash escribe prompts para Ming, critica cada resultado y aprende.

Memoria en memoria.json:
  historial: una entrada por imagen (categoria, idea, prompt, critica, rating, nota)
  lecciones: {categoria: [leccion, ...]} que se inyectan en el system prompt
"""
import base64, difflib, io, json, re, threading
from pathlib import Path
from PIL import Image
import marcas, motor, kits, letras

ROOT = Path(__file__).parent
from datos import DATOS
MEM = DATOS / "memoria.json"
MODEL = "qwen/qwen3.7-flash"
RGBA = "RGBA, 4-channel, transparent background. "
# sin "pensar" en voz alta: qwen responde directo (el razonamiento le metia ~1 min)
RAPIDO = {"reasoning": {"enabled": False}}
_lock = threading.Lock()  # el server es multihilo: una escritura de memoria a la vez
MAX_LECCIONES = 25  # ponytail: se quedan las mas nuevas; consolidar con el LLM si 25 se queda corto

CATEGORIAS = {
    # nuestro fuerte: Ming es especialista en carteles de letras
    "tipografia": ("Cartel tipográfico / lettering", "4:5 vertical",
        "La tipografia ES el diseno: la frase es el heroe visual y ocupa 60-80% del lienzo. "
        "Composicion tipografica con jerarquia por tamano, peso y color (palabra clave enorme, conectores pequenos). "
        "Especifica cada palabra con su estilo exacto: familia (serif didona, grotesca condensada, script caligrafica, "
        "slab, display 3D), peso, caja, tracking, interlineado negativo si es impacto. Tratamientos permitidos: "
        "relleno con textura, contorno, sombra dura, extrusion 3D, neon, letras que se superponen o se cortan con el borde. "
        "Fondo sobrio que haga contraste. Pocas palabras: maximo 12."),
    "cartel": ("Cartel publicitario (valla, banner, pendón)", "16:9 horizontal para valla; 9:16 vertical para pendon",
        "Regla de valla: se lee en 5 segundos desde un carro en movimiento. Maximo 7 palabras, un solo mensaje, "
        "tipografia enorme sans-serif bold, producto o visual heroe gigante, logo de marca visible, contraste extremo "
        "(nada de tonos medios juntos). Nada de letra pequena, parrafos ni direcciones largas: como mucho un dato "
        "corto (web, telefono o @usuario). Si es pendon/roll-up: logo arriba, mensaje en el tercio superior, "
        "beneficios en iconos al centro, contacto abajo, nada importante en el 10% inferior."),
    "flyer": ("Flyer promocional", "3:4 vertical",
        "Jerarquia clara en 3 segundos: titular > oferta > visual > datos (fecha, lugar, contacto). "
        "Una sola idea central, badge de oferta con alto contraste, pie con contacto legible. "
        "Maximo 2 familias tipograficas. Colores de marca dominantes, un color de acento para el CTA."),
    "musica": ("Portada de música (álbum/single)", "1:1",
        "Debe funcionar en miniatura de 64px en Spotify: nombre del artista y titulo grandes o iconicos. "
        "Tipografia que respire el genero (reggaeton/urbano: cromada, 3D, agresiva; salsa/tropical: retro, calida; "
        "rock: grunge; pop: limpia y brillante; trap: oscura, minimal, neon). Fotografia o ilustracion conceptual, "
        "no stock generico. Sin logos de plataformas ni etiquetas de parental advisory salvo que las pidan."),
    "pelicula": ("Póster de película", "2:3 vertical",
        "Estructura de poster de cine: tagline arriba, key art con protagonista o simbolo central, "
        "title treatment con personalidad, fecha de estreno y billing block (bloque de creditos condensado, "
        "letra alta y estrecha) abajo. Iluminacion cinematografica, color grading del genero "
        "(terror: frio y desaturado; accion: teal/orange; drama: tonos naturales; comedia: brillante)."),
    "web": ("Página web / landing (UI)", "16:10 desktop",
        "Mockup de landing page real, no ilustracion: navbar con logo y 4-5 links, hero con headline, "
        "subheadline y boton CTA, visual del producto, luego secciones (beneficios en 3 tarjetas, testimonios, precios). "
        "Grid de 12 columnas, espaciado generoso, UI moderna tipo Framer/Webflow. Enumera cada texto de boton y link."),
    "evento": ("Póster de evento / concierto", "4:5 vertical",
        "Nombre del evento o artista principal dominante, line-up en jerarquia (headliner grande, "
        "resto menor), fecha, hora, lugar y boleteria claramente separados. Energia visual acorde al evento."),
    "historia": ("Historia Instagram/TikTok", "9:16 vertical",
        "Zonas seguras: nada importante en el 14% superior ni el 20% inferior (ahi va la UI de la app). "
        "Mensaje principal en el tercio central, texto corto y enorme, un CTA tipo sticker "
        "(\"Desliza\", \"Link en bio\"). Pensado para leerse en 2 segundos mientras se pasa."),
    "post": ("Post para redes (feed)", "4:5 vertical",
        "Scroll-stopper: un gancho visual fuerte, maximo 8-10 palabras de texto en la imagen, "
        "marca discreta en una esquina. Contraste alto para feed movil."),
    "producto": ("Foto / anuncio de producto", "1:1",
        "Producto heroe centrado con iluminacion de estudio (key light suave, rim light, sombra de contacto), "
        "superficie y props que cuenten el estilo de vida de la marca, reflejos y materiales realistas. "
        "Texto minimo: nombre del producto y claim corto."),
    "logo": ("Logo / identidad", "1:1",
        "Hoja de logo: simbolo + logotipo, version horizontal y apilada, version monocromatica, "
        "paleta con codigos hex. Formas simples, escalables, sin degradados excesivos. Fondo limpio."),
    "infografia": ("Infografía", "3:4 vertical",
        "Titulo claro, datos organizados en bloques numerados o flujo, iconos consistentes, "
        "cada cifra y etiqueta enumerada exactamente. Una paleta de 3-4 colores con significado."),
}

PERSONA = """Eres "Director", el mejor director de arte y prompt engineer de LATAM. Tienes 20 anos \
dirigiendo portadas de discos para artistas latinos, posters de cine, identidad de marca, campanas \
para redes y diseno web. Tambien eres narrador visual: cada pieza cuenta una historia en un vistazo \
(quien, que siente, que promete). Tu trabajo: convertir la idea del cliente en el prompt perfecto \
para el modelo de imagen Ming-Image-0.1-Design, especialista en diseno con texto legible.

Reglas de oro:
- Todo texto visible va en el idioma del cliente (espanol neutro LATAM), con acentos y signos exactos. \
Las descripciones del diseno van en ingles (el modelo las entiende mejor).
- Si el cliente da textos exactos, respetalos caracter por caracter. Si no, escribe copy corto, \
profesional y vendedor en espanol; nada de lorem ipsum.
- Pocas palabras en la imagen: el texto largo es donde los modelos fallan.
- Especifica tipografia (familia, peso, caja, tracking), paleta con hex, iluminacion, camara y materiales.
- Nada de relleno literario: solo decisiones visuales concretas.
"""

# estilos base de la guia oficial de inclusionAI (ling-ui-design / visual-direction)
ESTILOS = {
    "limpio": "Clean: light canvas, generous whitespace, cool gray surfaces, one quiet blue or neutral accent, geometric sans, hairline dividers, soft rounded shapes.",
    "calido": "Warm: cream or stone surfaces, serif or humanist headlines with sans body, softer contrast, restrained terracotta or olive accent.",
    "oscuro": "Dark: near-black canvas, high-contrast type, one luminous accent color, tighter spacing, restrained hairline or glass details.",
    "bold": "Bold: oversized type, saturated accent blocks, few gray tones, strong graphic shapes and large image crops.",
}
# formatos que Ming respeta (verificado: 3:4 -> 1824x2432, 9:16 -> 1440x2560, 16:10 -> 2592x1632)
FORMATOS = {"1:1", "4:5", "3:4", "2:3", "9:16", "16:9", "16:10"}

SALIDA = """Devuelve SOLO un objeto JSON con dos claves:
{"plan": "2-3 frases en espanol explicando tu concepto y decisiones clave (para el cliente)",
 "caption": { ...el objeto con canvas_settings y layers segun las reglas de Ming... }}"""


def cargar():
    if MEM.exists():
        return json.loads(MEM.read_text(encoding="utf-8"))
    return {"historial": [], "lecciones": {}}


def guardar(m):
    tmp = MEM.with_suffix(".tmp")
    tmp.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(MEM)  # escritura atomica: si se corta la luz no se pierde la memoria


def _mutar(fn):
    """Carga, modifica y guarda la memoria sin que otro hilo la pise."""
    with _lock:
        m = cargar()
        r = fn(m)
        guardar(m)
        return r


def _leccion(m, cat, texto):
    texto = (texto or "").strip()
    lst = m["lecciones"].setdefault(cat, [])
    if texto and texto not in lst:
        lst.append(texto)
        del lst[:-MAX_LECCIONES]


def system_prompt(cat, m, salida=None):
    nombre, aspecto, guia = CATEGORIAS[cat]
    partes = [PERSONA, f"## Encargo: {nombre}\nFormato recomendado: {aspecto}.\n{guia}",
              "## Reglas del formato de Ming (oficiales)\n" + (ROOT / "ming_rewriter.txt").read_text(encoding="utf-8")]
    # el modo hibrido tiene su propia libreta: las lecciones viejas hablan de pedirle (o prohibirle) texto a Ming,
    # y en v2 el texto lo pone el motor; mezclarlas confunde al Director
    v2 = ":v2" if salida else ""
    lecciones = m["lecciones"].get(cat + v2, []) + m["lecciones"].get("general" + v2, [])
    if lecciones:
        partes.append("## Lecciones aprendidas de trabajos anteriores (APLICALAS)\n" + "\n".join(f"- {l}" for l in lecciones))
    buenos = [h for h in reversed(m["historial"]) if h["categoria"] == cat
              and (h.get("rating") == 1 or (h.get("critica") or {}).get("puntaje", 0) >= 8)][:2]
    if salida is None:  # los ejemplos viejos son de una sola imagen: en v2 confundirian al Director
        for h in buenos:
            partes.append(f"## Ejemplo que funciono bien (idea: {h['idea']})\n{h['prompt']}")
    partes.append(salida or SALIDA)
    return "\n\n".join(partes)


def _json_de(resp):
    txt = resp["choices"][0]["message"]["content"].strip()
    if txt.startswith("```"):
        txt = txt.split("\n", 1)[1].rsplit("```", 1)[0]
    return json.loads(txt)


HIBRIDO = """MODO MOTOR HIBRIDO (texto garantizado). El diseno se arma en dos capas:
1) Ming pinta el ARTE a partir de `caption`.
2) Nuestro motor escribe ENCIMA, con tipografia real, cada bloque de `textos`. Ese texto sale perfecto siempre.

Reglas:
- {titular}
- Todo lo demas que se lee va en `textos`: subtitulos, precios, listas, datos, fechas, contacto, CTA. Nunca en `caption`.
- En `caption` NO aparece ninguno de esos textos. Cada zona de `textos` debe existir en `layers` como un area limpia y tranquila para texto superpuesto (panel, franja, tarjeta vacia, pastilla vacia o espacio negativo de tono uniforme), con las MISMAS coordenadas, y su description debe decir "empty, no text, no letters, no numbers".
- Nunca pidas a Ming logos, marcas de agua, iconos con letras, telefonos, precios, correos ni URLs.
- Las zonas: dentro del lienzo, margen minimo 0.04 a los bordes, sin encimarse entre si. Alto segun la cantidad de texto: una linea de cuerpo ~0.03-0.045; un precio heroe ~0.08-0.14; una lista de N puntos ~N*0.05.
- Color de cada texto pensado contra el tono de su zona (el motor igual corrige si el contraste no alcanza).

Salida: agrega al JSON estas dos claves:
"fuentes": {{"titulo": "<familia>", "cuerpo": "<familia>"}}  elige de: {fuentes} (o las de la marca si las dio)
"textos": [{{"rol": "subtitulo|precio|lista|texto|contacto|cta|titulo|logo", "texto": "texto exacto; en lista un punto por linea separados por \\n", "zona": "cx: 0.500, cy: 0.500, w: 0.800, h: 0.100", "alinear": "left|center|right", "color": "#hex", "fuente": "titulo|cuerpo", "peso": 400, "mayusculas": false, "fondo": "#hex si va sobre pastilla/boton, si no vacio", "vinieta": "• o ✓ (solo lista)"}}]"""
TITULAR_MING = "El TITULAR principal (la frase mas grande y artistica) SI lo pinta Ming dentro de `caption`, con su tipografia artistica y el texto exacto entre comillas. No lo repitas en `textos`."
TITULAR_MOTOR = "Incluso el titular va en `textos` (rol titulo): en el arte no debe haber ninguna letra."


def _reservar_zonas(cap, textos):
    """Garantiza que Ming deje vacia cada zona de texto: si el Director no la puso en `layers`, la agregamos."""
    capas = cap.setdefault("layers", [])
    tomadas = []
    for c in capas:
        try:
            tomadas.append(motor.parse_zona(c.get("coordinates", "")))
        except ValueError:
            pass
    for t in textos:
        z = t["zona"]
        if any(all(abs(z[k] - o[k]) < 0.04 for k in z) for o in tomadas):
            continue
        capas.append({
            "description": "Clean empty area reserved for overlay typography: smooth, calm surface continuing the surrounding tones, empty, no text, no letters, no numbers, no logos.",
            "coordinates": f"cx: {z['cx']:.3f}, cy: {z['cy']:.3f}, w: {z['w']:.3f}, h: {z['h']:.3f}",
            "hierarchy_and_relation": "Reserved negative space above the background; no element overlaps it.",
            "color_specs": [],
        })


def _director(chat, cat, user_msg, rgba, formato, hibrido=False, titular_ming=True):
    if cat not in CATEGORIAS:
        raise ValueError("categoria invalida")
    sistema = system_prompt(cat, cargar())
    if hibrido:
        sistema += "\n\n" + HIBRIDO.format(titular=TITULAR_MING if titular_ming else TITULAR_MOTOR,
                                           fuentes=", ".join(motor.FUENTES))
    out = _json_de(chat({
        "model": MODEL, "temperature": 0.7, "max_tokens": 5000, **RAPIDO,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "system", "content": sistema},
                     {"role": "user", "content": user_msg}],
    }))
    cap = out["caption"]
    extra = {}
    if hibrido:
        textos, fuentes = motor.normalizar(out.get("textos"), out.get("fuentes"))
        if textos:
            if titular_ming:
                # el Director a veces igual manda el titular al motor: se lo devolvemos a Ming
                for t in textos:
                    if t["rol"] == "titulo":
                        t["pinta"] = "ming"
            del_motor = [t for t in textos if t.get("pinta") != "ming"]
            cap = motor.limpiar_caption(cap, del_motor)
            motor.planificar(cap, textos)
            _reservar_zonas(cap, del_motor)
            for t in textos:
                if t.get("pinta") == "ming":
                    z = t["zona"]
                    cap["layers"].append({
                        "description": f"Headline typography reading exactly \"{t['texto'].replace(chr(10), ' ')}\": bold, artistic, "
                                       "high-impact lettering that matches the design style, perfectly legible, spelled exactly.",
                        "coordinates": f"cx: {z['cx']:.3f}, cy: {z['cy']:.3f}, w: {z['w']:.3f}, h: {z['h']:.3f}",
                        "hierarchy_and_relation": "Topmost headline, nothing overlaps it.",
                        "color_specs": [t["color"]],
                    })
            extra = {"textos": textos, "fuentes": fuentes}
    if formato in FORMATOS:  # el formato elegido manda sobre lo que decida el Director
        cap.setdefault("canvas_settings", {})["aspect_ratio"] = formato
    return (RGBA if rgba else "") + json.dumps(cap, ensure_ascii=False), out.get("plan", ""), extra


SOLO_ARTE = """SOLO ARTE: el cliente quiere el arte grafico LIMPIO, sin una sola letra. El texto lo disena despues aparte.
- Ninguna capa de texto, titular, precio, logo, letrero ni numero. Si la idea trae textos entre comillas, NO los pintes:
  usalos solo para entender el tema y el ambiente.
- Deja aire limpio (zonas oscuras o lisas, sin detalle) donde despues iria el texto: arriba y abajo en verticales.
- El sujeto protagonista bien iluminado y completo, sin cortes."""


def crear_prompt(chat, cat, idea, rgba, formato="auto", estilo="auto", marca=None, hibrido=False, titular_ming=True, solo_arte=False):
    """chat(body) -> respuesta de /chat/completions. Devuelve (prompt_para_ming, plan)."""
    if solo_arte:  # interruptor "Diseno con texto" apagado: arte limpio, el texto se disena aparte
        prompt, plan, _ = crear_prompt(chat, cat, f"{idea}\n\n{SOLO_ARTE}", rgba, formato, estilo, marca)
        pre = RGBA if prompt.startswith(RGBA) else ""
        try:
            prompt = pre + json.dumps(_sin_texto(json.loads(prompt[len(pre):])), ensure_ascii=False)
        except ValueError:
            pass
        return prompt, plan, None
    msg = f"Idea del cliente:\n{idea}"
    if estilo in ESTILOS:
        msg += f"\n\nDireccion visual obligatoria: {ESTILOS[estilo]}"
    if marca and (kit := marcas.bloque_director(marca)):
        msg += "\n\n" + kit
    if formato in FORMATOS:
        msg += f"\n\nFormato obligatorio: {formato}"
    return _director(chat, cat, msg, rgba, formato, hibrido and not rgba, titular_ming)


def corregir(chat, file):
    """Reintento profesional (guia oficial): reescribir nombrando cada defecto observado."""
    h = _entrada(cargar(), file)
    cat = h["categoria"] if h["categoria"] in CATEGORIAS else "flyer"
    problemas = (h.get("critica") or {}).get("problemas") or []
    if not problemas and not h.get("nota"):
        raise ValueError("Aun no hay critica ni comentario para corregir")
    rgba = h["prompt"].startswith(RGBA)
    msg = (f"Idea del cliente:\n{h['idea']}\n\nEste prompt ya se genero y salio con defectos:\n{h['prompt'].removeprefix(RGBA)}\n\n"
           "Defectos observados en la imagen:\n" + "\n".join(f"- {p}" for p in problemas) +
           (f"\n\nComentario del cliente: {h['nota']}" if h.get("nota") else "") +
           "\n\nReescribe el prompt corrigiendo CADA defecto de forma explicita (nombra lo que se debe ver y lo que no). "
           "Conserva el formato, los textos exactos y todo lo que si funciono. En el plan di que corregiste.")
    if h.get("marca") and (kit := marcas.bloque_director(h["marca"])):
        msg += "\n\n" + kit
    if (motor.COMP / f"{Path(file).stem}.json").is_file():
        # diseno hibrido: los textos ya son exactos, solo se rehace el arte respetando sus zonas
        comp = motor.cargar(Path(file).stem)
        zonas = [f"{t['rol']}: cx {t['zona']['cx']}, cy {t['zona']['cy']}, w {t['zona']['w']}, h {t['zona']['h']}" for t in comp["textos"]]
        msg += ("\n\nEs un diseno del motor hibrido: NO muevas ni ocupes estas zonas reservadas (deben seguir vacias, "
                "sin texto): " + "; ".join(zonas))
    return _director(chat, cat, msg, rgba, None)


def capas_prompt(chat, data_url, n):
    """El Director mira el diseno y escribe la especificacion de capas en el formato oficial de Ming."""
    n = max(2, min(int(n), 10))
    out = _json_de(chat({
        "model": MODEL, "temperature": 0.2, "max_tokens": 1500, **RAPIDO,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": (
                f"You write layer-decomposition prompts for Ming-Image-0.1-Design-Layer. Look at the design and split it into exactly {n} layers, "
                "front (Layer 1) to back (last layer = background only). Group by role: overlay text, photographs/illustrations, "
                "containers (badges, ribbons, banners, frames), background. Quote every visible text string exactly. "
                'Answer ONLY JSON: {"layers": ["Layer 1 description", "..."]}. Each description is one concrete sentence in English. '
                "Examples: 'Central text stack reading WORLD, Card Making, DAY in mixed gold and red fonts.' / 'Solid bright red background.'")},
            {"role": "user", "content": [{"type": "image_url", "image_url": {"url": data_url}}]},
        ],
    }))
    capas = out["layers"][:n]
    lineas = [f"Decompose this image into {len(capas)} layers with the following specifications:", "",
              f"Number of layers: {len(capas)}",
              "Preserve the source composition and geometry exactly. Keep photographs and illustrations high-detail with clean boundaries."]
    lineas += [f"Layer {i}: {c}" for i, c in enumerate(capas, 1)]
    return "\n".join(lineas)


def registrar(file, cat, idea, prompt, marca=None):
    _mutar(lambda m: m["historial"].append({"file": file, "categoria": cat or "libre", "idea": idea or "", "prompt": prompt, "marca": marca or ""}))


def _entrada(m, file):
    for h in m["historial"]:
        if h["file"] == file:
            return h
    raise KeyError("imagen sin historial")


CRITICA_V2 = """Eres un director de arte exigente revisando un diseno TERMINADO para un cliente real.
Como se hizo: un modelo de imagen pinto SOLO el arte (fondo de ambiente + sujeto recortado aparte). Luego nuestro motor
puso TODOS los textos con tipografia real encima. Que haya texto es lo correcto: NO castigues el texto por existir.
Revisa como lo haria un disenador senior:
- Ortografia: cada texto visible contra la lista de textos esperados, letra por letra con tildes.
- Legibilidad y jerarquia: se lee en un celular? el titular manda? algo tapado o encimado?
- Sujeto: recorte limpio (sin halos de color, sin partes transparentes, sin cortes feos), se ve apetitoso/profesional.
- Composicion: margenes, equilibrio, espacio muerto, vidrios o cajas que ensucian, coherencia con la marca y el formato.
Las mediciones automaticas del motor son hechos: usalas.
Responde SOLO JSON: {"puntaje": 1-10, "problemas": ["..."], "leccion": "una regla GENERAL y accionable, en espanol, sobre
DECISIONES DE DIRECCION DE ARTE para este tipo de pieza (copy, jerarquia, donde ubicar sujeto y textos, que kit o letra
elegir, como describir el sujeto). Nunca sobre pedir o prohibir texto al modelo de imagen. Vacio si no hay nada nuevo."}"""


def criticar(chat, img_path, file):
    """El agente mira la imagen generada, la puntua y saca una leccion."""
    h = _entrada(cargar(), file)
    stem = Path(file).stem
    if (motor.COMP / f"{stem}.json").is_file():
        return _criticar_v2(chat, img_path, file, h, motor.cargar(stem))
    # 1024px JPG en vez del PNG de 4MB: sube y se analiza mucho mas rapido
    img = Image.open(img_path).convert("RGB")
    img.thumbnail((1024, 1024))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    b64 = base64.b64encode(buf.getvalue()).decode()
    out = _json_de(chat({
        "model": MODEL, "temperature": 0.2, "max_tokens": 1000, **RAPIDO,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": (
                "Eres un director de arte exigente revisando lo que genero el modelo de imagen. "
                "Compara la imagen con el prompt: textos exactos y legibles (letra por letra, acentos), "
                "jerarquia, composicion, calidad profesional. Responde SOLO JSON: "
                '{"puntaje": 1-10, "problemas": ["..."], "leccion": "una regla GENERAL y accionable, en espanol, '
                'para escribir mejores prompts de este tipo de pieza la proxima vez (no sobre esta imagen puntual). '
                'Vacio si no hay nada nuevo que aprender."}')},
            {"role": "user", "content": [
                {"type": "text", "text": f"Tipo de pieza: {h['categoria']}\nIdea: {h['idea']}\nPrompt usado:\n{h['prompt']}"},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            ]},
        ],
    }))
    critica = {"puntaje": int(out.get("puntaje", 0)), "problemas": out.get("problemas", [])}

    def aplicar(m):
        _entrada(m, file)["critica"] = critica
        _leccion(m, h["categoria"], out.get("leccion"))
    _mutar(aplicar)
    return critica


def _criticar_v2(chat, img_path, file, h, comp):
    img = Image.open(img_path).convert("RGB")
    img.thumbnail((1024, 1024))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    esperados = "\n".join(f'- {t["rol"]}: "{t["texto"].replace("*", "")}"' for t in comp["textos"] if t["texto"])
    medido = [f'{p["tipo"]} ({p.get("rol")}{" con " + p["con"] if p.get("con") else ""})'
              for p in (motor.ULTIMO_JUEZ.get(Path(file).stem) or {}).get("problemas", [])]
    out = _json_de(chat({
        "model": MODEL, "temperature": 0.2, "max_tokens": 1000, **RAPIDO,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": CRITICA_V2},
            {"role": "user", "content": [
                {"type": "text", "text": f"Tipo de pieza: {h['categoria']}\nIdea del cliente: {h['idea']}\n"
                                         f"Textos esperados (exactos):\n{esperados}\n"
                                         f"Mediciones del motor: {'; '.join(medido) or 'sin problemas medidos'}"},
                {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()}},
            ]},
        ],
    }))
    critica = {"puntaje": int(out.get("puntaje", 0) or 0), "problemas": out.get("problemas", [])}

    def aplicar(m):
        _entrada(m, file)["critica"] = critica
        _leccion(m, h["categoria"] + ":v2", out.get("leccion"))
    _mutar(aplicar)
    return critica


def calificar(chat, file, rating, nota):
    """Feedback del usuario: +1/-1 y nota opcional que se convierte en leccion."""
    h = _entrada(cargar(), file)
    leccion = ""
    if nota:
        out = _json_de(chat({
            "model": MODEL, "temperature": 0.2, "max_tokens": 300, **RAPIDO,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "user", "content": (
                f"El cliente {'aprobo' if rating == 1 else 'rechazo'} este diseno ({h['categoria']}) y comento: "
                f"\"{nota}\"\nPrompt usado:\n{h['prompt']}\n\n"
                'Convierte su comentario en una regla general y accionable para futuros prompts de este tipo. '
                'Responde SOLO JSON: {"leccion": "..."}')}],
        }))
        leccion = out.get("leccion")

    def aplicar(m):
        e = _entrada(m, file)
        e["rating"], e["nota"] = rating, nota
        _leccion(m, e["categoria"] + (":v2" if (motor.COMP / f"{Path(file).stem}.json").is_file() else ""), leccion)
    _mutar(aplicar)


def estado(file):
    m = cargar()
    for h in m["historial"]:
        if h["file"] == file:
            return {"puntaje": (h.get("critica") or {}).get("puntaje"), "rating": h.get("rating"),
                    "prompt": h["prompt"], "categoria": h["categoria"], "idea": h["idea"], "marca": h.get("marca", ""),
                    "hibrido": (motor.COMP / f"{Path(file).stem}.json").is_file()}
    return {}


# ---------------------------------------------------------------------------
# Motor hibrido v2: Ming pinta SOLO arte (fondo + sujeto aislado), el motor pone TODO el texto
# ---------------------------------------------------------------------------
SIN_TEXTO = (" Absolutely no text anywhere: no letters, no numbers, no words, no signage, no labels, no logos, "
             "no captions, no watermarks; any screen or phone shows abstract UI shapes only.")

ARTE_V2 = """MODO MOTOR HIBRIDO: Ming pinta SOLO ARTE, sin una sola letra. Nuestro motor pone TODO el texto con tipografia real.
Entregas estas piezas en JSON:

"fondo": caption en el formato de Ming (canvas_settings + layers) del FONDO: SOLO AMBIENTE. Luz, color, degradados,
  texturas, bokeh, particulas, formas abstractas suaves, entorno desenfocado. PROHIBIDO poner objetos protagonistas,
  aparatos, productos, personas o props: el protagonista es el sujeto y se pinta aparte. Un pedestal, piso o halo de luz
  solo si va justo debajo de sujeto_zona. Deja areas amplias y tranquilas donde ira el texto, sin paneles, cajas, marcos
  ni rectangulos. NUNCA nombres al sujeto en el fondo (nada de "donde esta el robot"): si lo nombras, Ming lo pinta.
  aspect_ratio = el formato del diseno.
"sujeto": caption del SUJETO PRINCIPAL aislado (persona, producto, personaje u objeto heroe), completo y centrado,
  sobre fondo CROMA plano para recortarlo: magenta puro #FF00FF (o verde puro #00FF00 si el sujeto es rosado/morado),
  sin piso, sin sombra proyectada, sin escenario, sin reflejos del fondo en el sujeto.
  aspect_ratio segun la forma del sujeto (1:1, 3:4 o 4:3). Si la idea menciona un plato, producto, persona o lugar, el
  sujeto es OBLIGATORIO (un menu o una oferta de comida sin comida no vende). Solo null si el diseno es puramente
  tipografico, un patron o un paisaje.
"sujeto_zona": "cx: 0.500, cy: 0.500, w: 0.600, h: 0.450" donde va el sujeto en el lienzo final.
"titular_detras": true solo si el titular es enorme y conviene el efecto portada de revista (el sujeto tapa parte de
  las letras). En ese caso la zona del titulo puede cruzarse con sujeto_zona; ningun otro texto puede.
"kit": el sistema tipografico que mejor viste la idea y la marca. Elige UNO de:
{kits}
"letra": el estilo de letra del TITULAR (fuente de cartel + tratamiento de rotulista: oro, cromo, neon, sticker, 3D...).
  Es lo que hace que el diseno se vea de disenador y no generico: elige el que mejor case con el rubro, la vibra y el
  fondo, y varia entre disenos (no uses siempre el mismo). Muchos ponen la palabra clave en otra fuente (por ejemplo
  caligrafica), asi que marca SIEMPRE una palabra clave en el titular. Elige UNO de:
{letras}
"lettering": en INGLES, 1-2 frases que describan como se veria el titular si lo rotulara a mano un letrista para ESTA
  idea: materiales, estilo de letra, colores (hex de la marca), efecto (por ejemplo "glossy 3D gold script with a ruby
  drop shadow" o "chunky retro sticker letters, cream fill, thick teal outline"). Sin fondos ni escenas: solo la letra.
"textos": TODOS los textos del diseno, incluido el titular (rol titulo):
  [{{"rol": "titulo|subtitulo|precio|lista|texto|contacto|cta|sticker|logo", "texto": "texto exacto; en lista un punto por linea separados por \\n, sin vinietas",
    "zona": "cx: 0.500, cy: 0.500, w: 0.800, h: 0.100", "alinear": "left|center|right", "color": "#hex", "fuente": "titulo|cuerpo",
    "peso": 400, "mayusculas": false, "fondo": "#hex si va sobre pastilla/boton, si no vacio", "vinieta": "• o ✓ (solo lista)"}}]

Copy de publicista (cuando el cliente no dio el texto exacto):
- Titular = gancho de maximo 6 palabras que venda el beneficio, no la descripcion ("Tu negocio vende mientras duermes",
  no "Asistente 3D amigable"). Marca UNA palabra clave del titular entre asteriscos: "Vende *mientras duermes*".
- Subtitulo: una frase corta que aterriza la promesa. CTA: verbo + beneficio ("Pide tu demo", "Reserva hoy").
- Precio: tal cual ("Desde $350", "$60/mes"); el motor lo convierte en precio heroe.
- La OFERTA es el gancho: si el mensaje principal es una promo ("2x1 los martes", "-30%"), va COMPLETA en el titulo.
  Nunca partas el gancho entre titulo y sticker.
- sticker (opcional, maximo 1): 1-3 palabras de urgencia o novedad EXTRA ("NUEVO", "SOLO HOY"), zona casi cuadrada, en una esquina.
- Lo que el cliente puso entre comillas se respeta letra por letra (puedes marcar su palabra clave con asteriscos).

Descripcion visual del sujeto: el modelo de imagen NO conoce nombres regionales. Describe como se VE, no como se llama:
  "mofongo" -> "golden-brown dome of mashed fried green plantain, rustic texture, garlic and pork crackling bits, in a wooden
  pilon"; "pastelillos" -> "golden crescent-shaped fried turnovers with crimped edges". Lo mismo con productos y lugares locales.

Reglas:
- En "fondo" y "sujeto" esta PROHIBIDO cualquier texto: letras, numeros, palabras, letreros, etiquetas, logos, pantallas con texto.
- Zonas de texto: dentro del lienzo, margen minimo 0.04 a los bordes, sin encimarse entre si ni con sujeto_zona.
  Alto segun la cantidad de texto: una linea de cuerpo ~0.03-0.045; un titular ~0.08-0.16; un precio heroe ~0.08-0.14;
  una lista de N puntos ~N*0.05.
- Color de cada texto pensado contra el tono del fondo en su zona (el motor corrige si el contraste no alcanza).

Devuelve SOLO un objeto JSON con: "plan" (2-3 frases en espanol para el cliente), "fondo", "sujeto", "sujeto_zona",
"titular_detras", "kit", "letra", "lettering", "textos"."""


def _sin_texto(caption):
    cs = caption.setdefault("canvas_settings", {})
    cs["image_style"] = str(cs.get("image_style", "")).rstrip(". ") + "." + SIN_TEXTO
    return caption


def _caption_de(x):
    """Acepta el caption como objeto o como texto JSON; None si no sirve."""
    if isinstance(x, str):
        try:
            x = json.loads(x)
        except ValueError:
            return None
    return x if isinstance(x, dict) and x.get("layers") else None


MEZCLA = """
BIBLIOTECA: el mensaje trae piezas que el cliente ya aprobo para esta marca. Decide con criterio de director de arte:
- sujeto: si la idea pide EXACTAMENTE un plato/producto/personaje que ya esta en la biblioteca, reusalo: es el real del
  cliente y debe verse igual siempre. Si solo se parece (otro plato, otra persona), null y se pinta nuevo.
- fondo: reusa uno solo si su ambiente (nombre y etiquetas) encaja con lo pedido. Si ninguno encaja, null.
- objetos: maximo 2 y solo si suman a la idea (limones junto al plato, maracas en una noche de salsa); nunca para
  rellenar. Lo normal es []. Zona pequena en un borde o junto al sujeto, sin tapar textos.
- Si el cliente pide algo "nuevo" (plato nuevo, fondo nuevo), no reuses ese tipo.
- Aunque reuses, escribe igual "fondo" y "sujeto" completos: son el respaldo.
Agrega al JSON: "biblioteca": {"sujeto": "id o null", "fondo": "id o null", "objetos": [{"id": "id", "zona": "cx: 0.850, cy: 0.800, w: 0.150, h: 0.150"}],
"motivo": "1 frase en espanol para el cliente: que reusaste, que se pinta nuevo y por que"}"""
_NUEVO = {"sujeto": re.compile(r"\b(plato|sujeto|personaje|producto)s?\s+nuev", re.I), "fondo": re.compile(r"\bfondos?\s+nuev", re.I)}


def _eleccion(pedido, biblio, idea):
    """Lo que el Director quiso reusar, filtrado: solo ids reales del catalogo y del tipo correcto."""
    if not biblio or not isinstance(pedido, dict):
        return None
    ps = biblio["piezas"]
    ok = lambda pid, tipo: pid if isinstance(pid, str) and ps.get(pid, {}).get("tipo") == tipo and not (tipo in _NUEVO and _NUEVO[tipo].search(idea)) else None
    objetos = []
    for o in pedido.get("objetos") or []:
        if isinstance(o, dict) and ok(o.get("id"), "objeto") and len(objetos) < 2:
            try:
                objetos.append({"id": o["id"], "zona": motor.parse_zona(o.get("zona") or "")})
            except ValueError:
                pass
    e = {"sujeto": ok(pedido.get("sujeto"), "sujeto"), "fondo": ok(pedido.get("fondo"), "fondo"), "objetos": objetos}
    if not (e["sujeto"] or e["fondo"] or objetos):
        return None
    usados = [ps[e[k]]["nombre"] or k for k in ("sujeto", "fondo") if e[k]] + [ps[o["id"]]["nombre"] or "objeto" for o in objetos]
    e["motivo"] = "♻ De tu biblioteca: " + ", ".join(f'"{n}"' for n in usados) + ". " + str(pedido.get("motivo") or "").strip()
    return e


def _plano(t):
    return re.sub(r"\s+", " ", t.replace("*", "")).strip().casefold()


def respetar_comillas(textos, idea):
    """Lo que el cliente puso entre comillas sale letra por letra. El Director a veces lo "corrige"
    ("Fuego Boricua" -> "FUEGO BORIQUA"): si un texto se le parece mucho pero no es igual, se restituye."""
    for q in (a or b for a, b in re.findall(r'"([^"]{2,80})"|“([^”]{2,80})”', idea or "")):
        if any(_plano(q) in _plano(t["texto"]) for t in textos):
            continue
        parecido = max(textos, key=lambda t: difflib.SequenceMatcher(None, _plano(q), _plano(t["texto"])).ratio(), default=None)
        if parecido and difflib.SequenceMatcher(None, _plano(q), _plano(parecido["texto"])).ratio() >= 0.75:
            mayus = parecido["texto"].replace("*", "").isupper()
            parecido["texto"] = q.upper() if mayus else q
            if parecido["rol"] == "titulo":
                parecido["texto"] = motor.marcar_clave(parecido["texto"])
    return textos


def ortografia(chat, textos, idea):
    """El Director a veces escribe sin tildes ("Nomina", "Naci"). Un corrector de ortografia con candado: solo se acepta
    si quedan las mismas palabras (mismo largo, casi iguales) y nunca toca lo que el cliente puso entre comillas."""
    citas = [_plano(a or b) for a, b in re.findall(r'"([^"]{2,80})"|“([^”]{2,80})”', idea or "")]
    idx = [i for i, t in enumerate(textos) if t["texto"] and t["rol"] != "logo" and not any(c in _plano(t["texto"]) for c in citas)]
    if not idx:
        return textos
    try:
        out = _json_de(chat({"model": MODEL, "temperature": 0, "max_tokens": 1500, **RAPIDO, "response_format": {"type": "json_object"},
                             "messages": [{"role": "system", "content": (
                                 "Eres corrector de estilo de espanol neutro. Corrige SOLO ortografia: tildes, letras mal escritas, "
                                 "signos de apertura (¡ ¿). No cambies palabras, ni el orden, ni mayusculas, ni los asteriscos, ni los "
                                 'saltos de linea. Responde SOLO JSON: {"textos": ["...", ...]} en el mismo orden.')},
                                 {"role": "user", "content": json.dumps([textos[i]["texto"] for i in idx], ensure_ascii=False)}]}))
        nuevos = out.get("textos") or []
    except Exception:  # el corrector es un extra: si falla, el diseno sigue
        return textos
    for i, nuevo in zip(idx, nuevos):
        viejo = textos[i]["texto"]
        if (isinstance(nuevo, str) and nuevo != viejo and len(nuevo.split()) == len(viejo.split())
                and nuevo.count("*") == viejo.count("*") and difflib.SequenceMatcher(None, viejo, nuevo).ratio() >= 0.85):
            textos[i]["texto"] = nuevo
    return textos


def nombre_de_marca(textos, marca):
    """El texto con rol logo es el nombre de la marca: se escribe como en el kit (no "NANBOY"). Si la marca no tiene
    logo cargado, el motor no dibujaria nada: pasa a ser texto para que el nombre no se pierda."""
    m = marcas.listar().get(marca) if marca else None
    if m:  # "NANBOY EN VIVO": el nombre mal escrito en cualquier texto se corrige (respetando mayusculas)
        nombre = m["nombre"]
        for t in textos:
            def fijar(w):
                p = w.group(0)
                if p.casefold() != nombre.casefold() and difflib.SequenceMatcher(None, p.casefold(), nombre.casefold()).ratio() >= 0.9:
                    return nombre.upper() if p.isupper() else nombre
                return p
            if " " not in nombre and len(nombre) >= 5:
                t["texto"] = re.sub(r"\w+", fijar, t["texto"])
    for t in textos:
        if t["rol"] == "logo":
            if m:
                t["texto"] = m["nombre"]
            if not marcas.logo_url(marca) and t["texto"]:
                t["rol"] = "texto"
    return textos


def director_v2(chat, cat, idea, formato="auto", estilo="auto", marca=None, lettering=True, biblio=None, serie=None):
    """Plano completo del diseno en dos piezas de arte sin texto + textos exactos para el motor.
    biblio: catalogo de la biblioteca de la marca (biblioteca.catalogo); el Director decide que reusar.
    serie: receta congelada (series.obtener); la cara queda fija y el Director solo escribe contenido."""
    if cat not in CATEGORIAS:
        raise ValueError("categoria invalida")
    if serie:
        import series
        formato = serie["formato"]
    msg = f"Idea del cliente:\n{idea}"
    if estilo in ESTILOS:
        msg += f"\n\nDireccion visual obligatoria: {ESTILOS[estilo]}"
    if marca and (kit := marcas.bloque_director(marca)):
        msg += "\n\n" + kit
    if formato in FORMATOS:
        msg += f"\n\nFormato obligatorio: {formato}"
    biblio = biblio if biblio and biblio.get("piezas") else None
    if biblio:
        msg += "\n\n" + biblio["texto"]
    if serie:
        msg += "\n\n" + series.encargo(serie)
    sistema = system_prompt(cat, cargar(), ARTE_V2.format(kits=kits.menu(), letras=letras.menu()) + (MEZCLA if biblio else ""))
    mensajes = [{"role": "system", "content": sistema}, {"role": "user", "content": msg}]
    for intento in range(2):  # si el Director se salta una pieza, se le pide de nuevo una vez
        try:
            out = _json_de(chat({"model": MODEL, "temperature": 0.7, "max_tokens": 6000, **RAPIDO,
                                 "response_format": {"type": "json_object"}, "messages": mensajes}))
        except ValueError:
            out = {}
        fondo = _caption_de(out.get("fondo") or out.get("background") or out.get("caption"))
        if fondo:
            break
        mensajes = mensajes[:2] + [{"role": "user", "content": msg + "\n\nIMPORTANTE: tu respuesta anterior no traia la clave "
                                     '"fondo" (objeto con canvas_settings y layers). Devuelve el JSON completo con TODAS las claves.'}]
    if not fondo:
        raise ValueError("El Director no devolvio el fondo dos veces seguidas; intenta de nuevo")
    eleccion = _eleccion(out.get("biblioteca"), biblio, idea)
    sin_protagonista = (not _caption_de(out.get("sujeto")) and not (eleccion and eleccion["sujeto"])
                        and cat not in ("tipografia", "logo") and not (serie and not serie.get("sujeto_zona")))
    if sin_protagonista:  # en la prueba de producto dejo un menu y una oferta de tostones sin comida: se le pide una vez mas
        try:
            otra = _json_de(chat({"model": MODEL, "temperature": 0.5, "max_tokens": 6000, **RAPIDO, "response_format": {"type": "json_object"},
                                  "messages": mensajes + [{"role": "assistant", "content": json.dumps(out, ensure_ascii=False)},
                                                          {"role": "user", "content": "Falta el SUJETO: esta pieza necesita un protagonista visual "
                                                           "(el plato, producto o persona de la idea, o un objeto heroe que la represente). Devuelve el "
                                                           'JSON completo otra vez, con "sujeto" (caption sobre croma) y "sujeto_zona".'}]}))
            if _caption_de(otra.get("sujeto")) and _caption_de(otra.get("fondo")):
                out, fondo = otra, _caption_de(otra.get("fondo"))
                if formato in FORMATOS:
                    fondo.setdefault("canvas_settings", {})["aspect_ratio"] = formato
        except Exception:  # el segundo pedido es un extra: si falla, sigue sin sujeto
            pass
    if serie and serie.get("fondo"):  # fondo fijo de la serie: siempre ese, aunque se haya usado la semana pasada
        eleccion = {**(eleccion or {"sujeto": None, "objetos": [], "motivo": ""}), "fondo": serie["fondo"]}
    if eleccion and eleccion["fondo"] and formato not in FORMATOS:  # fondo reusado: el lienzo toma su formato
        import biblioteca
        formato = biblioteca.ratio(biblio["piezas"][eleccion["fondo"]])
    if formato in FORMATOS:
        fondo.setdefault("canvas_settings", {})["aspect_ratio"] = formato
    crudos = out.get("textos")
    if serie and isinstance(crudos, list):  # en una serie la posicion la pone la serie: sin zona no se descarta
        crudos = [{**t, "zona": t.get("zona") or "cx: 0.5, cy: 0.5, w: 0.5, h: 0.1"} for t in crudos if isinstance(t, dict)]
    textos, fuentes = motor.normalizar(crudos, out.get("fuentes"))
    textos = [t for t in textos if t.get("pinta") != "ming"]
    if serie:
        textos = series.aplicar(textos, serie)
        if not any(t["rol"] != "logo" for t in textos):
            raise ValueError("El Director no escribió los textos de la serie; intenta de nuevo")
    textos = respetar_comillas(textos, idea)
    textos = ortografia(chat, textos, idea)
    textos = nombre_de_marca(textos, marca)
    sujeto = _caption_de(out.get("sujeto"))
    hay_sujeto = sujeto is not None or bool(eleccion and eleccion["sujeto"])
    detras = bool(out.get("titular_detras")) and hay_sujeto
    zona = None
    if hay_sujeto and serie and serie.get("sujeto_zona"):  # la serie fija donde va el plato
        detras = serie["titular_detras"]
        zona = motor.parse_zona(serie["sujeto_zona"])
        sujeto = _sin_texto(sujeto) if sujeto else None
    elif hay_sujeto:
        try:
            zona = motor.parse_zona(out.get("sujeto_zona") or "cx: 0.5, cy: 0.55, w: 0.6, h: 0.45")
        except ValueError:
            zona = motor.parse_zona("cx: 0.5, cy: 0.55, w: 0.6, h: 0.45")
        # el plano se valida antes de pintar: ningun texto encima del sujeto (salvo el titular si va detras)
        plano = {"layers": [{"description": "subject", "coordinates": "cx: {cx}, cy: {cy}, w: {w}, h: {h}".format(**zona)}]}
        motor.planificar(plano, textos, ignorar={"titulo"} if detras else set())
        zona = motor.heroe_en_hueco(textos, motor.parse_zona(plano["layers"][0]["coordinates"]),
                                    {"titulo"} if detras else frozenset())
        sujeto = _sin_texto(sujeto) if sujeto else None
    fondo = _sin_texto(motor.limpiar_caption(_solo_ambiente(fondo, zona), textos))
    kid = out.get("kit") if out.get("kit") in kits.KITS else kits.POR_CATEGORIA.get(cat, "impacto")
    colores = (marcas.listar().get(marca) or {}).get("colores") if marca else None
    lid = out.get("letra") if out.get("letra") in letras.LETRAS else None
    kit = kits.resolver(kid, colores, None, lid)
    if serie:  # misma tipografia y letra cada semana; el lettering de Ming saldria distinto cada vez
        kit, lid, lettering = serie["kit"], (serie["kit"].get("letra") or {}).get("id"), False
    titulo = next((t for t in textos if t["rol"] == "titulo"), None)
    letrero = None
    if lettering and titulo and titular_corto(titulo["texto"]):
        letrero = lettering_ming(titulo, kit, str(out.get("lettering") or ""), formato)
    return {
        "plan": (f'📌 Serie "{serie["nombre"]}": misma cara, contenido nuevo. ' if serie else "")
                + (eleccion["motivo"] + " " if eleccion and eleccion["motivo"] else "") + out.get("plan", "")
                + f" Kit tipografico: {kit['nombre']}." + (f" Letra: {kit['letra']['nombre']}." if lid else ""),
        "prompt": json.dumps(fondo, ensure_ascii=False),
        "hibrido": {"v": 2, "sujeto": json.dumps(sujeto, ensure_ascii=False) if sujeto else None, "sujeto_zona": zona,
                    "titular_detras": detras, "textos": textos, "fuentes": kit["fuentes"], "kit": kit, "lettering": letrero,
                    "biblioteca": {k: v for k, v in eleccion.items() if k != "motivo"} if eleccion else None},
    }


# ---------------------------------------------------------------------------
# Paso 3: Ming pinta SOLO el titular corto (lettering artistico) aislado sobre croma; el Director lo lee letra por
# letra y, si no coincide, se repinta o el titular vuelve a la letra del catalogo.
# ---------------------------------------------------------------------------
LETTERING_GRUPO = {
    "lujo": "elegant luxury lettering, refined serif and flowing script",
    "caligrafia": "flowing hand-painted brush script lettering with confident strokes",
    "urbano": "bold urban street lettering, graffiti and sticker culture",
    "retro": "vintage retro sign-painter lettering",
    "fiesta": "playful chunky festive lettering, bubbly and joyful",
    "terror": "dark dramatic horror poster lettering",
    "tech": "sleek futuristic display lettering",
    "deporte": "dynamic athletic varsity lettering",
    "mano": "authentic handmade chalk and brush lettering",
}
LETTERING_FX = {
    "oro": "polished metallic gold", "cromo": "mirror chrome", "holo": "iridescent holographic foil",
    "neon": "glowing neon light", "neon_tubo": "glowing neon tube sign", "sticker": "die-cut sticker with a thick outline",
    "doble_contorno": "double outline", "extrusion": "3D extruded letters", "sombra_larga": "retro long shadow",
    "sombra_dura": "hard offset drop shadow", "rayas": "70s striped echo outlines", "relieve": "embossed letterpress",
    "glitch": "RGB glitch split", "degradado": "smooth color gradient",
}


def _sin_marcas(texto):
    return re.sub(r"\*([^*\n]+)\*", r"\1", texto).replace("\n", " ").strip()


def titular_corto(texto):
    """Ming solo rotula titulares cortos: con mas palabras su ortografia falla y el lettering pierde fuerza."""
    t = _sin_marcas(texto)
    return 0 < len(t.split()) <= 4 and len(t) <= 32


def _croma_para(colores):
    """Magenta salvo que el lettering lleve rosados/morados (ahi verde). Probado: con verde, Ming lo uso de adorno
    dentro del lettering de una marca de comida; el magenta casi nunca aparece en una marca."""
    def dist(a, b):
        return sum((int(a[i:i + 2], 16) - int(b[i:i + 2], 16)) ** 2 for i in (1, 3, 5)) ** 0.5
    cols = [c for c in colores if isinstance(c, str) and len(c) == 7]
    return "verde" if any(dist(CROMA["magenta"], c) < 150 for c in cols) else "magenta"


def _aspecto(zona, formato):
    """Formato de Ming mas parecido a la zona del titular (Ming no pinta mas ancho que 16:9)."""
    W, H = (int(x) for x in formato.split(":")) if formato in FORMATOS else (4, 5)
    r = zona["w"] * W / max(1e-6, zona["h"] * H)
    opciones = {"16:9": 16 / 9, "16:10": 1.6, "1:1": 1.0, "4:5": 0.8, "3:4": 0.75}
    return min(opciones, key=lambda k: abs(opciones[k] - r))


def lettering_ming(titulo, kit, estilo_director="", formato="auto"):
    """Pedido a Ming para rotular SOLO el titular, aislado sobre croma plano. Devuelve {caption, esperado}."""
    texto = _sin_marcas(titulo["texto"])
    claves = re.findall(r"\*([^*\n]+)\*", titulo["texto"])
    pal = kit["paleta"]
    colores = [pal["primario"], pal["acento"], pal["claro"]]
    nombre = _croma_para(colores + [pal["oscuro"]])
    letra = (kit.get("letra") or {}).get("id")
    base = []
    if letra in letras.LETRAS:
        le = letras.LETRAS[letra]
        base.append(LETTERING_GRUPO[le["grupo"]])
        if le.get("fx") in LETTERING_FX:
            base.append(LETTERING_FX[le["fx"]])
    estilo = ", ".join(x for x in [estilo_director.strip().rstrip("."), *base] if x) or "bold artistic headline lettering"
    enfasis = f' The words "{", ".join(claves)}" are the hero words: larger or in a contrasting accent style.' if claves else ""
    cap = {
        "canvas_settings": {
            "aspect_ratio": _aspecto(titulo["zona"], formato),
            "image_style": (f"Isolated hand-lettering artwork on a perfectly flat, uniform pure {nombre} ({CROMA[nombre]}) chroma-key "
                            "background filling the whole frame edge to edge. Only the headline lettering, centered, filling about 88% of "
                            "the canvas width. No other text, no extra letters, no objects, no scene, no frame, no border, no floor, no "
                            f"gradient or shadow on the background. The lettering never uses {nombre} or similar colors. Style: {estilo}."),
        },
        "layers": [
            {"description": f"Perfectly flat, uniform, solid pure {nombre} ({CROMA[nombre]}) chroma-key backdrop filling the entire canvas "
                            "edge to edge: no texture, no gradient, no vignette, no shadow.",
             "coordinates": "cx: 0.500, cy: 0.500, w: 1.000, h: 1.000",
             "hierarchy_and_relation": "Bottom layer; the lettering sits on top of it.", "color_specs": [CROMA[nombre]]},
            {"description": f'Headline lettering reading exactly "{texto}", spelled letter by letter exactly like that, every accent and '
                            f"symbol preserved, nothing added or removed. {estilo}.{enfasis} Perfectly legible.",
             "coordinates": "cx: 0.500, cy: 0.500, w: 0.900, h: 0.760",
             "hierarchy_and_relation": "The only element on the canvas.", "color_specs": colores},
        ],
    }
    return {"caption": json.dumps(cap, ensure_ascii=False), "esperado": texto}


def _norm(t):
    """Para comparar lo que Ming escribio: sin mayusculas ni signos sueltos; las letras (con tilde y ñ) cuentan todas."""
    return re.sub(r"[^\w&$%€]+", " ", t.casefold()).strip()


def leer_titular(chat, png_bytes):
    """El Director transcribe el lettering tal cual lo ve (sin corregir)."""
    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    img.thumbnail((1024, 1024))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=90)
    out = _json_de(chat({
        "model": MODEL, "temperature": 0, "max_tokens": 200, **RAPIDO,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": (
                "You are a strict proofreader. Transcribe EXACTLY every letter, number and symbol painted in the image, as written, "
                "including spelling mistakes, missing or extra letters and missing accents. Do not correct anything. "
                'Answer ONLY JSON: {"texto": "transcription"}')},
            {"role": "user", "content": [{"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()}}]},
        ],
    }))
    return str(out.get("texto", ""))[:200]


def titular_correcto(leido, esperado):
    return _norm(leido) == _norm(esperado)


def reforzar_lettering(caption, esperado, leido):
    """Reintento: se le muestra a Ming lo que escribio mal y se deletrea el texto."""
    cap = json.loads(caption)
    deletreo = " - ".join(esperado.replace(" ", "_"))
    capa = cap["layers"][-1]
    capa["description"] = (f'SPELLING IS CRITICAL. The previous attempt wrote "{leido}", which is WRONG. Write exactly "{esperado}" '
                           f"(letter by letter: {deletreo}; _ is a space). " + capa["description"])
    return json.dumps(cap, ensure_ascii=False)


def _solo_ambiente(fondo, zona_sujeto):
    """El fondo es ambiente: se descartan capas de objetos (chicas) salvo las que sostienen al sujeto (pedestal, halo)."""
    capas = []
    for c in fondo.get("layers", []):
        try:
            z = motor.parse_zona(c.get("coordinates", ""))
        except ValueError:
            capas.append(c)
            continue
        grande = z["w"] * z["h"] >= 0.45
        bajo_sujeto = zona_sujeto is not None and motor._choca(z, zona_sujeto, 0) and z["cy"] >= zona_sujeto["cy"]
        if grande or bajo_sujeto:
            capas.append(c)
    fondo["layers"] = capas or fondo.get("layers", [])[:1]
    cs = fondo.setdefault("canvas_settings", {})
    cs["image_style"] = str(cs.get("image_style", "")).rstrip(". ") + ". Ambient backdrop only, no foreground objects, no devices, no props."
    return fondo


SIN_FIGURAS = " Empty environment: no characters, no people, no robots, no creatures, no products, no devices."


CROMA = {"magenta": "#FF00FF", "verde": "#00FF00"}


def forzar_croma(prompt):
    """El recorte depende de que el sujeto venga sobre croma plano: se exige por codigo, no se confia en el Director.
    Magenta por defecto (comida y productos tienen verdes, casi nunca magenta puro); verde si el sujeto es rosa/morado."""
    try:
        cap = json.loads(prompt)
    except ValueError:
        return prompt
    texto = json.dumps(cap, ensure_ascii=False).lower()
    nombre = "verde" if any(w in texto for w in ("pink", "magenta", "purple", "violet", "fuchsia", "rosa", "morado")) else "magenta"
    # el croma va como capa de fondo extra; NUNCA se borra nada del sujeto (una capa a lienzo completo puede ser
    # el sujeto mismo: borrarla hizo que Ming inventara otro plato). Ming igual puede ignorar el croma: el recorte
    # no depende de el (BiRefNet), solo lo aprovecha si llega.
    capas = list(cap.get("layers", []))
    cap["layers"] = [{"description": f"Perfectly flat, uniform, solid pure {nombre} ({CROMA[nombre]}) chroma-key backdrop filling the entire "
                                     "canvas edge to edge: no texture, no gradient, no vignette, no floor, no shadow.",
                      "coordinates": "cx: 0.500, cy: 0.500, w: 1.000, h: 1.000",
                      "hierarchy_and_relation": "Bottom layer; the isolated subject sits on top of it.",
                      "color_specs": [CROMA[nombre]]}] + capas
    cs = cap.setdefault("canvas_settings", {})
    estilo = str(cs.get("image_style", ""))
    if "chroma-key background" not in estilo:
        cs["image_style"] = (f"Studio cutout: the subject is isolated on a perfectly flat, uniform pure {nombre} ({CROMA[nombre]}) "
                             "chroma-key background filling the whole frame, no gradient, no floor, no cast shadow, no colored light "
                             "on the subject. The whole subject is fully visible and centered with a generous empty margin on every side: "
                             "nothing touches or is cut by the canvas edges. " + estilo)
    return json.dumps(cap, ensure_ascii=False)


def reforzar_sin_texto(prompt, fondo=False):
    """Reintento cuando Ming colo letras (o un protagonista en el fondo): se repite la prohibicion con mas fuerza."""
    extra = SIN_TEXTO + (SIN_FIGURAS if fondo else "")
    try:
        cap = json.loads(prompt)
    except ValueError:
        return prompt + extra
    cs = cap.setdefault("canvas_settings", {})
    cs["image_style"] = ("STRICTLY TEXT-FREE, EMPTY BACKDROP. " if fondo else "STRICTLY TEXT-FREE ARTWORK. ") + str(cs.get("image_style", "")) + extra
    return json.dumps(cap, ensure_ascii=False)


def detectar_texto(chat, png_bytes, fondo=False):
    """El Director revisa el arte: ¿Ming colo letras? En un fondo tambien: ¿pinto un protagonista (persona,
    robot, producto) que no pediamos? Devuelve (hay_problema, que_vio)."""
    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    img.thumbnail((896, 896))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    out = _json_de(chat({
        "model": MODEL, "temperature": 0, "max_tokens": 200, **RAPIDO,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": (
                "You check artwork for any rendered text. Text means readable or pseudo letters, numbers, words, signage, "
                "labels, logos with letters, or text on screens. Abstract shapes and icons without letters are NOT text. "
                + ("This image must be an EMPTY BACKDROP: also report as a problem any character, person, robot, creature, "
                   "product or device in it (light, particles, abstract shapes and a plain pedestal are fine). " if fondo else "")
                + 'Answer ONLY JSON: {"texto": true|false, "donde": "short description or empty"}  (texto=true means any problem found)')},
            {"role": "user", "content": [{"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()}}]},
        ],
    }))
    return bool(out.get("texto")), str(out.get("donde", ""))[:200]
