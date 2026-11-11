# Inbox a Acción

Agente de IA que convierte mensajes de clientes en acciones. Recibe un texto, lo clasifica con Gemini (cliente, tipo, urgencia, resumen y acción sugerida), decide qué hacer según reglas y ejecuta herramientas a través de un servidor MCP. Los casos se guardan y se ven en un panel web. Proyecto personal en construcción.

```
mensaje ──▶ API (FastAPI) ──▶ clasificador (Gemini) ──▶ agente por reglas ──▶ herramientas (servidor MCP)
                │                                                                  │
                └──▶ casos en SQLite ──▶ panel en React              Telegram · tarea · hoja de cálculo
```

## Estado

- [x] Clasificador con validación (Pydantic), reintentos y salida JSON
- [x] Dataset de evaluación y bitácora de iteraciones del prompt (ver [`docs/bitacora.md`](docs/bitacora.md))
- [x] API con FastAPI y autenticación por token
- [x] Servidor MCP con 3 herramientas
- [x] Agente por reglas que elige las herramientas según tipo y urgencia
- [x] Aviso real por Telegram (`notificar_equipo`)
- [x] Persistencia de casos en SQLite
- [x] Panel en React
- [ ] `registrar_en_sheet` real (hoy simulado)
- [ ] `crear_tarea` real (hoy simulado)
- [x] Flujo en n8n: correo a la API (probado con un correo de ejemplo; la lectura de Gmail por IMAP aún no está probada)
- [x] Agente que decide con el LLM (Gemini propone, los guardarraíles filtran y las reglas son el respaldo)
- [ ] Despliegue en Cloud Run (con Firestore en lugar de SQLite)

## Reglas del agente

| Caso | Acciones |
|---|---|
| `spam` | Solo se guarda, no ejecuta nada |
| `cotizacion` | Registra en la hoja, crea una tarea y avisa al canal de ventas |
| `soporte` o `queja` con urgencia alta | Crea una tarea de prioridad alta y envía un aviso urgente |
| Cualquier otro | Registra en la hoja |

Si una herramienta falla, el caso igualmente se guarda con el error en `acciones`.

Con `AGENTE_MODO=llm`, Gemini propone el plan y unos guardarraíles lo filtran: el spam nunca ejecuta herramientas, solo se aceptan las herramientas declaradas con argumentos válidos y un problema urgente siempre avisa al equipo. Si Gemini falla, se usan las reglas. Cada acción indica en `planificador` quién la decidió.

## Requisitos

- Python 3.11 o superior
- Node.js (LTS), solo para el panel
- Una clave de API de [Google AI Studio](https://aistudio.google.com/apikey)
- Un bot de Telegram (opcional): sin él, los avisos se simulan

## Configuración (Windows PowerShell)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r api\requirements.txt
Copy-Item .env.example .env
```

Edita `.env` con tus valores:

| Variable | Para qué sirve |
|---|---|
| `GEMINI_API_KEY` | Clave de Google AI Studio |
| `MODELO_LLM` | Nombre del modelo (cambia con el tiempo; si da 404, mira el vigente en AI Studio) |
| `PROMPT_VERSION` | Versión del prompt a usar (`v1`, `v2`, `v3`) |
| `AGENTE_MODO` | `reglas` (por defecto) o `llm`: quién decide qué herramientas ejecutar |
| `API_TOKEN` | Token que protege la API. Genera uno largo, por ejemplo con `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `TELEGRAM_BOT_TOKEN` | Token del bot, de @BotFather (opcional) |
| `TELEGRAM_CHAT_ID` | Chat que recibe los avisos (opcional) |
| `DB_PATH` | Ruta de la base SQLite (opcional, por defecto `data\casos.db`) |

## Cómo ejecutarlo

Necesitas dos terminales con el entorno activo (tres si usas el panel).

**1. API**

```powershell
uvicorn main:app --app-dir api --reload
```

Documentación interactiva en <http://localhost:8000/docs>.

**2. Panel** (opcional)

```powershell
cd panel
npm install
npm run dev
```

Abre <http://localhost:5173> e ingresa tu `API_TOKEN`.

**3. Probar con un mensaje**

```powershell
$token = (Select-String -Path .env -Pattern '^API_TOKEN=').Line.Split('=',2)[1]
$cuerpo = [System.Text.Encoding]::UTF8.GetBytes('{"mensaje": "Necesito una cotización para automatizar mi facturación antes del viernes."}')
Invoke-RestMethod -Method Post -Uri http://localhost:8000/procesar -Headers @{"x-api-token"=$token} -ContentType "application/json; charset=utf-8" -Body $cuerpo
```

## API

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/salud` | Estado del servicio (sin token) |
| `POST` | `/procesar` | Clasifica un mensaje, ejecuta las acciones y guarda el caso |
| `GET` | `/casos` | Lista los casos, más recientes primero. Acepta `?limite=` (1 a 500) y `?tipo=` |

`/procesar` y `/casos` requieren la cabecera `x-api-token`.

## Pruebas

Ninguna de estas pruebas gasta cuota de Gemini ni envía avisos reales:

```powershell
python tests\test_almacen.py
python tests\test_agente.py
python tests\test_api.py
python tests\test_telegram.py
python tests\test_agente_llm.py
```

## Evaluar el prompt

Mide el acierto del clasificador contra un dataset etiquetado. Esta sí llama a Gemini:

```powershell
$env:PROMPT_VERSION="v3"
python tests\evaluar.py
```

Para otro dataset: `$env:DATASET="mensajes_dificiles.json"`. Los resultados de cada versión, lo que falló y lo que se cambió están en la [bitácora](docs/bitacora.md).

## Evaluar el agente

Compara el plan de Gemini con el de las reglas, sin ejecutar ninguna herramienta (una llamada a Gemini por mensaje que no sea spam):

```powershell
python tests\evaluar_agente.py
```

## Estructura

```
api/          API, clasificador, agente y almacén de casos
mcp_server/   Servidor MCP con las herramientas
prompts/      Versiones del prompt del clasificador
panel/        Panel web en React (Vite)
tests/        Pruebas y datasets de evaluación
docs/         Bitácora de iteraciones del prompt
```

## Notas

- Nunca subas el archivo `.env` ni la carpeta `data\`: contienen claves y mensajes de clientes. Ambos están en `.gitignore`.
- El servidor MCP usa stdio: no imprimas a la salida estándar dentro de `mcp_server\server.py`, porque corrompe el protocolo.
- SQLite sirve para desarrollo local. En Cloud Run el disco se borra al reiniciar, por eso la persistencia está aislada en `api\almacen.py` para cambiarla por Firestore.
- Los tests activan `MODO_PRUEBA`, que fuerza las notificaciones simuladas aunque tu `.env` tenga el token real.
