"""Mide el porcentaje de aciertos del clasificador contra el dataset de ejemplo.

Uso (desde la raiz del repo):
    python tests\\evaluar.py
"""
import json
import os
import time
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "api"))

from clasificador import clasificar  # noqa: E402

datos = json.loads((Path(__file__).parent / "mensajes_ejemplo.json").read_text(encoding="utf-8"))

aciertos_tipo = 0
aciertos_urg = 0
fallos = []

for i, caso in enumerate(datos, start=1):
    time.sleep(float(os.environ.get('PAUSA', '4')))
    try:
        res = clasificar(caso["mensaje"])
    except Exception as e:
        print(f"{i:>2}. ERROR: {e}")
        fallos.append((i, caso["mensaje"], "error", "-"))
        continue

    ok_tipo = res.tipo == caso["tipo"]
    ok_urg = res.urgencia == caso["urgencia"]
    aciertos_tipo += ok_tipo
    aciertos_urg += ok_urg
    marca = "OK " if ok_tipo and ok_urg else "XX "
    print(f"{i:>2}. {marca} esperado={caso['tipo']}/{caso['urgencia']}  obtenido={res.tipo}/{res.urgencia}")
    if not (ok_tipo and ok_urg):
        fallos.append((i, caso["mensaje"], f"{res.tipo}/{res.urgencia}", f"{caso['tipo']}/{caso['urgencia']}"))

total = len(datos)
print()
print(f"Tipo correcto:    {aciertos_tipo}/{total}")
print(f"Urgencia correcta: {aciertos_urg}/{total}")

if fallos:
    print("\nFallos (para la bitacora):")
    for n, msg, obtenido, esperado in fallos:
        print(f"- #{n}: obtenido {obtenido}, esperado {esperado} -> {msg[:70]}")


