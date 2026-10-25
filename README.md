# Ming Studio

Estudio de arte con IA que corre en tu computadora. Describes la idea y Ming Studio te entrega el arte: flyers, carteles, portadas, fondos y productos, con su propio director de arte que planea cada pieza.

- **Gratis e ilimitado.** La app es open source. Usa el modelo Ming-Image a través de OpenRouter con **tu propia key**, así que tú controlas el costo (hoy es prácticamente cero).
- **Todo local.** Tus diseños, marcas y biblioteca se quedan en tu computadora.
- **Se actualiza sola.** Cuando sale una versión nueva, la app te avisa y la instalas con un botón.

Hecho por [365 Collaboration](https://www.365collaboration.net) · [@365collaboration](https://www.youtube.com/@365collaboration)

## Qué necesitas

| | Windows | Mac |
|---|---|---|
| Python 3.10 o más nuevo | [python.org](https://www.python.org/downloads/) (marca **"Add python.exe to PATH"**) | [python.org](https://www.python.org/downloads/) |
| Node.js (LTS) | [nodejs.org](https://nodejs.org) | [nodejs.org](https://nodejs.org) |
| Git | [git-scm.com](https://git-scm.com/download/win) | en la Terminal: `xcode-select --install` |
| Una key de OpenRouter | [openrouter.ai/keys](https://openrouter.ai/keys) | [openrouter.ai/keys](https://openrouter.ai/keys) |

Espacio: unos 1.5 GB (Chromium para exportar y el modelo que recorta fondos).

## Instalar

Abre una terminal (en Windows, "Símbolo del sistema"; en Mac, "Terminal") y pega:

```
git clone https://github.com/365diascollaboration-prog/ming-studio.git
cd ming-studio
```

Después:

- **Windows:** doble clic en `instalar.bat`
- **Mac:** en la misma Terminal, `bash instalar.sh`

## Abrir

- **Windows:** doble clic en `iniciar.bat`
- **Mac:** doble clic en `iniciar.command` (la primera vez: clic derecho, Abrir)

Se abre en tu navegador en `http://127.0.0.1:8140`. Pega tu key de OpenRouter arriba y listo. La key se guarda solo en tu navegador.

Para apagar Ming Studio, cierra la ventana negra de la terminal.

## Actualizar

Cuando haya una versión nueva te sale un aviso arriba en la app. Le das a **Actualizar**, cierras Ming Studio y lo abres otra vez.

También puedes hacerlo a mano: `git pull` dentro de la carpeta y vuelves a correr el instalador.

## Tus datos

Todo lo tuyo vive en la carpeta **`MingStudio`** dentro de tu usuario (`C:\Users\TU_USUARIO\MingStudio` o `/Users/TU_USUARIO/MingStudio`): diseños, marcas, logos, biblioteca y lo que la app aprende de tus calificaciones. Las actualizaciones nunca tocan esa carpeta. Para respaldar, copia esa carpeta.

## Opciones avanzadas

Variables de entorno antes de abrir la app:

| Variable | Qué hace |
|---|---|
| `MING_DISENADOR_ON=1` | Prende el Diseñador IA (escribe el diseño con texto encima del arte). Experimental. |
| `MING_DISENADOR=modelo` | Modelo de OpenRouter para el Diseñador (por defecto `qwen/qwen3.8-flash`). |
| `MING_PUERTO=8141` | Otro puerto. |
| `MING_DATOS=ruta` | Otra carpeta para tus datos. |

## Problemas comunes

- **"Falta Python" aunque lo instalé:** reinstálalo marcando "Add python.exe to PATH" y abre una terminal nueva.
- **"La key no funciona":** revisa que esté completa (empieza con `sk-or-v1-`).
- **El primer recorte tarda:** la primera vez se baja el modelo de recorte (unos 170 MB).

¿Otro problema? Abre un [issue](https://github.com/365diascollaboration-prog/ming-studio/issues).

## Licencia

[AGPL-3.0](LICENSE). Puedes usarla, estudiarla y modificarla. Si la ofreces como servicio a otros, tienes que publicar tu código con la misma licencia.
