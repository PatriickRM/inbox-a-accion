"""Pruebas del agente por reglas y de la conexion real con el servidor MCP.

Uso (desde la raiz del repo):  python tests/test_agente.py   (o: pytest tests)
No llama al LLM: usa casos ya clasificados.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api"))

from agente import ejecutar, plan_por_reglas  # noqa: E402


def caso(tipo, urgencia, cliente="Ana - Textiles Sol"):
    return {"cliente": cliente, "tipo": tipo, "urgencia": urgencia,
            "resumen": "Resumen de prueba.", "accion_sugerida": "Accion de prueba."}


def nombres(plan):
    return [p["herramienta"] for p in plan]


def test_spam_no_hace_nada():
    assert plan_por_reglas(caso("spam", "baja")) == []


def test_cotizacion_usa_las_tres_herramientas():
    assert nombres(plan_por_reglas(caso("cotizacion", "baja"))) == [
        "registrar_en_sheet", "crear_tarea", "notificar_equipo"]


def test_cotizacion_con_plazo_sube_prioridad():
    tarea = plan_por_reglas(caso("cotizacion", "alta"))[1]
    assert tarea["args"]["prioridad"] == "alta"


def test_soporte_alta_notifica_urgente():
    plan = plan_por_reglas(caso("soporte", "alta"))
    assert nombres(plan) == ["crear_tarea", "notificar_equipo"]
    assert plan[0]["args"]["prioridad"] == "alta"
    assert plan[1]["args"]["canal"] == "urgente"


def test_queja_alta_notifica_urgente():
    assert nombres(plan_por_reglas(caso("queja", "alta"))) == ["crear_tarea", "notificar_equipo"]


def test_resto_solo_registra():
    for tipo, urg in [("soporte", "media"), ("queja", "media"), ("consulta", "baja"), ("soporte", "baja")]:
        assert nombres(plan_por_reglas(caso(tipo, urg))) == ["registrar_en_sheet"], (tipo, urg)


def test_integracion_con_servidor_mcp_real():
    res = ejecutar(caso("cotizacion", "alta"))
    assert [r["herramienta"] for r in res] == ["registrar_en_sheet", "crear_tarea", "notificar_equipo"]
    assert all(r["ok"] for r in res), res


def test_spam_no_abre_el_servidor():
    assert ejecutar(caso("spam", "baja")) == []


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
