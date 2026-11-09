"""Almacen de casos en SQLite: un archivo local, sin servidor ni cuenta.

La ruta sale de DB_PATH (por defecto data/casos.db). Se lee en cada llamada,
asi los tests pueden apuntar a un archivo temporal.
Mas adelante, en Cloud Run, este modulo se reemplaza por Firestore sin tocar main.py.
"""
import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS casos (
    id TEXT PRIMARY KEY,
    fecha TEXT NOT NULL,
    cliente TEXT, tipo TEXT, urgencia TEXT,
    resumen TEXT, accion_sugerida TEXT, origen TEXT,
    acciones TEXT
)
"""


def _conectar() -> sqlite3.Connection:
    ruta = Path(os.getenv("DB_PATH") or RAIZ / "data" / "casos.db")
    ruta.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(ruta)
    con.row_factory = sqlite3.Row
    con.execute(_ESQUEMA)
    return con


def guardar(caso: dict) -> None:
    with closing(_conectar()) as con, con:  # 'con' como contexto = commit/rollback
        con.execute(
            "INSERT INTO casos VALUES (?,?,?,?,?,?,?,?,?)",
            (caso["id"], caso["fecha"], caso["cliente"], caso["tipo"], caso["urgencia"],
             caso["resumen"], caso["accion_sugerida"], caso["origen"],
             json.dumps(caso.get("acciones", []), ensure_ascii=False)),
        )


def listar(limite: int = 100, tipo: str | None = None) -> list[dict]:
    """Casos mas recientes primero."""
    sql, params = "SELECT * FROM casos", []
    if tipo:
        sql += " WHERE tipo = ?"
        params.append(tipo)
    sql += " ORDER BY fecha DESC LIMIT ?"
    params.append(limite)
    with closing(_conectar()) as con:
        filas = con.execute(sql, params).fetchall()
    casos = []
    for f in filas:
        d = dict(f)
        d["acciones"] = json.loads(d["acciones"] or "[]")
        casos.append(d)
    return casos
