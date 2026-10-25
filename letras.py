"""Estilos de letra para el titular: fuente de cartel + tratamiento de rotulista (+ fuente propia para la palabra clave).

El kit pone el sistema (escala, colores, boton, lista); la letra viste SOLO el titular y su palabra clave.
Todas son de Google Fonts (licencia libre, uso comercial). Colores por rol: primario, acento, claro, oscuro.
Campos: f fuente, p peso, may mayusculas, tr tracking (em), ln interlineado, fx efecto, it italica, arco (curva 0-0.3),
desgaste (textura gastada), color/color2/sombra/brillo/borde (roles). clave: lo mismo + tam (x tamano) y rot (grados).
"""

GRUPOS = {
    "lujo": "Lujo y elegancia",
    "caligrafia": "Caligrafía",
    "urbano": "Urbano y grafiti",
    "retro": "Retro y vintage",
    "fiesta": "Fiesta y tropical",
    "terror": "Oscuro y terror",
    "tech": "Tech y futurista",
    "deporte": "Deportivo y póster",
    "mano": "Hecho a mano",
}

# caligraficas: nunca en mayusculas (un rotulista no las escribe asi); el lienzo las pasa a Tipo Titulo
SCRIPT = {"Great Vibes", "Allura", "Pacifico", "Yellowtail", "Kaushan Script", "Lobster", "Parisienne", "Sacramento",
          "Dancing Script", "Caveat", "Caveat Brush"}

L = lambda n, g, para, f, clave=None, **k: {"nombre": n, "grupo": g, "para": para, "f": f, "clave": clave or {}, **k}

LETRAS = {
    # lujo y elegancia
    "gala-oro": L("Gala de Oro", "lujo", "bodas, joyería, galas, aniversarios", "Cinzel", p=700, may=True, tr=.06, ln=1.05, fx="oro",
                  clave=dict(f="Great Vibes", fx="oro", tam=1.45, rot=-4, may=False, tr=0)),
    "revista-bodoni": L("Revista Bodoni", "lujo", "moda, belleza, portadas editoriales", "Bodoni Moda", p=700, tr=-.02, ln=.95, fx="color",
                        clave=dict(it=True, color="acento")),
    "firma-playfair": L("Playfair con Firma", "lujo", "restaurantes finos, vinos, perfumes", "Playfair Display", p=800, tr=-.01, ln=1.0, fx="color",
                        clave=dict(f="Allura", tam=1.5, rot=-6, color="acento", tr=0)),
    "cormorant-fino": L("Cormorant Fino", "lujo", "spa, bienes raíces, arquitectura", "Cormorant Garamond", p=600, may=True, tr=.12, ln=1.0,
                        fx="degradado", color="acento", color2="claro", clave=dict(it=True, may=False, fx="color", color="acento")),
    "italiana-moda": L("Italiana Moda", "lujo", "boutiques, moda, joyería minimal", "Italiana", may=True, tr=.2, ln=1.05, fx="color",
                       clave=dict(fx="oro")),
    "deco-gatsby": L("Art Déco Gatsby", "lujo", "fiestas de gala, cócteles, años 20", "Poiret One", may=True, tr=.14, ln=1.05, fx="oro",
                     clave=dict(f="Limelight", fx="oro", may=True)),
    "cine-limelight": L("Estreno de Cine", "lujo", "películas, teatro, estrenos", "Limelight", may=True, tr=.04, ln=1.0, fx="cromo",
                        clave=dict(fx="oro")),
    "decorativa-cinzel": L("Imperial", "lujo", "eventos premium, marcas clásicas", "Cinzel Decorative", p=700, may=True, tr=.04, ln=1.05, fx="oro",
                           clave=dict(fx="cromo")),
    "serif-calido": L("Serif Cálido", "lujo", "cafeterías finas, panaderías, libros", "DM Serif Display", tr=-.01, ln=.95, fx="relieve",
                      clave=dict(it=True, color="acento", fx="relieve")),
    "fraunces-suave": L("Fraunces Suave", "lujo", "marcas modernas cálidas, packaging", "Fraunces", p=800, tr=-.03, ln=.92, fx="color",
                        clave=dict(it=True, color="acento")),
    # caligrafia
    "firma-vibes": L("Firma Elegante", "caligrafia", "invitaciones, quinceañeras, bodas", "Great Vibes", ln=1.1, fx="color",
                     clave=dict(color="acento")),
    "pacifico-playa": L("Pacifico Playa", "caligrafia", "playa, surf, heladerías, verano", "Pacifico", ln=1.2, fx="sombra_dura", sombra="primario",
                        clave=dict(color="acento", fx="sombra_dura", sombra="oscuro")),
    "yellowtail-retro": L("Rótulo Retro", "caligrafia", "diners, barberías clásicas, autos", "Yellowtail", ln=1.1, fx="sombra_larga", sombra="primario", arco=.18,
                          clave=dict(color="acento", fx="sombra_larga", sombra="oscuro")),
    "brocha-kaushan": L("Brocha Rápida", "caligrafia", "deportes, fitness, comida callejera", "Kaushan Script", ln=1.05, fx="sombra_dura", sombra="oscuro",
                        clave=dict(color="acento")),
    "lobster-clasico": L("Lobster Clásico", "caligrafia", "pizzerías, comida familiar, ferias", "Lobster", ln=1.05, fx="extrusion", sombra="primario",
                         clave=dict(color="acento", fx="extrusion", sombra="oscuro")),
    "parisienne-oro": L("Parisienne Dorada", "caligrafia", "perfumes, champaña, bodas", "Parisienne", ln=1.1, fx="oro",
                        clave=dict(fx="oro")),
    "neon-letrero": L("Letrero de Neón", "caligrafia", "bares, noches, cócteles, karaoke", "Sacramento", ln=1.05, fx="neon_tubo", brillo="acento",
                      clave=dict(fx="neon_tubo", brillo="primario")),
    "dancing-dulce": L("Dulce", "caligrafia", "repostería, pasteles, regalos", "Dancing Script", p=700, ln=1.0, fx="sombra_dura", sombra="oscuro",
                       clave=dict(color="acento")),
    # urbano y grafiti
    "spray-calle": L("Spray Callejero", "urbano", "reggaetón, trap, eventos de calle", "Sedgwick Ave Display", ln=.95, fx="sticker", borde="oscuro",
                     color="claro", clave=dict(color="acento", fx="sticker", borde="oscuro")),
    "marcador": L("Marcador", "urbano", "barberías, tatuajes, juveniles", "Permanent Marker", may=True, ln=1.0, fx="sombra_dura", sombra="acento",
                  clave=dict(color="acento", fx="sombra_dura", sombra="oscuro")),
    "tiza-salvaje": L("Trazo Salvaje", "urbano", "rock, conciertos, bares", "Rock Salt", may=True, ln=1.15, fx="color", desgaste=True,
                      clave=dict(color="acento")),
    "bungee-calle": L("Bungee Calle", "urbano", "streetwear, skate, juegos", "Bungee", may=True, ln=.95, fx="sombra_larga", sombra="acento",
                      clave=dict(color="acento", fx="sombra_larga", sombra="oscuro")),
    "glitch-trap": L("Glitch Trap", "urbano", "trap, gaming, música electrónica", "Rubik Glitch", may=True, ln=.95, fx="glitch",
                     clave=dict(color="acento", fx="glitch")),
    "pintura-chorreada": L("Pintura Chorreada", "urbano", "halloween urbano, grafiti, rap", "Rubik Wet Paint", may=True, ln=1.0, fx="color",
                           clave=dict(color="acento")),
    "anton-sticker": L("Sticker Bold", "urbano", "promos, ofertas, comida rápida", "Anton", may=True, ln=.92, fx="sticker", borde="oscuro",
                       clave=dict(color="acento", fx="sticker", borde="oscuro")),
    "cromo-reggaeton": L("Cromo Reggaetón", "urbano", "portadas de música, perreo, discotecas", "Bebas Neue", may=True, tr=.02, ln=.9, fx="cromo",
                         clave=dict(fx="holo")),
    "monoton-neon": L("Neón Monoton", "urbano", "discotecas, retro 80s, fiestas", "Monoton", may=True, ln=1.0, fx="neon_tubo", brillo="acento",
                      clave=dict(fx="neon_tubo", brillo="primario")),
    # retro y vintage
    "setentas": L("Rayas 70s", "retro", "salsa, funk, cafeterías vintage", "Shrikhand", ln=1.0, fx="rayas", color="acento", color2="claro", sombra="primario",
                  clave=dict(color="claro", fx="rayas", color2="acento", sombra="primario")),
    "groovy": L("Groovy", "retro", "vinilos, ropa vintage, festivales", "Bagel Fat One", ln=.95, fx="extrusion", color="acento", sombra="primario", arco=.15,
                clave=dict(color="claro", fx="extrusion", sombra="primario")),
    "synthwave": L("Synthwave", "retro", "fiestas 80s, gaming, música retro", "Righteous", may=True, tr=.04, ln=.95, fx="holo",
                   clave=dict(fx="cromo")),
    "arcade": L("Arcade", "retro", "videojuegos, gaming, tech retro", "Press Start 2P", may=True, ln=1.3, fx="sombra_dura", sombra="acento",
                clave=dict(color="acento", fx="sombra_dura", sombra="oscuro")),
    "western": L("Viejo Oeste", "retro", "BBQ, cervecerías, rodeo, country", "Rye", may=True, tr=.02, ln=1.05, fx="sombra_dura", sombra="oscuro", desgaste=True,
                 color="acento", clave=dict(color="claro")),
    "diner": L("Diner Americano", "retro", "hamburguesas, malteadas, carteles clásicos", "Abril Fatface", ln=.95, fx="sombra_larga", sombra="primario",
               clave=dict(color="acento", fx="sombra_larga", sombra="oscuro")),
    "cartoon": L("Caricatura", "retro", "niños, juguetes, cumpleaños", "Titan One", ln=.95, fx="sticker", borde="oscuro", arco=.12,
                 clave=dict(color="acento", fx="sticker", borde="oscuro")),
    "comic": L("Cómic", "retro", "promos divertidas, snacks, eventos", "Luckiest Guy", may=True, ln=.95, fx="extrusion", sombra="oscuro", arco=.14,
               clave=dict(color="acento", fx="extrusion", sombra="oscuro")),
    "imprenta": L("Imprenta Vieja", "retro", "cervecerías artesanales, barberías, tabaco", "Bowlby One SC", may=True, tr=.02, ln=.95, fx="relieve",
                  desgaste=True, clave=dict(color="acento", fx="relieve")),
    # fiesta y tropical
    "fiesta-sticker": L("Fiesta Sticker", "fiesta", "comida caribeña, fiestas, cumpleaños", "Lilita One", ln=.95, fx="sticker", borde="oscuro", arco=.14,
                        clave=dict(color="acento", fx="sticker", borde="oscuro")),
    "verano": L("Verano", "fiesta", "bebidas, playa, heladerías", "Chewy", ln=1.0, fx="sombra_dura", sombra="primario",
                clave=dict(color="acento", fx="sombra_dura", sombra="oscuro")),
    "alegre": L("Alegre Redonda", "fiesta", "guarderías, apps, marcas amigables", "Fredoka", p=700, ln=.95, fx="sticker", borde="primario",
                clave=dict(color="acento", fx="sticker", borde="oscuro")),
    "calido-3d": L("Gordita 3D", "fiesta", "comida, postres, promos familiares", "Baloo 2", p=800, ln=.9, fx="extrusion", sombra="primario",
                   clave=dict(color="acento", fx="extrusion", sombra="oscuro")),
    "letrero-picante": L("Letrero Picante", "fiesta", "comida mexicana, salsas, ferias", "Bungee Spice", may=True, ln=.95, fx="fuente_color",
                         clave=dict()),
    "juguete-3d": L("Juguete 3D", "fiesta", "juguetes, gaming, eventos infantiles", "Nabla", may=True, ln=1.0, fx="fuente_color",
                    clave=dict()),
    "bocina": L("Bocina", "fiesta", "fiestas, discotecas, verbenas", "Honk", may=True, ln=1.0, fx="fuente_color",
                clave=dict()),
    # oscuro y terror
    "terror": L("Terror", "terror", "halloween, películas de miedo, escape rooms", "Creepster", may=True, tr=.02, ln=1.0, fx="neon", color="acento", brillo="acento",
                clave=dict(color="claro")),
    "sangre": L("Sangre", "terror", "terror extremo, eventos góticos", "Nosifer", may=True, ln=1.05, fx="color", color="acento",
                clave=dict(color="claro")),
    "gotico": L("Gótico", "terror", "metal, tatuajes, cervezas oscuras", "UnifrakturMaguntia", ln=1.0, fx="cromo",
                clave=dict(fx="oro")),
    "metal": L("Heavy Metal", "terror", "conciertos de rock y metal", "Metal Mania", may=True, ln=1.0, fx="cromo",
               clave=dict(fx="cromo")),
    "pirata": L("Pirata", "terror", "bares, ron, aventuras, juegos", "Pirata One", ln=1.0, fx="sombra_dura", sombra="oscuro", desgaste=True, color="claro",
                clave=dict(color="acento")),
    # tech y futurista
    "orbital": L("Orbital", "tech", "tecnología, IA, autos, gaming", "Orbitron", p=800, may=True, tr=.08, ln=1.0, fx="cromo",
                 clave=dict(fx="holo")),
    "galeria": L("Galería de Arte", "tech", "arte, agencias creativas, museos", "Syne", p=800, tr=-.03, ln=.92, fx="color",
                 clave=dict(fx="contorno", color="acento")),
    "expandida": L("Expandida", "tech", "startups, lanzamientos, apps", "Unbounded", p=800, may=True, tr=-.02, ln=.95, fx="color",
                   clave=dict(fx="holo")),
    "condensada": L("Condensada Gigante", "tech", "eventos, conferencias, anuncios fuertes", "Big Shoulders Display", p=900, may=True, tr=.02, ln=.85,
                    fx="color", clave=dict(color="oscuro", fx="resaltado", fondo="acento")),
    "codigo": L("Código", "tech", "programación, hackathons, ciberseguridad", "Space Mono", p=700, may=True, tr=-.02, ln=1.0, fx="glitch",
                clave=dict(color="acento")),
    "bricolage": L("Grotesca Moderna", "tech", "marcas modernas, SaaS, diseño", "Bricolage Grotesque", p=800, tr=-.04, ln=.9, fx="color",
                   clave=dict(color="oscuro", fx="resaltado", fondo="acento")),
    "deformada": L("Deformada", "tech", "música, festivales, marcas jóvenes", "Tilt Warp", may=True, ln=.95, fx="sombra_larga", sombra="acento",
                   clave=dict(color="acento", fx="sombra_larga", sombra="oscuro")),
    # deportivo y poster
    "veloz": L("Deportivo Veloz", "deporte", "gimnasios, torneos, carreras", "Barlow Condensed", p=900, it=True, may=True, tr=.01, ln=.88, fx="sombra_dura",
               sombra="acento", clave=dict(color="acento", fx="sombra_dura", sombra="oscuro")),
    "universitario": L("Universitario", "deporte", "equipos, colegios, ropa deportiva", "Graduate", may=True, tr=.02, ln=1.0, fx="doble_contorno",
                       color="claro", color2="acento", sombra="oscuro", clave=dict(color="acento", fx="doble_contorno", color2="claro", sombra="oscuro")),
    "estadio": L("Estadio", "deporte", "partidos, boxeo, lucha, eventos", "Staatliches", may=True, tr=.04, ln=.95, fx="doble_contorno",
                 color="claro", color2="primario", sombra="oscuro", clave=dict(color="acento")),
    "poster-oswald": L("Póster Clásico", "deporte", "anuncios, conferencias, política", "Oswald", p=700, may=True, tr=.02, ln=.92, fx="relieve",
                       clave=dict(color="acento", fx="relieve")),
    # hecho a mano
    "pizarra": L("Pizarra de Tiza", "mano", "menús, cafeterías, especiales del día", "Amatic SC", p=700, may=True, tr=.04, ln=1.0, fx="color", desgaste=True,
                 clave=dict(color="acento")),
    "pincel": L("Pincel Artesanal", "mano", "orgánicos, hecho a mano, mercados", "Caveat Brush", ln=1.0, fx="sombra_dura", sombra="oscuro",
                clave=dict(color="acento")),
    "nota-mano": L("Nota a Mano", "mano", "consejos, frases, posts cercanos", "Caveat", p=700, ln=.95, fx="color",
                   clave=dict(color="acento", fx="subrayado")),
}


def _rol(estilo, pal):
    for campo in ("color", "color2", "brillo", "sombra", "borde", "fondo"):
        if estilo.get(campo) in pal:
            estilo[campo] = pal[estilo[campo]]
    return estilo


def aplicar(kit, lid, pal):
    """Viste el titular del kit resuelto con la letra `lid`. El precio y el sticker conservan la fuente del kit."""
    le = LETRAS[lid]
    base = {"peso": 400, "mayus": False, "tracking": 0.0, "linea": 1.0, "efecto": "color", "color": "claro"}
    t = {**base, **{k2: le[k1] for k1, k2 in (("p", "peso"), ("may", "mayus"), ("tr", "tracking"), ("ln", "linea"), ("fx", "efecto"))
                    if k1 in le}}
    for k in ("color", "color2", "brillo", "sombra", "borde", "arco", "desgaste", "it"):
        if k in le:
            t[k] = le[k]
    c = le["clave"]
    clave = {"efecto": c.get("fx", t["efecto"]), "color": c.get("color", t["color"])}
    for k1, k2 in (("f", "fuente"), ("p", "peso"), ("may", "mayus"), ("tr", "tracking"), ("it", "it"), ("tam", "tam"), ("rot", "rot"),
                   ("color2", "color2"), ("brillo", "brillo"), ("sombra", "sombra"), ("borde", "borde"), ("fondo", "fondo")):
        if k1 in c:
            clave[k2] = c[k1]
    t["script"] = le["f"] in SCRIPT
    clave["script"] = clave.get("fuente", le["f"]) in SCRIPT
    if clave["script"]:
        clave["mayus"] = False
    kit["fuentes"] = {**kit["fuentes"], "precio": kit["fuentes"]["titulo"], "titulo": le["f"]}
    kit["titulo"], kit["clave"] = _rol(t, pal), _rol(clave, pal)
    kit["letra"] = {"id": lid, "nombre": le["nombre"]}
    return kit


def menu():
    """Lista corta por grupo para que el Director elija."""
    out = []
    for g, titulo in GRUPOS.items():
        out.append(f"{titulo}:")
        out += [f'  - "{k}": {v["nombre"]} ({v["para"]})' for k, v in LETRAS.items() if v["grupo"] == g]
    return "\n".join(out)


def variadas(excluir=(), n=3, primero=None):
    """n letras de grupos distintos (rotando), para que "probar letras" muestre variedad de verdad."""
    por_grupo = {g: [k for k, v in LETRAS.items() if v["grupo"] == g and k not in excluir] for g in GRUPOS}
    orden = sorted(GRUPOS, key=lambda g: g != primero)
    out = []
    while len(out) < n and any(por_grupo.values()):
        for g in orden:
            if por_grupo[g] and len(out) < n:
                out.append(por_grupo[g].pop(0))
    return out


def fuentes():
    """Familias usadas (titular + clave), para verificar que existan en Google Fonts."""
    return sorted({v["f"] for v in LETRAS.values()} | {v["clave"]["f"] for v in LETRAS.values() if "f" in v["clave"]})


if __name__ == "__main__":
    pal = {"primario": "#e11d2a", "acento": "#ffd400", "claro": "#ffffff", "oscuro": "#111111"}
    k = aplicar({"fuentes": {"titulo": "Anton", "cuerpo": "Archivo"}}, "gala-oro", dict(pal))
    assert k["fuentes"] == {"titulo": "Cinzel", "cuerpo": "Archivo", "precio": "Anton"}, k["fuentes"]
    assert k["titulo"]["efecto"] == "oro" and k["clave"]["fuente"] == "Great Vibes" and k["clave"]["tam"] == 1.45
    assert k["clave"]["script"] and not k["titulo"]["script"]
    assert aplicar({"fuentes": {"titulo": "Anton", "cuerpo": "Archivo"}}, "neon-letrero", dict(pal))["titulo"]["script"]
    k = aplicar({"fuentes": {"titulo": "Anton", "cuerpo": "Archivo"}}, "setentas", dict(pal))
    assert k["titulo"]["color"] == "#ffd400" and k["titulo"]["sombra"] == "#e11d2a" and k["clave"]["color2"] == "#ffd400"
    v = variadas()
    assert len(v) == 3 and len({LETRAS[x]["grupo"] for x in v}) == 3
    assert len(variadas(excluir=set(LETRAS))) == 0
    print(f"ok letras ({len(LETRAS)} estilos, {len(fuentes())} fuentes)")
