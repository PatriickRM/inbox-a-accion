# Bitácora de iteraciones

Modelo: gemini-3.5-flash-lite | Dataset: 12 mensajes

| Versión | Qué probé | Qué falló | Qué cambié | Resultado |
|---|---|---|---|---|
| v1 | Prompt base con 1 ejemplo | Leyó el enojo como urgencia alta (#4) y un login fallido como alta (#6) | Definir cada nivel de urgencia y aclarar que el tono no cuenta | Tipo 12/12, urgencia 10/12 |
| v2 | Definiciones de urgencia por nivel | Regresión en #5: una queja con amenaza de reclamo formal bajó a media, porque mi regla ignoraba el riesgo de escalamiento | Agregar amenaza de escalar (reclamo, denuncia, cancelación) como criterio de urgencia alta | Tipo 12/12, urgencia 11/12 |
| v3 | (completa tras evaluar) | | | |
