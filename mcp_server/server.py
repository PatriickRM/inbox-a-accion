"""Servidor MCP de Inbox a Accion: notificar_equipo real (Telegram); el resto, simulado.

IMPORTANTE: con transporte stdio, stdout es el canal del protocolo MCP.
Nunca uses print() a stdout aqui; los mensajes de depuracion van a stderr.
"""
import logging
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

# httpx registra la URL de cada peticion y la de Telegram contiene el token del bot.
# Se silencia para que el token nunca llegue a la terminal ni a los logs.
for _nombre in ("httpx", "httpcore"):
    logging.getLogger(_nombre).setLevel(logging.WARNING)

# El servidor MCP corre como subproceso y NO hereda el .env del padre
# (el SDK pasa solo un entorno minimo), asi que lo cargamos aqui.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

try:  # mcp 2.x
    from mcp.server.mcpserver import MCPServer as _Servidor
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as _Servidor

mcp = _Servidor("inbox-a-accion")


def _log(texto: str) -> None:
    print(texto, file=sys.stderr, flush=True)


@mcp.tool()
def registrar_en_sheet(cliente: str, tipo: str, urgencia: str, resumen: str) -> dict:
    """Registra un caso como una fila en Google Sheets."""
    # TODO: integrar la API de Google Sheets (gspread)
    _log(f"[SHEET] {cliente} | {tipo} | {urgencia} | {resumen}")
    return {"ok": True, "hoja": "Casos"}


@mcp.tool()
def crear_tarea(titulo: str, descripcion: str, prioridad: str = "media") -> dict:
    """Crea una tarea en el gestor de proyectos (Notion o Trello)."""
    # TODO: llamar a la API de Notion o Trello
    _log(f"[TAREA] {titulo} ({prioridad})")
    return {"ok": True, "id": "tarea-demo-001"}


@mcp.tool()
def notificar_equipo(mensaje: str, canal: str = "general") -> dict:
    """Envia una notificacion al equipo por Telegram."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    texto = f"[{canal}] {mensaje}"[:4000]  # Telegram acepta hasta 4096 caracteres

    if os.getenv("MODO_PRUEBA") or not token or not chat_id:
        # Modo simulado: sin credenciales, o forzado por MODO_PRUEBA (lo usan los tests
        # para no enviar avisos reales aunque el .env tenga el token de verdad)
        _log(f"[NOTIF simulada #{canal}] {mensaje}")
        return {"ok": True, "simulado": True}

    base = os.getenv("TELEGRAM_API_BASE", "https://api.telegram.org")
    try:
        r = httpx.post(f"{base}/bot{token}/sendMessage",
                       json={"chat_id": chat_id, "text": texto}, timeout=10)
        if r.status_code != 200:
            detalle = r.json().get("description", "sin detalle") if r.headers.get("content-type", "").startswith("application/json") else "sin detalle"
            _log(f"[NOTIF] Telegram respondio {r.status_code}: {detalle}")
            return {"ok": False, "error": f"Telegram {r.status_code}: {detalle}"}
        return {"ok": True, "message_id": r.json()["result"]["message_id"]}
    except httpx.HTTPError as e:
        # No usamos str(e): puede incluir la URL, y la URL lleva el token del bot.
        _log(f"[NOTIF] fallo de red: {type(e).__name__}")
        return {"ok": False, "error": f"fallo de red ({type(e).__name__})"}


if __name__ == "__main__":
    mcp.run()  # transporte stdio por defecto
