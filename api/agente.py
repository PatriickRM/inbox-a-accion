"""Agente: decide qué herramientas MCP ejecutar y las ejecuta.

AGENTE_MODO=reglas (por defecto): reglas fijas, predecibles y sin costo de LLM.
AGENTE_MODO=llm: Gemini propone el plan, los guardarraíles lo filtran
(ver agente_llm.py) y, si Gemini falla, se usan las reglas como respaldo.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

import agente_llm

RAIZ = Path(__file__).resolve().parent.parent
SERVIDOR_MCP = RAIZ / "mcp_server" / "server.py"


def _log(texto: str) -> None:
    print(texto, file=sys.stderr, flush=True)


def plan_por_reglas(caso: dict) -> list[dict]:
    """Devuelve la lista de llamadas a herramientas [{'herramienta', 'args'}]."""
    tipo, urgencia = caso["tipo"], caso["urgencia"]
    cliente, resumen = caso["cliente"], caso["resumen"]

    def sheet():
        return {"herramienta": "registrar_en_sheet",
                "args": {"cliente": cliente, "tipo": tipo, "urgencia": urgencia, "resumen": resumen}}

    def tarea(prioridad):
        return {"herramienta": "crear_tarea",
                "args": {"titulo": f"[{tipo}] {cliente}", "descripcion": f"{resumen} Accion: {caso['accion_sugerida']}",
                         "prioridad": prioridad}}

    def aviso(canal, prefijo=""):
        return {"herramienta": "notificar_equipo",
                "args": {"mensaje": f"{prefijo}{tipo} ({urgencia}) de {cliente}: {resumen}", "canal": canal}}

    if tipo == "spam":
        return []  # solo se guarda en la base de datos, no se notifica
    if tipo == "cotizacion":
        return [sheet(), tarea("alta" if urgencia == "alta" else "media"), aviso("ventas")]
    if tipo in ("soporte", "queja") and urgencia == "alta":
        return [tarea("alta"), aviso("urgente", "URGENTE: ")]
    return [sheet()]


def _leer_resultado(r) -> dict:
    """Extrae el dict que devolvió la herramienta (viene como texto JSON en content)."""
    if getattr(r, "structured_content", None):
        return dict(r.structured_content)
    for bloque in getattr(r, "content", []) or []:
        texto = getattr(bloque, "text", None)
        if texto:
            try:
                dato = json.loads(texto)
                return dato if isinstance(dato, dict) else {"valor": dato}
            except json.JSONDecodeError:
                return {"texto": texto}
    return {}


def _parametros_servidor() -> StdioServerParameters:
    # El subproceso recibe un entorno mínimo; solo reenviamos lo que hace falta.
    env = {k: os.environ[k] for k in ("MODO_PRUEBA",) if k in os.environ}
    return StdioServerParameters(command=sys.executable, args=[str(SERVIDOR_MCP)], env=env)


async def _decidir(caso: dict, reglas: list[dict], sesion) -> tuple[list[dict], str]:
    """Elige el plan según el modo. Devuelve (plan, quién_lo_decidió)."""
    if os.getenv("AGENTE_MODO", "reglas").strip().lower() != "llm":
        return reglas, "reglas"
    try:
        herramientas = (await sesion.list_tools()).tools
        # La llamada a Gemini es bloqueante: va en un hilo para no frenar el bucle del cliente MCP
        propuesta = await asyncio.to_thread(agente_llm.planificar_con_llm, caso, herramientas)
        plan, ajustes, uso_reglas = agente_llm.validar_plan(propuesta, caso, herramientas, reglas)
        for a in ajustes:
            _log(f"[AGENTE] guardarraíl: {a}")
        return plan, ("reglas (plan vacío del LLM)" if uso_reglas else "llm")
    except Exception as e:  # Gemini saturado, sin cuota, respuesta rara...: nunca perdemos el caso
        # Solo el tipo de error: no volcamos el mensaje por si arrastra datos sensibles
        _log(f"[AGENTE] respaldo a reglas por {type(e).__name__} {getattr(e, 'code', '')}".strip())
        return reglas, "reglas (respaldo)"


async def _ejecutar_async(caso: dict) -> list[dict]:
    reglas = plan_por_reglas(caso)
    resultados = []
    async with stdio_client(_parametros_servidor()) as (leer, escribir):
        async with ClientSession(leer, escribir) as sesion:
            await sesion.initialize()
            plan, quien = await _decidir(caso, reglas, sesion)
            for paso in plan:
                try:
                    r = await sesion.call_tool(paso["herramienta"], paso["args"])
                    datos = _leer_resultado(r)
                    ok = (not r.is_error) and datos.get("ok", True) is not False
                    entrada = {"herramienta": paso["herramienta"], "ok": ok, "resultado": datos}
                    if not ok:
                        entrada["error"] = datos.get("error", "la herramienta devolvio un error")
                except Exception as e:  # una herramienta que falla no debe tumbar las demas
                    entrada = {"herramienta": paso["herramienta"], "ok": False, "error": str(e)}
                entrada["planificador"] = quien
                resultados.append(entrada)
    return resultados


def _correr(corrutina):
    """Ejecuta una corrutina en un bucle propio.

    En Windows, uvicorn --reload deja activo un bucle (Selector) que no puede lanzar
    subprocesos, y el cliente MCP necesita lanzar el servidor como subproceso.
    Con un bucle Proactor propio funciona igual con o sin --reload.
    """
    if sys.platform == "win32":
        bucle = asyncio.ProactorEventLoop()
        try:
            return bucle.run_until_complete(corrutina)
        finally:
            bucle.close()
    return asyncio.run(corrutina)


def ejecutar(caso: dict) -> list[dict]:
    """Decide y ejecuta. Síncrono: seguro de llamar desde un endpoint FastAPI normal."""
    if caso["tipo"] == "spam":
        return []  # regla fija: ni se abre el servidor MCP ni se gasta una llamada al LLM
    return _correr(_ejecutar_async(caso))


async def _listar_herramientas():
    async with stdio_client(_parametros_servidor()) as (leer, escribir):
        async with ClientSession(leer, escribir) as sesion:
            await sesion.initialize()
            return (await sesion.list_tools()).tools


def obtener_herramientas():
    """Descubre las herramientas que declara el servidor MCP (nombre, descripción y esquema)."""
    return _correr(_listar_herramientas())
