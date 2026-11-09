"""Servidor MCP de Inbox a Accion: 3 herramientas en modo simulado.

IMPORTANTE: con transporte stdio, stdout es el canal del protocolo MCP.
Nunca uses print() a stdout aqui; los mensajes de depuracion van a stderr.
"""
import sys

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
    """Envia una notificacion al equipo por Slack o Telegram."""
    # TODO: webhook de Slack o Bot API de Telegram
    _log(f"[NOTIF #{canal}] {mensaje}")
    return {"ok": True}


if __name__ == "__main__":
    mcp.run()  # transporte stdio por defecto
