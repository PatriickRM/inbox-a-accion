"""Planificador con LLM: Gemini decide qué herramientas MCP ejecutar.

Gemini NO ejecuta nada. Solo propone un plan (lista de llamadas). Después
validar_plan() lo filtra con guardarraíles fijos, porque el caso viene de
texto escrito por un cliente (no es confiable) y el plan decide acciones reales.
"""
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

RAIZ = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ / ".env")

MAX_ACCIONES = 4      # tope de llamadas que puede proponer el LLM
MAX_TEXTO = 2000      # largo máximo de cada argumento de texto
CAMPOS_CASO = ("cliente", "tipo", "urgencia", "resumen", "accion_sugerida")

_TIPOS_GEMINI = {"string": "STRING", "integer": "INTEGER", "number": "NUMBER", "boolean": "BOOLEAN"}


def _prompt() -> str:
    version = os.getenv("AGENTE_PROMPT_VERSION", "v1")
    return (RAIZ / "prompts" / f"agente_{version}.txt").read_text(encoding="utf-8-sig")


def _esquema(herramienta) -> dict:
    """Esquema JSON de los argumentos (mcp 2.x: input_schema; mcp 1.x: inputSchema)."""
    return getattr(herramienta, "input_schema", None) or getattr(herramienta, "inputSchema", None) or {}


def _schema_gemini(esquema: dict) -> types.Schema:
    """Convierte el esquema JSON de una herramienta MCP al formato de Gemini."""
    propiedades = {}
    for nombre, p in esquema.get("properties", {}).items():
        tipo = _TIPOS_GEMINI.get(p.get("type"))
        if tipo is None:  # mejor fallar (y usar reglas) que declarar mal una herramienta
            raise ValueError(f"tipo no soportado en '{nombre}': {p.get('type')}")
        datos = {"type": tipo}
        if p.get("description"):
            datos["description"] = p["description"]
        if p.get("enum"):
            datos["enum"] = [str(x) for x in p["enum"]]
        propiedades[nombre] = types.Schema(**datos)
    return types.Schema(type="OBJECT", properties=propiedades, required=list(esquema.get("required", [])))


def declaraciones(herramientas) -> list[types.FunctionDeclaration]:
    return [
        types.FunctionDeclaration(name=h.name, description=h.description or "", parameters=_schema_gemini(_esquema(h)))
        for h in herramientas
    ]


def _llamar(cliente, contenido: str, decls, intentos: int = 3):
    """Llama a Gemini y reintenta con espera creciente si está saturado (503) o limitado (429)."""
    config = types.GenerateContentConfig(
        system_instruction=_prompt(),
        tools=[types.Tool(function_declarations=decls)],
        # Gemini solo propone: ejecutamos nosotros, tras validar
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        temperature=0,
        max_output_tokens=1000,
    )
    modelo = os.getenv("MODELO_LLM", "gemini-3.5-flash-lite")
    for n in range(intentos):
        try:
            return cliente.models.generate_content(model=modelo, contents=contenido, config=config)
        except (errors.ServerError, errors.ClientError) as e:
            temporal = isinstance(e, errors.ServerError) or getattr(e, "code", None) == 429
            if not temporal or n == intentos - 1:
                raise
            time.sleep(2 ** (n + 1))


def planificar_con_llm(caso: dict, herramientas, cliente=None) -> list[dict]:
    """Pide a Gemini el plan. Devuelve [{'herramienta': ..., 'args': {...}}], sin validar."""
    cliente = cliente or genai.Client()  # lee GEMINI_API_KEY; se crea aquí para no exigirla al importar
    # Solo le damos los campos clasificados, no el mensaje original: menos superficie de ataque
    contenido = "Caso clasificado:\n" + json.dumps({k: caso.get(k) for k in CAMPOS_CASO}, ensure_ascii=False, indent=2)
    resp = _llamar(cliente, contenido, declaraciones(herramientas))
    llamadas = getattr(resp, "function_calls", None) or []
    return [{"herramienta": fc.name, "args": dict(fc.args or {})} for fc in llamadas]


def _limpiar_args(args: dict, esquema: dict):
    """Devuelve (args_limpios, None) o (None, motivo_del_rechazo)."""
    props = esquema.get("properties", {})
    limpio = {}
    for k, v in args.items():
        if k not in props:
            continue  # argumentos que la herramienta no declara: se eliminan
        tipo = props[k].get("type")
        if tipo == "string":
            if isinstance(v, (dict, list)) or v is None:
                return None, f"el argumento '{k}' debe ser texto"
            v = str(v).strip()[:MAX_TEXTO]
        elif tipo == "integer":
            if isinstance(v, bool) or not isinstance(v, (int, float)) or int(v) != v:
                return None, f"el argumento '{k}' debe ser entero"
            v = int(v)
        elif tipo == "number":
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                return None, f"el argumento '{k}' debe ser numérico"
        elif tipo == "boolean" and not isinstance(v, bool):
            return None, f"el argumento '{k}' debe ser booleano"
        if props[k].get("enum") and v not in props[k]["enum"]:
            return None, f"el argumento '{k}' tiene un valor no permitido"
        limpio[k] = v
    faltan = [r for r in esquema.get("required", []) if limpio.get(r) in (None, "")]
    if faltan:
        return None, f"faltan argumentos obligatorios: {', '.join(faltan)}"
    return limpio, None


def validar_plan(plan: list[dict], caso: dict, herramientas, reglas: list[dict]):
    """Aplica los guardarraíles. Devuelve (plan_final, ajustes, uso_reglas).

    - spam: nunca ejecuta herramientas, diga lo que diga el LLM.
    - Solo herramientas declaradas por el servidor MCP, con argumentos válidos.
    - Sin duplicados y con un tope de acciones.
    - Un problema urgente (soporte o queja con urgencia alta) siempre notifica al equipo.
    - Un plan vacío para un caso real no se acepta: se usan las reglas.
    """
    ajustes: list[str] = []
    if caso["tipo"] == "spam":
        if plan:
            ajustes.append("spam: se descartaron todas las acciones propuestas")
        return [], ajustes, False

    esquemas = {h.name: _esquema(h) for h in herramientas}
    final, vistos = [], set()
    for paso in plan:
        nombre = paso.get("herramienta")
        if nombre not in esquemas:
            ajustes.append(f"herramienta desconocida descartada: {nombre}")
            continue
        args, motivo = _limpiar_args(paso.get("args") or {}, esquemas[nombre])
        if motivo:
            ajustes.append(f"{nombre} descartada: {motivo}")
            continue
        clave = (nombre, json.dumps(args, sort_keys=True, ensure_ascii=False))
        if clave in vistos:
            ajustes.append(f"{nombre} duplicada descartada")
            continue
        if len(final) >= MAX_ACCIONES:
            ajustes.append(f"se superó el máximo de {MAX_ACCIONES} acciones")
            break
        vistos.add(clave)
        final.append({"herramienta": nombre, "args": args})

    if not final:
        ajustes.append("plan vacío o inválido para un caso real: se usan las reglas")
        return list(reglas), ajustes, True

    urgente = caso["tipo"] in ("soporte", "queja") and caso["urgencia"] == "alta"
    if urgente and not any(p["herramienta"] == "notificar_equipo" for p in final):
        aviso = next((p for p in reglas if p["herramienta"] == "notificar_equipo"), None)
        if aviso:
            ajustes.append("problema urgente sin aviso: se agregó notificar_equipo")
            final.append(aviso)
    return final, ajustes, False
