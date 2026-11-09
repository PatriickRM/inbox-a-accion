# Inbox a Acción

Clasificador de mensajes de clientes con IA: recibe un texto y devuelve un JSON con cliente, tipo, urgencia, resumen y acción sugerida. Proyecto personal en construcción.

## Estado
- [x] Clasificador con validación (Pydantic) y reintentos
- [x] Dataset de evaluación y bitácora de iteraciones del prompt (ver `docs/bitacora.md`)
- [ ] API con FastAPI
- [ ] Servidor MCP con herramientas
- [ ] Flujo en n8n
- [ ] Despliegue en Cloud Run
- [ ] Panel en React

## Cómo ejecutarlo (Windows PowerShell)
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r api\requirements.txt
Copy-Item .env.example .env   # luego edita .env con tu clave de Gemini
python api\clasificador.py
```

## Evaluar el prompt
```powershell
$env:PROMPT_VERSION="v3"
python tests\evaluar.py
```

## Notas
- Nunca subas el archivo `.env`: está en `.gitignore`.
- Los modelos de Gemini cambian de nombre; si hay un 404, revisa el nombre vigente en Google AI Studio.