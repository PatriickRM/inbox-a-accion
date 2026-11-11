"""Compara el plan de Gemini con el de las reglas sobre los datasets etiquetados.

Hace UNA llamada a Gemini por mensaje (el spam se omite: es regla fija) y NO ejecuta
ninguna herramienta ni envia avisos. Usa el tipo y la urgencia esperados de cada mensaje,
asi mide solo al agente y no al clasificador.

Uso (desde la raiz del repo):
    python tests\\evaluar_agente.py
    $env:DATASET="mensajes_dificiles.json"; python tests\\evaluar_agente.py
    $env:PAUSA="13"; python tests\\evaluar_agente.py     # si tu modelo permite pocas peticiones por minuto
"""
import json
import os
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "api"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(RAIZ / ".env")

import agente  # noqa: E402
import agente_llm  # noqa: E402


def construir_caso(item: dict) -> dict:
    return {"cliente": "desconocido", "tipo": item["tipo"], "urgencia": item["urgencia"],
            "resumen": item["mensaje"][:120], "accion_sugerida": "Revisar el caso."}


def evaluar(datasets, planificar=agente_llm.planificar_con_llm, pausa=4.0):
    herramientas = agente.obtener_herramientas()
    evaluados = iguales = con_ajustes = errores = spam = 0
    diferencias, ajustados = [], []
    n = 0

    for nombre in datasets:
        print(f"\n== {nombre}")
        datos = json.loads((Path(__file__).parent / nombre).read_text(encoding="utf-8"))
        for item in datos:
            n += 1
            caso = construir_caso(item)
            etiqueta = f"{caso['tipo']}/{caso['urgencia']}"
            if caso["tipo"] == "spam":
                spam += 1
                print(f"{n:>2}. --  {etiqueta:<18} spam: regla fija, no se consulta a Gemini")
                continue

            reglas = agente.plan_por_reglas(caso)
            time.sleep(pausa)
            try:
                propuesta = planificar(caso, herramientas)
                plan, ajustes, uso_reglas = agente_llm.validar_plan(propuesta, caso, herramientas, reglas)
            except Exception as e:
                errores += 1
                print(f"{n:>2}. ERR {etiqueta:<18} {type(e).__name__} {getattr(e, 'code', '')}")
                continue

            evaluados += 1
            r = [p["herramienta"] for p in reglas]
            l = [p["herramienta"] for p in plan]
            igual = sorted(r) == sorted(l)
            iguales += igual
            print(f"{n:>2}. {'=  ' if igual else 'DIF'} {etiqueta:<18} reglas={r}  llm={l}")
            if not igual:
                diferencias.append((n, etiqueta, item["mensaje"][:70], r, l))
            if ajustes:
                con_ajustes += 1
                ajustados.append((n, etiqueta, ajustes))
                for a in ajustes:
                    print(f"       guardarraíl: {a}")

    print("\n" + "=" * 60)
    print(f"Evaluados (no spam):                  {evaluados}")
    print(f"Mismo conjunto de herramientas:       {iguales}/{evaluados}")
    print(f"Distinto al de las reglas:            {evaluados - iguales}/{evaluados}")
    print(f"Casos donde un guardarraíl intervino: {con_ajustes}/{evaluados}")
    print(f"Errores (Gemini no respondió):        {errores}")
    print(f"Spam omitido:                         {spam}")
    if diferencias:
        print("\nDiferencias respecto a las reglas (para la bitácora):")
        for n, etiqueta, msg, r, l in diferencias:
            print(f"- #{n} {etiqueta}: reglas={r} llm={l}  -> {msg}")
    print("\nUna diferencia no es un error: es un caso para que TÚ juzgues si Gemini decidió mejor o peor.")
    return {"evaluados": evaluados, "iguales": iguales, "con_ajustes": con_ajustes, "errores": errores}


if __name__ == "__main__":
    lista = os.environ.get("DATASET", "mensajes_ejemplo.json,mensajes_dificiles.json").split(",")
    evaluar([d.strip() for d in lista], pausa=float(os.environ.get("PAUSA", "4")))
