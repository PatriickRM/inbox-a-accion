"""Prueba la API completa con un clasificador simulado (no gasta cuota de Gemini).

Uso (desde la raiz del repo):  python tests/test_api.py
"""
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "api"))
os.environ["MODO_PRUEBA"] = "1"  # nunca enviar avisos reales desde los tests
import tempfile  # noqa: E402
os.environ["DB_PATH"] = str(Path(tempfile.mkdtemp()) / "prueba.db")  # nunca tocar la base real
os.environ["API_TOKEN"] = "token-de-prueba"
os.environ.setdefault("GEMINI_API_KEY", "falsa-para-pruebas")

from fastapi.testclient import TestClient  # noqa: E402

import clasificador  # noqa: E402

# Importamos main despues de fijar las variables de entorno
import main  # noqa: E402

RESPUESTAS = {
    "cotizacion": clasificador.Caso(cliente="Ana", tipo="cotizacion", urgencia="alta",
                                    resumen="Pide cotizacion.", accion_sugerida="Contactar."),
    "spam": clasificador.Caso(cliente="desconocido", tipo="spam", urgencia="baja",
                              resumen="Publicidad.", accion_sugerida="Ignorar."),
}
main.clasificar = lambda mensaje: RESPUESTAS["spam" if "premio" in mensaje else "cotizacion"]

cliente = TestClient(main.app)
H = {"x-api-token": "token-de-prueba"}


def test_salud():
    assert cliente.get("/salud").json() == {"estado": "ok"}


def test_sin_token_es_401():
    assert cliente.post("/procesar", json={"mensaje": "hola"}).status_code == 401
    assert cliente.get("/casos").status_code == 401


def test_token_malo_es_401():
    assert cliente.post("/procesar", json={"mensaje": "hola"}, headers={"x-api-token": "malo"}).status_code == 401


def test_mensaje_vacio_es_422():
    assert cliente.post("/procesar", json={"mensaje": ""}, headers=H).status_code == 422


def test_cotizacion_ejecuta_tres_herramientas():
    r = cliente.post("/procesar", json={"mensaje": "Necesito una cotizacion"}, headers=H)
    assert r.status_code == 200, r.text
    acciones = r.json()["acciones"]
    assert [a["herramienta"] for a in acciones] == ["registrar_en_sheet", "crear_tarea", "notificar_equipo"]
    assert all(a["ok"] for a in acciones), acciones


def test_spam_se_guarda_sin_acciones():
    r = cliente.post("/procesar", json={"mensaje": "Ganaste un premio"}, headers=H)
    assert r.status_code == 200 and r.json()["acciones"] == []


def test_casos_lista_lo_procesado():
    nuevo = cliente.post("/procesar", json={"mensaje": "Necesito una cotizacion"}, headers=H).json()
    casos = cliente.get("/casos", headers=H).json()
    assert nuevo["id"] in [c["id"] for c in casos]


def test_casos_filtra_por_tipo_y_respeta_limite():
    cliente.post("/procesar", json={"mensaje": "Ganaste un premio"}, headers=H)
    cliente.post("/procesar", json={"mensaje": "Necesito una cotizacion"}, headers=H)
    solo_spam = cliente.get("/casos?tipo=spam", headers=H).json()
    assert solo_spam and all(c["tipo"] == "spam" for c in solo_spam)
    assert len(cliente.get("/casos?limite=1", headers=H).json()) == 1
    assert cliente.get("/casos?limite=0", headers=H).status_code == 422


def test_si_el_agente_falla_el_caso_se_guarda():
    original = main.ejecutar
    main.ejecutar = lambda caso: (_ for _ in ()).throw(RuntimeError("fallo simulado"))
    try:
        antes = len(cliente.get("/casos?limite=500", headers=H).json())
        r = cliente.post("/procesar", json={"mensaje": "Necesito una cotizacion"}, headers=H)
        assert r.status_code == 200
        assert r.json()["acciones"][0]["ok"] is False
        assert len(cliente.get("/casos?limite=500", headers=H).json()) == antes + 1
    finally:
        main.ejecutar = original


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
