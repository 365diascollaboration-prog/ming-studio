"""Check del ciclo del agente sin llamar a OpenRouter: python test_agente.py"""
import json, os, tempfile
from pathlib import Path
from PIL import Image

tmp = Path(tempfile.mkdtemp())
os.environ["MING_DATOS"] = str(tmp / "datos")  # antes de importar: los tests nunca tocan los datos del usuario
import agente

agente.MEM = tmp / "memoria.json"
img = tmp / "a.png"
Image.new("RGB", (8, 8)).save(img)


def fake(respuesta):
    def chat(body):
        if not chat.llamadas:  # la primera llamada de cada encargo es la del Director (despues viene el corrector)
            fake.last = body
        chat.llamadas.append(body)
        return {"choices": [{"message": {"content": json.dumps(respuesta)}}]}
    chat.llamadas = []
    return chat


cap = {"canvas_settings": {}, "layers": []}
p, plan, _ = agente.crear_prompt(fake({"plan": "ok", "caption": cap}), "musica", "single \"Fuego\"", True)
assert p.startswith(agente.RGBA) and plan == "ok"
assert "Portada de música" in fake.last["messages"][0]["content"]
assert fake.last["reasoning"] == {"enabled": False}  # modo rapido activo

agente.registrar("a.png", "musica", "single", p)
c = agente.criticar(fake({"puntaje": 9, "problemas": [], "leccion": "Titulo en 20% del alto"}), img, "a.png")
assert c["puntaje"] == 9
agente.calificar(fake({"leccion": "Evitar fondos planos"}), "a.png", -1, "muy plano")

m = agente.cargar()
assert m["lecciones"]["musica"] == ["Titulo en 20% del alto", "Evitar fondos planos"]
# la siguiente vez, las lecciones y el buen ejemplo (puntaje 9) entran al system prompt
sp = agente.system_prompt("musica", m)
assert "Evitar fondos planos" in sp and "Ejemplo que funciono bien" in sp

# formato elegido pisa lo que diga el Director, y el estilo llega en el mensaje
p, _, _ = agente.crear_prompt(fake({"plan": "", "caption": {"canvas_settings": {"aspect_ratio": "1:1"}, "layers": []}}),
                           "cartel", "valla", False, formato="16:9", estilo="bold")
assert json.loads(p)["canvas_settings"]["aspect_ratio"] == "16:9"
assert "Bold:" in fake.last["messages"][1]["content"]

# corregir usa los defectos de la critica y conserva el RGBA
p2, _, _ = agente.corregir(fake({"plan": "corregido", "caption": cap}), "a.png")
assert p2.startswith(agente.RGBA) and "Defectos observados" in fake.last["messages"][1]["content"]

# capas: formato oficial "Decompose ... Layer N:"
cp = agente.capas_prompt(fake({"layers": ["Headline text", "Photo", "Red background"]}), "data:image/png;base64,x", 3)
assert cp.startswith("Decompose this image into 3 layers") and "\nLayer 3: Red background" in cp
print("ok")

# kit de marca: entra al encargo del Director y queda en el historial
import marcas
marcas.ARCHIVO = tmp / "marcas.json"
mid = marcas.guardar({"nombre": "Mercado Caribe", "colores": ["#0f8b8d"], "tono": "alegre y familiar"})
agente.crear_prompt(fake({"plan": "", "caption": cap}), "flyer", "2x1", False, marca=mid)
assert "KIT DE MARCA" in fake.last["messages"][1]["content"] and "#0f8b8d" in fake.last["messages"][1]["content"]
agente.registrar("b.png", "flyer", "2x1", "{}", mid)
assert agente._entrada(agente.cargar(), "b.png")["marca"] == mid
print("ok marcas")

# motor hibrido: textos validados, fuera del arte, y zona reservada en el caption aunque el Director la olvide
import motor
motor.COMP = tmp
hib_cap = {"canvas_settings": {}, "layers": [{"description": "Headline reads \"PLAN PRO\" and price \"$200\"", "coordinates": "cx: 0.500, cy: 0.100, w: 0.800, h: 0.100"}]}
p3, _, extra = agente.crear_prompt(fake({"plan": "", "caption": hib_cap, "fuentes": {"titulo": "Anton", "cuerpo": "x;evil"},
    "textos": [{"rol": "precio", "texto": "$200", "zona": "cx: 0.5, cy: 0.5, w: 0.4, h: 0.1", "color": "#fff"},
               {"rol": "lista", "texto": "a\\nb", "zona": "basura"}]}), "flyer", "plan", False, hibrido=True)
assert [t["rol"] for t in extra["textos"]] == ["precio"]          # la zona invalida se descarta
assert extra["fuentes"] == {"titulo": "Anton", "cuerpo": "Inter"}  # familia sospechosa -> respaldo
assert "$200" not in p3 and "PLAN PRO" in p3                       # el precio sale del arte, el titular queda
assert "cx: 0.500, cy: 0.500, w: 0.400, h: 0.100" in p3             # zona reservada agregada
assert "motor hibrido" in fake.last["messages"][0]["content"].lower()
print("ok hibrido")

# planificador: si el texto choca con el sujeto, maqueta sin cruces (texto vs sujeto, texto vs texto, logo)
cap_c = {"layers": [{"description": "bg", "coordinates": "cx: 0.5, cy: 0.5, w: 1, h: 1"},
                    {"description": "robot", "coordinates": "cx: 0.5, cy: 0.45, w: 0.6, h: 0.5"}]}
tx, _ = motor.normalizar([
    {"rol": "logo", "zona": "cx: 0.1, cy: 0.1, w: 0.2, h: 0.1"},
    {"rol": "titulo", "texto": "T", "zona": "cx: 0.5, cy: 0.18, w: 0.8, h: 0.15"},
    {"rol": "precio", "texto": "$1", "zona": "cx: 0.5, cy: 0.42, w: 0.6, h: 0.1"},
    {"rol": "lista", "texto": "a\nb", "zona": "cx: 0.5, cy: 0.58, w: 0.7, h: 0.15"},
    {"rol": "contacto", "texto": "c", "zona": "cx: 0.5, cy: 0.92, w: 0.8, h: 0.08"}], {})
assert motor.planificar(cap_c, tx)
rob = motor.parse_zona(cap_c["layers"][1]["coordinates"])
cajas = [t["zona"] for t in tx]
assert not any(motor._choca(z, rob, 0) for z in cajas[1:]), "texto encima del sujeto"
assert not any(motor._choca(a, b, 0) for i, a in enumerate(cajas) for b in cajas[i + 1:]), "textos encimados"
assert [t["rol"] for t in sorted(tx[1:], key=lambda t: t["zona"]["cy"])] == ["titulo", "precio", "lista", "contacto"]  # orden de lectura
print("ok planificador")

# croma: quita el fondo atrapado en huecos, respeta zonas oscuras del sujeto, y no toca fondos que no son croma
import numpy as np
from PIL import ImageDraw
im = Image.new('RGB', (200, 200), (0, 255, 0)); dr = ImageDraw.Draw(im)
dr.ellipse([40, 30, 160, 180], fill=(240, 240, 245)); dr.ellipse([85, 90, 115, 120], fill=(0, 250, 5)); dr.rectangle([75, 130, 125, 165], fill=(20, 22, 30))
o = np.asarray(motor._croma(im.convert('RGBA'), im))
assert o[105, 100, 3] == 0 and o[147, 100, 3] == 255 and o[60, 100, 3] == 255
plano = Image.new('RGB', (50, 50), (40, 30, 35))
assert np.array_equal(np.asarray(motor._croma(plano.convert('RGBA'), plano)), np.asarray(plano.convert('RGBA')))
print("ok croma")

# el titular nunca se compacta cuando el planificador hace espacio para el heroe
cap_t = {"layers": [{"description": "robot", "coordinates": "cx: 0.5, cy: 0.5, w: 0.6, h: 0.6"}]}
tx2, _ = motor.normalizar([{"rol": "titulo", "texto": "T", "zona": "cx: 0.5, cy: 0.3, w: 0.9, h: 0.14"},
                           {"rol": "lista", "texto": "a\nb\nc", "zona": "cx: 0.5, cy: 0.6, w: 0.7, h: 0.32"},
                           {"rol": "contacto", "texto": "c", "zona": "cx: 0.5, cy: 0.9, w: 0.6, h: 0.05"}], {})
motor.planificar(cap_t, tx2)
assert tx2[0]["zona"]["h"] == 0.14 and tx2[1]["zona"]["h"] < 0.32  # se compacta la lista, no el titular
print("ok titular")

# kits: marcas de palabra clave validas solo en titulares; sticker es un rol; la paleta sale de la marca
import kits
tk, _ = motor.normalizar([{"rol": "titulo", "texto": "Vende *mientras duermes*", "zona": "cx: .5, cy: .2, w: .8, h: .1"},
                          {"rol": "titulo", "texto": "Roto *mal", "zona": "cx: .5, cy: .4, w: .8, h: .1"},
                          {"rol": "lista", "texto": "*a*\nb", "zona": "cx: .5, cy: .6, w: .8, h: .1"},
                          {"rol": "sticker", "texto": "NUEVO", "zona": "cx: .8, cy: .8, w: .15, h: .1"}], {})
assert [t["texto"] for t in tk] == ["Vende *mientras duermes*", "Roto *mal*", "a\nb", "NUEVO"] and tk[3]["rol"] == "sticker"
k365 = kits.resolver("tech", ["#76c0fc", "#3ebfff", "#97e1fe", "#842915", "#f57905", "#050505"])
assert k365["paleta"]["acento"] == "#f57905" and k365["cta"]["color"] == k365["paleta"]["primario"]
print("ok kits")

# el Director se salta el fondo una vez: se le vuelve a pedir y sale bien
_resp = iter([{"plan": "x"}, {"plan": "y", "fondo": json.dumps({"canvas_settings": {}, "layers": [{"description": "bg", "coordinates": "cx: .5, cy: .5, w: 1, h: 1"}]}), "textos": [], "kit": "neon"}])
r = agente.director_v2(lambda b: {"choices": [{"message": {"content": json.dumps(next(_resp))}}]}, "flyer", "idea")
assert r["hibrido"]["kit"]["id"] == "neon" and json.loads(r["prompt"])["layers"]
print("ok reintento director")

# palabra clave automatica y logo que nunca pisa al titular
assert motor.marcar_clave("Automatiza tu negocio con Agentes de IA") == "Automatiza tu negocio con Agentes de *IA*"
assert motor.marcar_clave("NOCHE BORICUA") == "NOCHE *BORICUA*"
assert motor.marcar_clave("Hola") == "Hola"
Image.new('RGB', (300, 400), (5, 5, 20)).save(tmp / 'plano.png')
tl, _ = motor.normalizar([{"rol": "logo", "zona": "cx: 0.5, cy: 0.06, w: 0.15, h: 0.08"},
                          {"rol": "titulo", "texto": "Titular largo de prueba", "zona": "cx: 0.5, cy: 0.1, w: 0.9, h: 0.12"}], {})
tl, _ = motor.acomodar(tmp / 'plano.png', tl)
assert not motor._choca(tl[0]["zona"], tl[1]["zona"], 0), (tl[0]["zona"], tl[1]["zona"])
assert tl[0]["zona"]["cx"] < 0.2 or tl[0]["zona"]["cx"] > 0.8  # el logo se fue a una esquina
print("ok logo y clave")

# el heroe llena el hueco libre mas grande entre textos
th, _ = motor.normalizar([{"rol": "titulo", "texto": "T", "zona": "cx: .5, cy: .15, w: .8, h: .12"},
                          {"rol": "contacto", "texto": "c", "zona": "cx: .5, cy: .92, w: .6, h: .05"}], {})
zh = motor.heroe_en_hueco(th, {"cx": 0.5, "cy": 0.6, "w": 0.3, "h": 0.2})
assert zh["h"] > 0.55 and zh["cy"] - zh["h"] / 2 > 0.21 and zh["cy"] + zh["h"] / 2 < 0.895, zh
print("ok heroe")

# croma: si rembg se comio parte clara del sujeto (borde de plato), la llave la devuelve
im2 = Image.new('RGB', (200, 200), (0, 255, 0)); ImageDraw.Draw(im2).ellipse([30, 60, 170, 150], fill=(245, 245, 240))
comido = im2.convert('RGBA'); px = comido.load()
for x in range(120, 170):
    for y in range(60, 150): px[x, y] = px[x, y][:3] + (0,)  # rembg borro el borde derecho
o2 = np.asarray(motor._croma(comido, im2))
assert o2[105, 150, 3] == 255 and o2[5, 5, 3] == 0
print("ok croma devuelve")

# croma forzado por codigo: magenta por defecto, verde si el sujeto es rosado; y el recorte magenta funciona
pm = json.loads(agente.forzar_croma(json.dumps({"canvas_settings": {}, "layers": [{"description": "mofongo with parsley"}]})))
pv = json.loads(agente.forzar_croma(json.dumps({"canvas_settings": {}, "layers": [{"description": "pink perfume bottle"}]})))
assert "#FF00FF" in pm["canvas_settings"]["image_style"] and "#00FF00" in pv["canvas_settings"]["image_style"]
assert pm["layers"][0]["color_specs"] == ["#FF00FF"] and pm["layers"][0]["coordinates"].startswith("cx: 0.500, cy: 0.500, w: 1.000")
im3 = Image.new('RGB', (200, 200), (255, 0, 255)); dr3 = ImageDraw.Draw(im3)
dr3.ellipse([40, 40, 160, 160], fill=(30, 140, 40)); dr3.rectangle([90, 90, 110, 110], fill=(40, 25, 20))  # perejil + salsa oscura
o3 = np.asarray(motor._croma(im3.convert('RGBA'), im3))
assert o3[60, 100, 3] == 255 and o3[100, 100, 3] == 255 and o3[5, 5, 3] == 0
print("ok croma magenta")

# recorte sobre fondo plano (no croma): devuelve el borde claro que rembg se comio CON su color original,
# pela la sombra proyectada pegada y rellena huecos de sujeto (salsa oscura) pero no huecos de fondo
bg = (45, 35, 41)
im4 = Image.new('RGB', (300, 300), bg); d4 = ImageDraw.Draw(im4)
d4.ellipse([40, 200, 260, 250], fill=(8, 8, 8))            # sombra proyectada bajo el plato
d4.ellipse([30, 60, 270, 220], fill=(235, 232, 225))        # plato blanco
d4.ellipse([100, 100, 200, 180], fill=(150, 110, 40))       # comida
d4.ellipse([140, 130, 160, 150], fill=(90, 60, 10))         # salsa oscura (hueco de sujeto)
d4.ellipse([60, 120, 75, 135], fill=bg)                     # hueco de fondo real dentro del plato
r4 = im4.convert('RGBA'); p4 = r4.load()
for x in range(300):
    for y in range(300):
        c = p4[x, y]
        comido = x > 262 and 60 < y < 220                   # rembg se comio el filo derecho del plato
        es_fondo = c[:3] == bg or (c[:3] == (8, 8, 8) and False)
        salsa = c[:3] == (90, 60, 10)
        p4[x, y] = ((0, 0, 0, 0) if (es_fondo or comido or salsa) else c)
for x in range(40, 261):                                    # rembg dejo pegada la sombra
    for y in range(221, 250):
        if im4.getpixel((x, y)) == (8, 8, 8): p4[x, y] = (8, 8, 8, 255)
o4 = np.asarray(motor._refinar(r4, im4))
assert o4[140, 266, 3] > 200 and o4[140, 266, 0] > 200     # filo del plato vuelve, blanco (no negro)
assert o4[240, 150, 3] < 30                                 # sombra pelada
assert o4[140, 150, 3] > 200                                # salsa rellena
assert o4[127, 67, 3] < 60                                  # hueco de fondo real sigue transparente
print("ok recorte refinado")

# reticulas: los 5 layouts dejan todo dentro del lienzo, ningun texto (salvo el titular "detras") pisa al sujeto,
# y se puede saltar entre layouts sin perder el plano original ni lo editado a mano
Image.new('RGB', (400, 500), (240, 240, 240)).save(motor.BASE / '_test-ret.png')
Image.new('RGBA', (200, 300), (200, 50, 50, 255)).save(motor.BASE / '_test-ret-sujeto.png')
tr, _ = motor.normalizar([{"rol": "logo", "zona": "cx: .1, cy: .05, w: .12, h: .08"},
                          {"rol": "titulo", "texto": "Gran oferta de martes", "zona": "cx: .5, cy: .1, w: .9, h: .12"},
                          {"rol": "subtitulo", "texto": "Solo hoy", "zona": "cx: .5, cy: .2, w: .8, h: .05"},
                          {"rol": "lista", "texto": "uno\ndos\ntres", "zona": "cx: .5, cy: .7, w: .8, h: .12"},
                          {"rol": "precio", "texto": "$9.99", "zona": "cx: .5, cy: .8, w: .5, h: .1"},
                          {"rol": "cta", "texto": "Pide ya", "zona": "cx: .5, cy: .9, w: .4, h: .05"}], {})
dr = {"base": "salidas/base/_test-ret.png", "w": 400, "h": 500, "textos": tr, "paneles": [], "v": 2,
      "sujeto": {"src": "salidas/base/_test-ret-sujeto.png", "zona": {"cx": .5, "cy": .5, "w": .4, "h": .3}}}
for rid in motor.RETICULAS:
    x = motor.reticula(dr, rid)
    sz = x["sujeto"]["zona"]
    for t in x["textos"]:
        z = t["zona"]
        assert 0 <= z["cy"] - z["h"] / 2 and z["cy"] + z["h"] / 2 <= 1.001 and 0 <= z["cx"] - z["w"] / 2, (rid, t["rol"], z)
        if t["rol"] not in ("sticker",) and not (x["titular_detras"] and t["rol"] == "titulo"):
            assert not motor._choca(z, sz, 0), (rid, t["rol"], z, sz)
    x["textos"][1]["texto"] = "Editado"
    y = motor.reticula(x, "dividido")  # desde otra reticula: parte del original y conserva la edicion
    assert y["orig"]["textos"][1]["zona"] == tr[1]["zona"] and y["textos"][1]["texto"] == "Editado"
for f in ("_test-ret.png", "_test-ret-sujeto.png"):
    (motor.BASE / f).unlink()
print("ok reticulas")

# miniaturas de galeria: JPG chico, en cache, y se rehace si el PNG cambia
import io, os, server
src, dst = server.OUT / "_test-mini.png", server.MINI / "_test-mini.jpg"
Image.new("RGBA", (2000, 1000), (255, 0, 0, 128)).save(src)
assert Image.open(io.BytesIO(server.mini(src.name))).size == (480, 240)
os.utime(dst, (1, 1))  # miniatura "vieja" -> se rehace
Image.new("RGB", (1000, 4000)).save(src)
assert Image.open(io.BytesIO(server.mini(src.name))).size == (120, 480)
t = dst.stat().st_mtime
server.mini(src.name)
assert dst.stat().st_mtime == t  # sin cambios usa la cache
src.unlink(); dst.unlink()
print("ok miniaturas")

# letras: el titular se viste con el estilo elegido y el precio conserva la fuente del kit
import letras
k = kits.resolver("impacto", ["#b20101", "#e5b26c"], None, "gala-oro")
assert k["fuentes"]["titulo"] == "Cinzel" and k["fuentes"]["precio"] == "Anton" and k["clave"]["fuente"] == "Great Vibes"
assert k["clave"]["script"] and k["clave"]["mayus"] is False and k["titulo"]["efecto"] == "oro"
assert all(v["f"] for v in letras.LETRAS.values()) and len(letras.LETRAS) >= 60
assert "gala-oro" in letras.menu() and len(set(letras.LETRAS[x]["grupo"] for x in letras.variadas())) == 3
assert "letra" not in kits.resolver("impacto")
print("ok letras")

# paso 3: lettering de Ming. Ortografia exacta (tildes cuentan), solo titulares cortos, croma aunque el sujeto toque bordes
assert agente.titular_correcto("2X1 Los Martes", "2x1 LOS *MARTES*".replace("*", "")) and not agente.titular_correcto("Dias", "Días")
assert not agente.titular_correcto("NOCHE DE SALZA", "NOCHE DE SALSA")
assert agente.titular_corto("NOCHE DE *SALSA*") and not agente.titular_corto("Tu Nueva Web con Agente de IA que *Vende 24/7*")
assert agente._croma_para(["#b20101", "#e5b26c"]) == "magenta" and agente._croma_para(["#ff33cc"]) == "verde"
lt = agente.lettering_ming({"texto": "NOCHE DE *SALSA*", "zona": {"cx": .5, "cy": .2, "w": .8, "h": .12}},
                           kits.resolver("tropical", ["#b20101", "#e5b26c"], None, "neon-letrero"), "brush script", "3:4")
assert lt["esperado"] == "NOCHE DE SALSA" and '"SALSA"' in json.loads(lt["caption"])["layers"][1]["description"]
ar = np.zeros((200, 200, 3), np.uint8); ar[:] = (255, 0, 255); ar[60:, 20:] = (150, 110, 60)  # plato que se sale por abajo y la derecha
rc = motor._croma(None, Image.fromarray(ar))
assert rc is not None and rc.getpixel((100, 150))[3] == 255 and rc.getpixel((5, 5))[3] == 0
assert motor._croma(None, Image.new("RGB", (100, 100), (30, 40, 50))) is None  # foto normal: no es croma
print("ok lettering")

# biblioteca: piezas copiadas por marca, sin duplicar, lo viejo entra a "revisar", el Director solo llena lo vacio
import biblioteca
biblioteca.BIB = tmp / "bib"; biblioteca.INDICE = biblioteca.BIB / "biblioteca.json"; biblioteca.MINI = biblioteca.BIB / "mini"
bb, bc = motor.BASE, motor.COMP
motor.BASE, motor.COMP = tmp / "base", tmp / "comp"
motor.BASE.mkdir(); motor.COMP.mkdir()
Image.new("RGB", (900, 1200), (20, 60, 30)).save(motor.BASE / "d1.png")
Image.new("RGBA", (300, 200), (200, 150, 50, 255)).save(motor.BASE / "d1-sujeto.png")
(motor.COMP / "d1.json").write_text("{}"); (motor.COMP / "d1.export.json").write_text("{}")
Image.new("RGB", (900, 1200)).save(motor.BASE / "d2.png")  # sin comp: no es hibrido, no se importa
assert set(biblioteca.de_diseno("d1")) == {"fondo", "sujeto"} and biblioteca.de_diseno("d2") == {}
assert biblioteca.importar(lambda s: "mercado-caribe") == 2 and biblioteca.importar(lambda s: "x") == 0
ps = biblioteca.listar()
assert all(p["estado"] == "revisar" and p["marca"] == "mercado-caribe" for p in ps)
suj = next(p for p in ps if p["tipo"] == "sujeto")
assert Image.open(biblioteca.BIB / f"{suj['id']}.png").mode == "RGBA" and Image.open(biblioteca.MINI / f"{next(p for p in ps if p['tipo'] == 'fondo')['id']}.png").size == (270, 360)
assert biblioteca.agregar(motor.BASE / "d1-sujeto.png", "sujeto", "", "ok", "diseno:d1")["id"] == suj["id"]  # mismo origen: no duplica
biblioteca.editar(suj["id"], {"nombre": "Mofongo", "etiquetas": "Tropical, , noche", "estado": "ok", "tipo": "nada"})
p = biblioteca.ficha(fake({"nombre": "Otro nombre", "etiquetas": ["x"]}), suj["id"])
assert p["nombre"] == "Mofongo" and p["etiquetas"] == ["tropical", "noche"] and p["tipo"] == "sujeto" and p["estado"] == "ok"
fon = next(p for p in ps if p["tipo"] == "fondo")
assert biblioteca.ficha(fake({"nombre": "Selva de noche", "etiquetas": ["Noche", "selva"]}), fon["id"])["etiquetas"] == ["noche", "selva"]
assert "image_url" in json.dumps(fake.last["messages"][1])
(motor.BASE / "d1.png").unlink()  # borrar el diseno no toca la copia de la biblioteca
assert (biblioteca.BIB / f"{fon['id']}.png").is_file()
biblioteca.borrar(fon["id"])
assert not (biblioteca.BIB / f"{fon['id']}.png").is_file() and len(biblioteca.listar()) == 1
motor.BASE, motor.COMP = bb, bc
print("ok biblioteca")

# paso 2: el Director mezcla. Catalogo solo aprobado y de la marca; fondos sin repetir y del formato; ids inventados fuera
f45 = biblioteca.agregar(Image.new("RGB", (800, 1000)), "fondo", "mercado-caribe", "ok", nombre="Selva noche", etiquetas=["noche"])
f916 = biblioteca.agregar(Image.new("RGB", (900, 1600)), "fondo", "mercado-caribe", "ok", nombre="Playa")
lim = biblioteca.agregar(Image.new("RGBA", (100, 100), (0, 200, 0, 255)), "objeto", "mercado-caribe", "ok", nombre="Limones")
biblioteca.agregar(Image.new("RGB", (800, 1000)), "fondo", "mercado-caribe", "revisar")
biblioteca.agregar(Image.new("RGB", (800, 1000)), "fondo", "otra", "ok")
cat_ = biblioteca.catalogo("mercado-caribe", "auto", [])
assert set(cat_["piezas"]) == {suj["id"], f45["id"], f916["id"], lim["id"]} and "formato 4:5" in cat_["texto"]
assert set(biblioteca.catalogo("mercado-caribe", "9:16", [])["piezas"]) == {suj["id"], f916["id"], lim["id"]}
biblioteca.usar([f45["id"]], "d9")
assert f45["id"] not in biblioteca.catalogo("mercado-caribe", "auto", ["d9"])["piezas"]  # usado hace poco: no se ofrece
assert biblioteca.catalogo("", "auto", [])["piezas"] == {}
assert biblioteca.pieza(f45["id"], "fondo", "mercado-caribe") and not biblioteca.pieza(f45["id"], "fondo", "otra") and not biblioteca.pieza("inventado", "fondo", "mercado-caribe")
e = agente._eleccion({"sujeto": f45["id"], "fondo": f916["id"], "objetos": [{"id": lim["id"], "zona": "cx: 0.9, cy: 0.9, w: 0.1, h: 0.1"}] * 3,
                      "motivo": "Noche de playa"}, cat_, "mofongo")
assert e["sujeto"] is None and e["fondo"] == f916["id"] and len(e["objetos"]) == 2 and '"Playa"' in e["motivo"]  # tipo equivocado fuera
assert agente._eleccion({"sujeto": suj["id"]}, cat_, "quiero un PLATO NUEVO de mofongo") is None
assert agente._eleccion({"sujeto": "x1"}, cat_, "") is None and agente._eleccion({"sujeto": suj["id"]}, None, "") is None
plano = {"plan": "ok", "fondo": {"canvas_settings": {}, "layers": [{"description": "jungle", "coordinates": "cx: 0.5, cy: 0.5, w: 1, h: 1"}]},
         "sujeto": None, "sujeto_zona": "cx: 0.5, cy: 0.6, w: 0.5, h: 0.4",
         "textos": [{"rol": "titulo", "texto": "Sabor *criollo*", "zona": "cx: 0.5, cy: 0.12, w: 0.8, h: 0.1"}],
         "biblioteca": {"sujeto": suj["id"], "fondo": f916["id"], "objetos": [], "motivo": "Tu mofongo de siempre."}}
r = agente.director_v2(fake(plano), "flyer", "mofongo", marca="mercado-caribe", lettering=False, biblio=cat_)
assert "BIBLIOTECA DE LA MARCA" in fake.last["messages"][1]["content"] and "BIBLIOTECA:" in fake.last["messages"][0]["content"]
hb = r["hibrido"]
assert hb["biblioteca"]["sujeto"] == suj["id"] and hb["sujeto"] is None and hb["sujeto_zona"]  # sujeto reusado: hay zona aunque no haya caption
assert json.loads(r["prompt"])["canvas_settings"]["aspect_ratio"] == "9:16" and r["plan"].startswith("♻ De tu biblioteca")
r = agente.director_v2(fake(plano), "flyer", "mofongo", marca="mercado-caribe", lettering=False)  # sin biblioteca: igual que antes
assert r["hibrido"]["biblioteca"] is None and "BIBLIOTECA:" not in fake.last["messages"][0]["content"]
ob = [{"zona": {"cx": .5, "cy": .12, "w": .1, "h": .1}}, {"zona": {"cx": .9, "cy": .9, "w": .1, "h": .1}}]
assert motor.objetos_libres(ob, [{"zona": {"cx": .5, "cy": .12, "w": .8, "h": .1}}]) == ob[1:]  # el que tapa texto se quita
print("ok mezcla")

# paso 3: series. Se congela la cara de un diseno; el Director solo pone contenido nuevo en los mismos roles
import series
series.ARCHIVO = tmp / "series.json"
bb, bc = motor.BASE, motor.COMP
motor.BASE, motor.COMP = tmp / "base", tmp / "comp"
Image.new("RGB", (800, 1000), (30, 10, 10)).save(motor.BASE / "s1.png")
kit_s = kits.resolver("impacto", ["#b20101"], None, "gala-oro")
motor.guardar("s1", {"base": "salidas/base/s1.png", "w": 800, "h": 1000, "kit": kit_s, "titular_detras": False,
                     "sujeto": {"src": "x", "zona": {"cx": .5, "cy": .6, "w": .5, "h": .3}},
                     "prompts": {"fondo": '{"canvas_settings": {"image_style": "warm salsa night"}}', "sujeto_zona": {"cx": .5, "cy": .6, "w": .6, "h": .4}},
                     "textos": [{"rol": "titulo", "texto": "Noche de *Salsa*", "zona": {"cx": .5, "cy": .12, "w": .8, "h": .1}, "alinear": "left",
                                 "color": "#ffcc00", "fuente": "titulo", "peso": 900, "mayusculas": True, "fondo": "", "vinieta": "", "panel": True, "arte": "x.png"},
                                {"rol": "precio", "texto": "$12", "zona": {"cx": .8, "cy": .85, "w": .2, "h": .1}, "alinear": "center",
                                 "color": "#ffffff", "fuente": "titulo", "peso": 800, "mayusculas": False, "fondo": "", "vinieta": ""},
                                {"rol": "logo", "texto": "", "zona": {"cx": .1, "cy": .95, "w": .12, "h": .06}}]})
sid = series.crear("s1", "Viernes de Salsa", "mercado-caribe", fondo_fijo=True)
s = series.obtener(sid, "mercado-caribe")
assert s["formato"] == "4:5" and s["kit"]["letra"]["id"] == "gala-oro" and s["sujeto_zona"] == {"cx": .5, "cy": .6, "w": .6, "h": .4}
assert biblioteca.pieza(s["fondo"], "fondo", "mercado-caribe") and "arte" not in s["textos"][0] and "panel" not in s["textos"][0]
assert series.obtener(sid, "otra") is None and series.obtener("nada", "mercado-caribe") is None
try:
    series.crear("s1", "  ", "mercado-caribe"); assert False
except ValueError:
    pass
nuevo = {"plan": "Mofongo de la semana", "fondo": plano["fondo"], "sujeto": {"canvas_settings": {}, "layers": [{"description": "mofongo"}]},
         "sujeto_zona": "cx: 0.2, cy: 0.2, w: 0.2, h: 0.2", "kit": "neon", "titular_detras": True,
         "textos": [{"rol": "precio", "texto": "$15"},
                    {"rol": "titulo", "texto": "Mofongo *Bravo*", "zona": "cx: 0.5, cy: 0.5, w: 0.3, h: 0.1"},
                    {"rol": "cta", "texto": "Reserva", "zona": "cx: 0.5, cy: 0.9, w: 0.3, h: 0.05"}, {"rol": "logo", "texto": "MC"}]}
r = agente.director_v2(fake(nuevo), "flyer", "mofongo esta semana", "16:9", marca="mercado-caribe", lettering=True, serie=s)
hb = r["hibrido"]
assert 'SERIE "Viernes de Salsa"' in fake.last["messages"][1]["content"] and "titulo, precio" in fake.last["messages"][1]["content"]
assert [t["rol"] for t in hb["textos"]] == ["titulo", "precio", "texto"]  # orden y roles de la serie; el cta extra se descarta
assert hb["textos"][2]["texto"] == "Mercado Caribe"  # marca sin logo cargado: su nombre pasa a texto, no se pierde
tit = hb["textos"][0]
assert tit["texto"] == "Mofongo *Bravo*" and tit["zona"] == {"cx": .5, "cy": .12, "w": .8, "h": .1} and tit["color"] == "#ffcc00" and tit["alinear"] == "left"
assert hb["textos"][1]["texto"] == "$15" and hb["textos"][1]["zona"]["cx"] == .8
assert hb["kit"]["id"] == "impacto" and hb["lettering"] is None and hb["titular_detras"] is False  # kit de la serie, sin lettering de Ming
assert hb["sujeto_zona"] == {"cx": .5, "cy": .6, "w": .6, "h": .4} and hb["biblioteca"]["fondo"] == s["fondo"]
assert json.loads(r["prompt"])["canvas_settings"]["aspect_ratio"] == "4:5" and r["plan"].startswith("📌 Serie")  # el 16:9 pedido no rompe la serie
series.borrar(sid)
assert series.listar() == {}
motor.BASE, motor.COMP = bb, bc
print("ok series")

# seguridad: solo se sirven paginas e imagenes; ids de biblioteca con ruta trampa se rechazan
import server
ok_pub = ["/", "/index.html", "/lienzo.html", "/salidas/a-01.png", "/salidas/base/a-sujeto.png", "/marcas_logos/x.png", "/biblioteca/mini/1.png"]
no_pub = ["/memoria.json", "/server.log", "/.git/config", "/agente.py", "/marcas.json", "/salidas/comp/a.json", "/biblioteca/biblioteca.json", "/.env", "/salidas/a.png.py"]
assert all(server.PUBLICO.match(p) for p in ok_pub) and not any(server.PUBLICO.match(p) for p in no_pub)
for malo in ("../salidas/x", "20261002085829-72186a/../../x", ""):
    try:
        biblioteca.borrar(malo); assert False
    except KeyError:
        pass
print("ok seguridad")

# reglas por codigo (prueba de producto 02/10): comillas del cliente, nombre de marca, formato de Ming, sello y caja
t = agente.respetar_comillas([{"rol": "titulo", "texto": "FUEGO *BORIQUA*"}], 'Salsa "Fuego Boricua" sobre madera')
assert t[0]["texto"].replace("*", "") == "FUEGO BORICUA"
import server, io as _io
big = _io.BytesIO(); Image.new("RGB", (1600, 900)).save(big, "PNG")
png, ok = server._al_formato(big.getvalue(), 9 / 16, False)
assert not ok
png, ok = server._al_formato(big.getvalue(), 9 / 16, True)
assert ok and abs(Image.open(_io.BytesIO(png)).size[0] / 900 - 9 / 16) < 0.01
z = motor.con_margen({"cx": 0.275, "cy": 0.5, "w": 0.55, "h": 0.1})
assert z["cx"] - z["w"] / 2 >= motor.MARGEN - 1e-9
Image.new("RGB", (400, 500), (20, 20, 20)).save(tmp / "liso.png")
ts = [{"rol": "titulo", "texto": "A", "zona": {"cx": 0.3, "cy": 0.15, "w": 0.5, "h": 0.2}},
      {"rol": "sticker", "texto": "NUEVO", "zona": {"cx": 0.2, "cy": 0.12, "w": 0.15, "h": 0.1}},
      {"rol": "subtitulo", "texto": "B", "zona": {"cx": 0.5, "cy": 0.95, "w": 0.6, "h": 0.1}}]
ts, _ = motor.acomodar(tmp / "liso.png", ts)
assert not motor._choca(ts[0]["zona"], ts[1]["zona"])  # el sello ya no tapa el titular
assert ts[2]["zona"]["h"] <= 0.1 + 1e-9  # sin lugar abajo se achica, nunca se agranda
print("ok reglas producto")

# un menu en fila no se apila en escalera; lo que va en la misma columna si se apila
fila = [{"rol": "texto", "texto": x, "zona": {"cx": cx, "cy": 0.06, "w": 0.12, "h": 0.04}} for x, cx in (("Inicio", 0.5), ("Precios", 0.65), ("Contacto", 0.8))]
fila += [{"rol": "titulo", "texto": "T", "zona": {"cx": 0.5, "cy": 0.07, "w": 0.8, "h": 0.1}}]
fila, _ = motor.acomodar(tmp / "liso.png", fila)
assert len({round(t["zona"]["cy"], 3) for t in fila[:3]}) == 1  # misma fila
assert fila[3]["zona"]["cy"] - fila[3]["zona"]["h"] / 2 >= fila[0]["zona"]["cy"] + fila[0]["zona"]["h"] / 2  # el titulo, debajo
print("ok menu en fila")

# corrector de ortografia con candado: tildes si; cambiar palabras o tocar comillas del cliente, no
c = fake({"textos": ["Nací en la calle", "Otra frase totalmente distinta aquí"]})
t = agente.ortografia(c, [{"rol": "titulo", "texto": "Naci en la calle"}, {"rol": "subtitulo", "texto": "Pidelo ya"},
                          {"rol": "cta", "texto": "Fuego Boriqua"}], 'Salsa "Fuego Boriqua"')
assert [x["texto"] for x in t] == ["Nací en la calle", "Pidelo ya", "Fuego Boriqua"]
print("ok ortografia")

# red: un corte pasajero se reintenta (3 intentos); una key mala (401) falla de una
import urllib.error, urllib.request as _ur
_llam, _orig, _sleep = [], _ur.urlopen, server.time.sleep
def _corte(req, timeout):
    _llam.append(1)
    if len(_llam) < 3:
        raise urllib.error.URLError(ConnectionResetError(10054, "forzado"))
    return _io.BytesIO(b'{"ok": 1}')
class _H:
    headers = {"X-OpenRouter-Key": "sk-test"}
server.time.sleep, _ur.urlopen = (lambda s: None), _corte
assert server.H._or(_H(), "x", {}) == {"ok": 1} and len(_llam) == 3
_llam.clear()
def _401(req, timeout):
    _llam.append(1); raise urllib.error.HTTPError("u", 401, "no", {}, _io.BytesIO(b""))
_ur.urlopen = _401
try:
    server.H._or(_H(), "x", {}); assert False
except urllib.error.HTTPError:
    assert len(_llam) == 1
_ur.urlopen, server.time.sleep = _orig, _sleep
print("ok reintentos")

# protagonista obligatorio: si el Director deja un flyer de comida sin sujeto, se le pide una vez mas
_sin = {"plan": "", "fondo": {"canvas_settings": {}, "layers": [{"description": "dark wood"}]}, "sujeto": None,
        "textos": [{"rol": "titulo", "texto": "Mofongo *hoy*", "zona": "cx: 0.5, cy: 0.15, w: 0.8, h: 0.12"}]}
_con = {**_sin, "sujeto": {"canvas_settings": {}, "layers": [{"description": "mofongo"}]}, "sujeto_zona": "cx: 0.5, cy: 0.6, w: 0.6, h: 0.5"}
_resp = [_sin, _con]
def _seq(body):
    return {"choices": [{"message": {"content": json.dumps(_resp.pop(0) if _resp else {"textos": []})}}]}
r = agente.director_v2(_seq, "flyer", "mofongo de hoy", lettering=False)
assert r["hibrido"]["sujeto"] and "mofongo" in r["hibrido"]["sujeto"]
_resp = [_sin]
assert agente.director_v2(_seq, "tipografia", "frase", lettering=False)["hibrido"]["sujeto"] is None  # tipografia: null vale
print("ok protagonista")

# el nombre de la marca mal escrito en cualquier texto se corrige; palabras parecidas pero distintas no
marcas.guardar({"nombre": "Nanoboy", "colores": []})
t = agente.nombre_de_marca([{"rol": "subtitulo", "texto": "NANBOY EN VIVO"}, {"rol": "texto", "texto": "Nanobot y Nano"}], "nanoboy")
assert t[0]["texto"] == "NANOBOY EN VIVO" and t[1]["texto"] == "Nanobot y Nano", t
print("ok nombre de marca")

# disenador IA: borrador -> render real -> el modelo mira su render (sin scripts del modelo, con logo y meta)
import disenador, motor, shutil
disenador.DIR = tmp / "disenos"; disenador.DIR.mkdir()
_out = motor.OUT
motor.OUT = tmp
Image.new("RGB", (400, 500), (20, 20, 30)).save(tmp / "arte.png")
_pag = ('<!doctype html><html><head><style>body{width:1080px;height:1350px;margin:0;position:relative;overflow:hidden;'
        'background:url(arte.png) center/cover}h1{position:absolute;top:80px;left:60px;color:#fff;font:900 120px sans-serif}</style>'
        '</head><body onload="x()"><script>alert(1)</script><h1>HOLA</h1></body></html>')
_ll = []
def _dchat(body):
    _ll.append(body)
    return {"choices": [{"message": {"content": "```html\n" + _pag + "\n```" if len(_ll) == 1 else "OK"}}], "usage": {"cost": 0.01}}
stem, meta = disenador.disenar(_dchat, tmp / "arte.png", "HOLA", "")
html = (disenador.DIR / stem / "index.html").read_text(encoding="utf-8")
assert "alert" not in html and "onload" not in html and "__listo" in html
assert (tmp / f"{stem}.png").is_file() and Image.open(tmp / f"{stem}.png").size == (2160, 2700)
assert meta["h"] == 1350 and meta["costo"] == 0.02 and len(_ll) == 2
assert _ll[1]["messages"][-1]["content"][0]["type"] == "image_url"  # la revision mira el render real
_ll.clear()
stem2, meta2 = disenador.retocar(_dchat, stem, "titular mas grande")
assert meta2["previo"] == stem and "titular mas grande" in _ll[0]["messages"][-1]["content"][-1]["text"]
motor.OUT = _out
print("ok disenador")

# interruptor "Diseno con texto" apagado: el Director recibe la orden de arte limpio y el prompt lleva la prohibicion de texto
_ch = fake({"plan": "ok", "caption": {"canvas_settings": {"image_style": "moody"}, "layers": [{"description": "copas"}]}})
p, plan, extra = agente.crear_prompt(_ch, "flyer", "Viernes \"HOY SE PRENDE\"", False, solo_arte=True, hibrido=True)
assert extra is None and agente.SIN_TEXTO.strip() in json.loads(p)["canvas_settings"]["image_style"]
assert "SOLO ARTE" in _ch.llamadas[0]["messages"][1]["content"] and "MOTOR HIBRIDO" not in _ch.llamadas[0]["messages"][0]["content"]
p, _, _ = agente.crear_prompt(fake({"plan": "", "caption": {"canvas_settings": {}, "layers": [{"description": "x"}]}}), "flyer", "x", True, solo_arte=True)
assert p.startswith(agente.RGBA) and "no text" in json.loads(p[len(agente.RGBA):])["canvas_settings"]["image_style"].lower()
print("ok solo arte")

# actualizaciones: comparar versiones por numero, no por texto ("1.10.0" es mas nueva que "1.9.0")
import server
assert server._v("1.10.0") > server._v("1.9.0") and server._v("v1.0.1") > server._v("1.0.0")
assert server.VERSION and (server.ROOT / "requirements.txt").is_file()
h = object.__new__(server.H)  # las imagenes se sirven desde la carpeta de datos, no desde el codigo
assert h.translate_path("/salidas/a%20b.png?v=1") == str(server.DATOS / "salidas/a b.png")
print("ok version")
