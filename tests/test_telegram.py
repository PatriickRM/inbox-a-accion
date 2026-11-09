"""Prueba notificar_equipo contra un Telegram falso local. No envia nada real.

Uso (desde la raiz del repo):  python tests/test_telegram.py
"""
import importlib.util
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
TOKEN_FALSO = "123456:TOKEN-FALSO-DE-PRUEBA"
RECIBIDO = []
MODO = {"estado": 200}


class FalsoTelegram(BaseHTTPRequestHandler):
    def do_POST(self):
        largo = int(self.headers.get("content-length", 0))
        RECIBIDO.append({"ruta": self.path, "cuerpo": json.loads(self.rfile.read(largo))})
        if MODO["estado"] == 200:
            cuerpo = {"ok": True, "result": {"message_id": 42}}
        else:
            cuerpo = {"ok": False, "description": "Bad Request: chat not found"}
        datos = json.dumps(cuerpo).encode()
        self.send_response(MODO["estado"])
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)

    def log_message(self, *a):
        pass


servidor = HTTPServer(("127.0.0.1", 0), FalsoTelegram)
threading.Thread(target=servidor.serve_forever, daemon=True).start()
URL_FALSA = f"http://127.0.0.1:{servidor.server_port}"

spec = importlib.util.spec_from_file_location("server_mcp", RAIZ / "mcp_server" / "server.py")
srv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(srv)
notificar = srv.notificar_equipo


def configurar(token=TOKEN_FALSO, chat="999", base=URL_FALSA):
    for k, v in (("TELEGRAM_BOT_TOKEN", token), ("TELEGRAM_CHAT_ID", chat), ("TELEGRAM_API_BASE", base)):
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def test_envia_mensaje_con_canal_y_chat_correctos():
    configurar(); RECIBIDO.clear(); MODO["estado"] = 200
    r = notificar("Cotizacion de Luis", canal="ventas")
    assert r == {"ok": True, "message_id": 42}, r
    assert RECIBIDO[0]["ruta"] == f"/bot{TOKEN_FALSO}/sendMessage"
    assert RECIBIDO[0]["cuerpo"] == {"chat_id": "999", "text": "[ventas] Cotizacion de Luis"}


def test_error_de_telegram_devuelve_ok_false_sin_token():
    configurar(); MODO["estado"] = 400
    r = notificar("hola")
    assert r["ok"] is False and "chat not found" in r["error"]
    assert TOKEN_FALSO not in json.dumps(r)


def test_caida_de_red_no_filtra_el_token():
    configurar(base="http://127.0.0.1:1")  # puerto cerrado
    r = notificar("hola")
    assert r["ok"] is False and TOKEN_FALSO not in json.dumps(r), r


def test_el_token_no_aparece_en_los_logs():
    import io, logging
    flujo = io.StringIO()
    manejador = logging.StreamHandler(flujo)
    logging.getLogger().addHandler(manejador)
    logging.getLogger().setLevel(logging.INFO)
    try:
        configurar(); MODO["estado"] = 200
        notificar("hola")
    finally:
        logging.getLogger().removeHandler(manejador)
    assert TOKEN_FALSO not in flujo.getvalue(), flujo.getvalue()


def test_sin_credenciales_es_modo_simulado():
    configurar(token=None, chat=None)
    assert notificar("hola") == {"ok": True, "simulado": True}


def test_modo_prueba_no_envia_aunque_haya_credenciales():
    configurar(); RECIBIDO.clear(); MODO["estado"] = 200
    os.environ["MODO_PRUEBA"] = "1"
    try:
        r = notificar("hola")
    finally:
        os.environ.pop("MODO_PRUEBA")
    assert r == {"ok": True, "simulado": True} and RECIBIDO == []


def test_mensaje_largo_se_recorta():
    configurar(); RECIBIDO.clear(); MODO["estado"] = 200
    notificar("x" * 10000)
    assert len(RECIBIDO[0]["cuerpo"]["text"]) <= 4096


if __name__ == "__main__":
    fallos = 0
    for nombre, fn in list(globals().items()):
        if nombre.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"OK   {nombre}")
            except Exception as e:
                fallos += 1
                print(f"FALLO {nombre}: {e!r}")
    print(f"\n{'Todo bien' if not fallos else f'{fallos} prueba(s) fallaron'}")
    sys.exit(1 if fallos else 0)
