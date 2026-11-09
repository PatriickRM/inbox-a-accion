# Bitácora de iteraciones

Modelo: gemini-3.5-flash-lite | temperature=0

## Dataset de ajuste (12 mensajes)

| Versión | Qué probé | Qué falló | Qué cambié | Resultado |
|---|---|---|---|---|
| v1 | Prompt base con 1 ejemplo | Leyó el enojo como urgencia alta (#4) | Definir cada nivel de urgencia y aclarar que el tono no cuenta | Tipo 12/12, urgencia 11/12 |
| v2 | Definiciones de urgencia por nivel | #5: queja con amenaza de reclamo formal quedó en media. #6: login bloqueado quedó en media | Agregar amenaza de escalar (reclamo, denuncia, cancelación) como criterio de urgencia alta | Tipo 12/12, urgencia 10/12 |
| v3 | Regla de escalamiento | Nada en este dataset | Ninguno | Tipo 12/12, urgencia 12/12 |

## Dataset difícil (8 mensajes nuevos, sin ajustar el prompt)

| Versión | Resultado | Fallos |
|---|---|---|
| v1 | Tipo 8/8, urgencia 8/8 | Ninguno |
| v3 | Tipo 8/8, urgencia 7/8 | #2: cotización + caída recurrente de facturación, obtuvo media y esperaba alta |

## Conclusiones
- Total acumulado: v1 19/20, v3 19/20. Empate: la diferencia de un mensaje no es concluyente.
- v3 mejoró en el dataset con el que se diseñó, pero no mejoró en mensajes nuevos. Las reglas extra pudieron ajustarse demasiado a #4, #5 y #6.
- La etiqueta de #6 estaba mal (media). Un login bloqueado cumple la definición de urgencia alta. La corregí antes de comparar versiones.
- Fijé temperature=0 porque #6 oscilaba entre corridas.
- No creé un v4 solo para arreglar #2: ajustar el prompt a un fallo suelto repetiría el error de v2.
- Limitación: 20 mensajes son pocos. Falta probar casos de escalamiento (reclamos, denuncias, abogados), que es lo que v3 agrega y lo que menos se ha probado.
