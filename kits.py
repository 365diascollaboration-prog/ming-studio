"""Kits tipograficos: sistemas completos disenados a mano. El Director solo ELIGE uno; la calidad la pone el kit.

Cada kit define fuentes (Google Fonts), escala (tamano de cada rol relativo al titular), tratamientos y estilo
de precio, lista, boton y sticker. Los colores salen del kit de marca (o de la paleta propia del kit).
Roles de color: primario, acento, claro, oscuro.
"""
import colorsys
import letras

KITS = {
    "neon": {
        "nombre": "Neón Nocturno", "para": "fondos oscuros, tech, fiestas, música urbana, noche",
        "fuentes": {"titulo": "Bebas Neue", "cuerpo": "Outfit"},
        "titulo": {"peso": 400, "mayus": True, "tracking": 0.02, "linea": 0.92, "efecto": "neon", "color": "claro", "brillo": "acento"},
        "clave": {"efecto": "neon", "color": "acento"},
        "cuerpo": {"peso": 400, "tracking": 0.01},
        "subtitulo": {"peso": 300, "mayus": True, "tracking": 0.18, "color": "claro"},
        "precio": {"fuente": "titulo", "peso": 400, "efecto": "neon", "color": "claro", "brillo": "primario"},
        "lista": {"vinieta": "check", "color": "claro"},
        "cta": {"estilo": "contorno", "radio": 0.5, "color": "acento", "mayus": True, "tracking": 0.12},
        "sticker": {"forma": "circulo", "color": "acento"},
        "escala": {"subtitulo": 0.34, "precio": 1.0, "lista": 0.26, "texto": 0.26, "cta": 0.3, "contacto": 0.2, "sticker": 0.4},
        "paleta": {"primario": "#00e5ff", "acento": "#ff2bd6", "claro": "#ffffff", "oscuro": "#07060d"},
    },
    "impacto": {
        "nombre": "Impacto Promo", "para": "ofertas, descuentos, retail, comida rápida, eventos masivos",
        "fuentes": {"titulo": "Anton", "cuerpo": "Archivo"},
        "titulo": {"peso": 400, "mayus": True, "tracking": 0.0, "linea": 0.9, "efecto": "extrusion", "color": "claro", "sombra": "primario"},
        "clave": {"efecto": "resaltado", "color": "oscuro", "fondo": "acento"},
        "cuerpo": {"peso": 600, "tracking": 0.0},
        "subtitulo": {"peso": 800, "mayus": True, "tracking": 0.04, "color": "acento"},
        "precio": {"fuente": "titulo", "peso": 400, "efecto": "extrusion", "color": "acento", "sombra": "oscuro"},
        "lista": {"vinieta": "flecha", "color": "claro"},
        "cta": {"estilo": "solido", "radio": 0.15, "color": "acento", "mayus": True, "tracking": 0.06},
        "sticker": {"forma": "estrella", "color": "acento"},
        "escala": {"subtitulo": 0.4, "precio": 1.15, "lista": 0.3, "texto": 0.3, "cta": 0.36, "contacto": 0.22, "sticker": 0.5},
        "paleta": {"primario": "#e11d2a", "acento": "#ffd400", "claro": "#ffffff", "oscuro": "#111111"},
    },
    "lujo": {
        "nombre": "Editorial Lujo", "para": "joyería, perfumes, moda, restaurantes finos, bienes raíces, bodas",
        "fuentes": {"titulo": "Playfair Display", "cuerpo": "Montserrat"},
        "titulo": {"peso": 500, "mayus": False, "tracking": -0.01, "linea": 1.02, "efecto": "degradado", "color": "acento", "color2": "claro"},
        "clave": {"efecto": "degradado", "color": "acento", "color2": "primario"},
        "cuerpo": {"peso": 400, "tracking": 0.02},
        "subtitulo": {"peso": 500, "mayus": True, "tracking": 0.28, "color": "claro"},
        "precio": {"fuente": "titulo", "peso": 400, "efecto": "degradado", "color": "acento", "color2": "claro"},
        "lista": {"vinieta": "rombo", "color": "claro"},
        "cta": {"estilo": "contorno", "radio": 0.0, "color": "acento", "mayus": True, "tracking": 0.3},
        "sticker": {"forma": "circulo", "color": "acento"},
        "escala": {"subtitulo": 0.26, "precio": 0.8, "lista": 0.24, "texto": 0.24, "cta": 0.24, "contacto": 0.18, "sticker": 0.34},
        "paleta": {"primario": "#b88a44", "acento": "#e6c77a", "claro": "#f7f1e6", "oscuro": "#141110"},
    },
    "tech": {
        "nombre": "Tech Limpio", "para": "software, apps, SaaS, agencias digitales, servicios B2B, IA",
        "fuentes": {"titulo": "Space Grotesk", "cuerpo": "Inter"},
        "titulo": {"peso": 700, "mayus": False, "tracking": -0.03, "linea": 1.0, "efecto": "ninguno", "color": "claro"},
        "clave": {"efecto": "color", "color": "acento"},
        "cuerpo": {"peso": 400, "tracking": 0.0},
        "subtitulo": {"peso": 500, "mayus": False, "tracking": 0.0, "color": "primario"},
        "precio": {"fuente": "titulo", "peso": 700, "efecto": "degradado", "color": "primario", "color2": "acento"},
        "lista": {"vinieta": "check", "color": "claro"},
        "cta": {"estilo": "solido", "radio": 0.5, "color": "primario", "mayus": False, "tracking": 0.0},
        "sticker": {"forma": "pildora", "color": "acento"},
        "escala": {"subtitulo": 0.38, "precio": 0.95, "lista": 0.28, "texto": 0.28, "cta": 0.3, "contacto": 0.2, "sticker": 0.3},
        "paleta": {"primario": "#3b82f6", "acento": "#22d3ee", "claro": "#ffffff", "oscuro": "#0a0f1c"},
    },
    "urbano": {
        "nombre": "Urbano Callejero", "para": "reggaetón, trap, streetwear, barberías, deportes, eventos de calle",
        "fuentes": {"titulo": "Bebas Neue", "cuerpo": "Archivo"},
        "titulo": {"peso": 400, "mayus": True, "tracking": 0.01, "linea": 0.88, "efecto": "sombra_dura", "color": "claro", "sombra": "acento"},
        "clave": {"efecto": "contorno", "color": "acento"},
        "cuerpo": {"peso": 700, "tracking": 0.02},
        "subtitulo": {"peso": 800, "mayus": True, "tracking": 0.1, "color": "acento"},
        "precio": {"fuente": "titulo", "peso": 400, "efecto": "sombra_dura", "color": "claro", "sombra": "acento"},
        "lista": {"vinieta": "flecha", "color": "claro"},
        "cta": {"estilo": "solido", "radio": 0.0, "color": "acento", "mayus": True, "tracking": 0.12},
        "sticker": {"forma": "cinta", "color": "acento"},
        "escala": {"subtitulo": 0.36, "precio": 1.0, "lista": 0.28, "texto": 0.28, "cta": 0.32, "contacto": 0.2, "sticker": 0.4},
        "paleta": {"primario": "#ffffff", "acento": "#c6ff00", "claro": "#ffffff", "oscuro": "#0b0b0b"},
    },
    "tropical": {
        "nombre": "Tropical Fiesta", "para": "comida caribeña, playa, verano, fiestas, bebidas, turismo",
        "fuentes": {"titulo": "Lilita One", "cuerpo": "Nunito"},
        "titulo": {"peso": 400, "mayus": False, "tracking": 0.0, "linea": 0.95, "efecto": "sombra_dura", "color": "claro", "sombra": "primario"},
        "clave": {"efecto": "sombra_dura", "color": "acento", "sombra": "oscuro"},
        "cuerpo": {"peso": 700, "tracking": 0.0},
        "subtitulo": {"peso": 800, "mayus": False, "tracking": 0.0, "color": "acento"},
        "precio": {"fuente": "titulo", "peso": 400, "efecto": "sombra_dura", "color": "acento", "sombra": "oscuro"},
        "lista": {"vinieta": "estrella", "color": "claro"},
        "cta": {"estilo": "solido", "radio": 0.5, "color": "acento", "mayus": False, "tracking": 0.0},
        "sticker": {"forma": "estrella", "color": "acento"},
        "escala": {"subtitulo": 0.4, "precio": 1.05, "lista": 0.3, "texto": 0.3, "cta": 0.34, "contacto": 0.22, "sticker": 0.46},
        "paleta": {"primario": "#0f8b8d", "acento": "#ffb627", "claro": "#fffaf0", "oscuro": "#1d1a2f"},
    },
    "retro": {
        "nombre": "Retro 70s", "para": "salsa, cafeterías, vintage, música retro, marcas nostálgicas",
        "fuentes": {"titulo": "Shrikhand", "cuerpo": "DM Sans"},
        "titulo": {"peso": 400, "mayus": False, "tracking": 0.0, "linea": 1.0, "efecto": "extrusion", "color": "acento", "sombra": "primario"},
        "clave": {"efecto": "extrusion", "color": "claro", "sombra": "primario"},
        "cuerpo": {"peso": 500, "tracking": 0.02},
        "subtitulo": {"peso": 700, "mayus": True, "tracking": 0.2, "color": "claro"},
        "precio": {"fuente": "titulo", "peso": 400, "efecto": "extrusion", "color": "claro", "sombra": "primario"},
        "lista": {"vinieta": "punto", "color": "claro"},
        "cta": {"estilo": "solido", "radio": 0.5, "color": "acento", "mayus": True, "tracking": 0.1},
        "sticker": {"forma": "circulo", "color": "primario"},
        "escala": {"subtitulo": 0.3, "precio": 0.9, "lista": 0.26, "texto": 0.26, "cta": 0.28, "contacto": 0.2, "sticker": 0.4},
        "paleta": {"primario": "#d9480f", "acento": "#ffd23f", "claro": "#fff4e0", "oscuro": "#2b1a12"},
    },
    "corporativo": {
        "nombre": "Corporativo Premium", "para": "servicios profesionales, consultoría, finanzas, salud, educación",
        "fuentes": {"titulo": "Montserrat", "cuerpo": "Montserrat"},
        "titulo": {"peso": 800, "mayus": False, "tracking": -0.02, "linea": 1.02, "efecto": "ninguno", "color": "claro"},
        "clave": {"efecto": "color", "color": "acento"},
        "cuerpo": {"peso": 400, "tracking": 0.0},
        "subtitulo": {"peso": 500, "mayus": True, "tracking": 0.14, "color": "acento"},
        "precio": {"fuente": "titulo", "peso": 800, "efecto": "ninguno", "color": "claro"},
        "lista": {"vinieta": "check", "color": "claro"},
        "cta": {"estilo": "solido", "radio": 0.12, "color": "acento", "mayus": True, "tracking": 0.08},
        "sticker": {"forma": "pildora", "color": "acento"},
        "escala": {"subtitulo": 0.3, "precio": 0.85, "lista": 0.26, "texto": 0.26, "cta": 0.26, "contacto": 0.19, "sticker": 0.3},
        "paleta": {"primario": "#1e3a8a", "acento": "#38bdf8", "claro": "#ffffff", "oscuro": "#0b1220"},
    },
    "artesanal": {
        "nombre": "Artesanal", "para": "panadería, café de especialidad, orgánicos, hecho a mano, emprendimientos locales",
        "fuentes": {"titulo": "Caveat", "cuerpo": "Lora"},
        "titulo": {"peso": 700, "mayus": False, "tracking": 0.0, "linea": 0.95, "efecto": "ninguno", "color": "claro"},
        "clave": {"efecto": "subrayado", "color": "acento"},
        "cuerpo": {"peso": 400, "tracking": 0.0},
        "subtitulo": {"peso": 500, "mayus": True, "tracking": 0.22, "color": "acento"},
        "precio": {"fuente": "titulo", "peso": 700, "efecto": "ninguno", "color": "acento"},
        "lista": {"vinieta": "rombo", "color": "claro"},
        "cta": {"estilo": "contorno", "radio": 0.5, "color": "acento", "mayus": False, "tracking": 0.02},
        "sticker": {"forma": "circulo", "color": "acento"},
        "escala": {"subtitulo": 0.28, "precio": 0.85, "lista": 0.28, "texto": 0.28, "cta": 0.3, "contacto": 0.2, "sticker": 0.4},
        "paleta": {"primario": "#7c4a2d", "acento": "#e9a23b", "claro": "#fbf6ee", "oscuro": "#2a1d14"},
    },
    "minimal": {
        "nombre": "Minimal Bold", "para": "marcas modernas, lanzamientos, arquitectura, arte, frases de impacto",
        "fuentes": {"titulo": "Archivo Black", "cuerpo": "Inter"},
        "titulo": {"peso": 400, "mayus": True, "tracking": -0.04, "linea": 0.88, "efecto": "ninguno", "color": "claro"},
        "clave": {"efecto": "contorno", "color": "claro"},
        "cuerpo": {"peso": 500, "tracking": 0.0},
        "subtitulo": {"peso": 600, "mayus": True, "tracking": 0.24, "color": "claro"},
        "precio": {"fuente": "titulo", "peso": 400, "efecto": "ninguno", "color": "acento"},
        "lista": {"vinieta": "numero", "color": "claro"},
        "cta": {"estilo": "solido", "radio": 0.0, "color": "claro", "mayus": True, "tracking": 0.16},
        "sticker": {"forma": "circulo", "color": "acento"},
        "escala": {"subtitulo": 0.22, "precio": 0.9, "lista": 0.22, "texto": 0.22, "cta": 0.22, "contacto": 0.17, "sticker": 0.3},
        "paleta": {"primario": "#111111", "acento": "#ff4d2e", "claro": "#ffffff", "oscuro": "#0a0a0a"},
    },
}

POR_CATEGORIA = {"flyer": "impacto", "cartel": "impacto", "tipografia": "minimal", "musica": "urbano", "pelicula": "lujo",
                 "web": "tech", "evento": "neon", "historia": "impacto", "post": "tech", "producto": "lujo",
                 "logo": "minimal", "infografia": "corporativo"}


def _hsl(hexa):
    r, g, b = (int(hexa[i:i + 2], 16) / 255 for i in (1, 3, 5))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    return h, s, l


def paleta_de_marca(colores, base):
    """Mapea los colores del kit de marca a los roles del kit: primario (el mas saturado de tono medio), acento
    (el saturado mas lejano en tono), claro y oscuro. Lo que la marca no cubre lo pone la paleta del kit."""
    pal = dict(base)
    cols = [c for c in colores or [] if isinstance(c, str) and len(c) == 7]
    if not cols:
        return pal
    info = {c: _hsl(c) for c in cols}
    vivos = sorted((c for c in cols if 0.18 < info[c][2] < 0.85 and info[c][1] > 0.25), key=lambda c: -info[c][1])
    if vivos:
        pal["primario"] = vivos[0]
        h0 = info[vivos[0]][0]
        dist = lambda c: min(abs(info[c][0] - h0), 1 - abs(info[c][0] - h0))
        viveza = lambda c: info[c][1] * (1 - abs(info[c][2] - 0.55) * 1.5)  # saturado y de luz media = llamativo
        # contraste por tono (azul vs naranja) o por luz (rojo vino vs dorado claro)
        contrastan = [c for c in vivos[1:] if dist(c) > 0.12 or (dist(c) > 0.05 and abs(info[c][2] - info[vivos[0]][2]) > 0.25)]
        pal["acento"] = max(contrastan, key=viveza) if contrastan else (vivos[1] if len(vivos) > 1 else vivos[0])
    claros = [c for c in cols if info[c][2] > 0.88]
    oscuros = [c for c in cols if info[c][2] < 0.12]
    if claros:
        pal["claro"] = max(claros, key=lambda c: info[c][2])
    if oscuros:
        pal["oscuro"] = min(oscuros, key=lambda c: info[c][2])
    return pal


def resolver(kid, colores_marca=None, fuentes_marca=None, letra=None):
    """Kit listo para el lienzo: roles de color convertidos a hex. Las fuentes de la marca mandan si las tiene.
    Con `letra` (ver letras.py) el titular y su palabra clave se visten con ese estilo de letra."""
    k = KITS.get(kid) or KITS["impacto"]
    pal = paleta_de_marca(colores_marca, k["paleta"])
    out = {"id": kid if kid in KITS else "impacto", "nombre": k["nombre"], "paleta": pal,
           "fuentes": {**k["fuentes"], **(fuentes_marca or {})}, "escala": k["escala"]}
    for rol in ("titulo", "clave", "cuerpo", "subtitulo", "precio", "lista", "cta", "sticker"):
        estilo = dict(k[rol])
        for campo in ("color", "color2", "brillo", "sombra", "fondo"):
            if estilo.get(campo) in pal:
                estilo[campo] = pal[estilo[campo]]
        out[rol] = estilo
    if letra in letras.LETRAS:
        letras.aplicar(out, letra, pal)
    return out


def menu():
    """Lista corta para que el Director elija."""
    return "\n".join(f'- "{k}": {v["nombre"]} (ideal para {v["para"]})' for k, v in KITS.items())


if __name__ == "__main__":
    # la paleta de 365 Collaboration: celestes (primario) + naranja (acento), claro/oscuro de la marca
    p = paleta_de_marca(["#76c0fc", "#3ebfff", "#97e1fe", "#842915", "#f57905", "#050505"], KITS["tech"]["paleta"])
    assert p["primario"] in ("#3ebfff", "#76c0fc") and p["acento"] == "#f57905" and p["oscuro"] == "#050505", p
    r = resolver("neon", ["#b20101", "#e5b26c"])
    assert r["titulo"]["brillo"].startswith("#") and r["cta"]["color"].startswith("#")
    assert resolver("inexistente")["id"] == "impacto"
    r = resolver("impacto", None, None, "gala-oro")
    assert r["letra"]["id"] == "gala-oro" and r["fuentes"]["precio"] == "Anton" and r["clave"]["fuente"] == "Great Vibes"
    assert "letra" not in resolver("impacto", None, None, "no-existe")
    print("ok kits")
