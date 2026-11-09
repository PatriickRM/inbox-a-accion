"""Agente por reglas: decide que herramientas MCP ejecutar segun el caso.

Fase 1 (esta): reglas simples y faciles de depurar.
Fase 2 (luego): darle al LLM la lista de herramientas para que decida.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

RAIZ = Path(__file__).resolve().parent.parent
SERVIDOR_MCP = RAIZ / "mcp_server" / "server.py"


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
    """Extrae el dict que devolvio la herramienta (viene como texto JSON en content)."""
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


async def _ejecutar_async(plan: list[dict]) -> list[dict]:
    # El subproceso recibe un entorno minimo; solo reenviamos lo que hace falta.
    env = {k: os.environ[k] for k in ("MODO_PRUEBA",) if k in os.environ}
    params = StdioServerParameters(command=sys.executable, args=[str(SERVIDOR_MCP)], env=env)
    resultados = []
    async with stdio_client(params) as (leer, escribir):
        async with ClientSession(leer, escribir) as sesion:
            await sesion.initialize()
            for paso in plan:
                try:
                    r = await sesion.call_tool(paso["herramienta"], paso["args"])
                    datos = _leer_resultado(r)
                    ok = (not r.is_error) and datos.get("ok", True) is not False
                    entrada = {"herramienta": paso["herramienta"], "ok": ok, "resultado": datos}
                    if not ok:
                        entrada["error"] = datos.get("error", "la herramienta devolvio un error")
                    resultados.append(entrada)
                except Exception as e:  # una herramienta que falla no debe tumbar las demas
                    resultados.append({"herramienta": paso["herramienta"], "ok": False, "error": str(e)})
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
    """Planifica y ejecuta. Sincrono: seguro de llamar desde un endpoint FastAPI normal."""
    plan = plan_por_reglas(caso)
    if not plan:
        return []
    return _correr(_ejecutar_async(plan))
