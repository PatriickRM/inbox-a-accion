# Bitácora de iteraciones

Modelo: gemini-3.5-flash-lite | Dataset: 12 mensajes | temperature=0

| Versión | Qué probé | Qué falló | Qué cambié | Resultado |
|---|---|---|---|---|
| v1 | Prompt base con 1 ejemplo | Leyó el enojo como urgencia alta (#4) | Definir cada nivel de urgencia y aclarar que el tono no cuenta | Tipo 12/12, urgencia 11/12 |
| v2 | Definiciones de urgencia por nivel | #5: una queja con amenaza de reclamo formal quedó en media. #6: login bloqueado quedó en media | Agregar amenaza de escalar (reclamo, denuncia, cancelación) como criterio de urgencia alta | Tipo 12/12, urgencia 10/12 |
| v3 | Regla de escalamiento | Nada en este dataset | Ninguno | Tipo 12/12, urgencia 12/12 |

## Notas
- La etiqueta de #6 estaba mal puesta (media). Un login bloqueado cumple mi propia definición de urgencia alta, así que la corregí. Antes de corregirla, v1 y v2 daban 10/12 y 11/12, y v3 daba 11/12.
- Fijé temperature=0 porque #6 oscilaba entre versiones. Los números de arriba se midieron todos con las etiquetas corregidas y temperature=0.
- Límite: v3 se diseñó mirando estos mismos 12 mensajes. El 12/12 no prueba que generalice. Siguiente paso: evaluarlo con mensajes nuevos sin modificarlo.
