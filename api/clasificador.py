import json
import os
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, ValidationError

RAIZ = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ / ".env")

client = genai.Client()  # lee GEMINI_API_KEY del entorno
MODELO = os.getenv("MODELO_LLM", "gemini-2.5-flash")
PROMPT = (RAIZ / "prompts" / "clasificador_v1.txt").read_text(encoding="utf-8-sig")


class Caso(BaseModel):
    cliente: str
    tipo: Literal["cotizacion", "soporte", "queja", "consulta", "spam"]
    urgencia: Literal["alta", "media", "baja"]
    resumen: str
    accion_sugerida: str


def clasificar(mensaje: str, reintentos: int = 2) -> Caso:
    ultimo_error = None
    for _ in range(reintentos + 1):
        resp = client.models.generate_content(
            model=MODELO,
            contents=mensaje,
            config=types.GenerateContentConfig(
                system_instruction=PROMPT,
                response_mime_type="application/json",
                max_output_tokens=1000,
            ),
        )
        texto = (resp.text or "").strip()
        texto = texto.replace("```json", "").replace("```", "").strip()
        try:
            return Caso(**json.loads(texto))
        except (json.JSONDecodeError, ValidationError) as e:
            ultimo_error = e
    raise ValueError(f"El LLM no devolvió JSON válido: {ultimo_error}")


if __name__ == "__main__":
    prueba = "Hola, necesito una cotización para automatizar mi facturación."
    print(clasificar(prueba).model_dump_json(indent=2))
