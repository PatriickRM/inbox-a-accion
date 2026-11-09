"""Pruebas del almacen SQLite. Usa un archivo temporal, nunca la base real.

Uso (desde la raiz del repo):  python tests/test_almacen.py
"""
import os
import sys
import tempfile
from pathlib import Path

os.environ["DB_PATH"] = str(Path(tempfile.mkdtemp()) / "prueba.db")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api"))

import almacen  # noqa: E402


def caso(id_, fecha, tipo="soporte", cliente="Ana"):
    return {"id": id_, "fecha": fecha, "cliente": cliente, "tipo": tipo, "urgencia": "alta",
            "resumen": "Caída de facturación", "accion_sugerida": "Llamar hoy", "origen": "correo",
            "acciones": [{"herramienta": "crear_tarea", "ok": True}]}


def test_guarda_y_lista_con_tildes_y_acciones():
    almacen.guardar(caso("a", "2026-11-09T10:00:00"))
    c = almacen.listar()[0]
    assert c["resumen"] == "Caída de facturación"
    assert c["acciones"] == [{"herramienta": "crear_tarea", "ok": True}]


def test_los_mas_recientes_van_primero():
    almacen.guardar(caso("b", "2026-11-09T11:00:00"))
    almacen.guardar(caso("c", "2026-11-09T12:00:00"))
    assert [x["id"] for x in almacen.listar()][:2] == ["c", "b"]


def test_filtra_por_tipo_y_limita():
    almacen.guardar(caso("d", "2026-11-09T13:00:00", tipo="spam"))
    assert [x["tipo"] for x in almacen.listar(tipo="spam")] == ["spam"]
    assert len(almacen.listar(limite=2)) == 2


def test_sobrevive_a_un_reinicio():
    # Cada llamada abre su propia conexion: equivale a reiniciar el proceso
    ids = {x["id"] for x in almacen.listar()}
    assert {"a", "b", "c", "d"} <= ids


def test_id_repetido_no_se_duplica():
    try:
        almacen.guardar(caso("a", "2026-11-09T10:00:00"))
    except Exception:
        return
    raise AssertionError("debio rechazar un id repetido")


def test_inyeccion_sql_no_funciona():
    almacen.listar(tipo="x'; DROP TABLE casos; --")
    assert almacen.listar()  # la tabla sigue ahi


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
