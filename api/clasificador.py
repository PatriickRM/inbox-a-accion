import json
import os
import time
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types
from pydantic import BaseModel, ValidationError

RAIZ = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ / ".env")

client = genai.Client()  # lee GEMINI_API_KEY del entorno
MODELO = os.getenv("MODELO_LLM", "gemini-3.8-flash")
PROMPT = (RAIZ / "prompts" / f"clasificador_{os.getenv('PROMPT_VERSION', 'v1')}.txt").read_text(encoding="utf-8-sig")


class Caso(BaseModel):
    cliente: str
    tipo: Literal["cotizacion", "soporte", "queja", "consulta", "spam"]
    urgencia: Literal["alta", "media", "baja"]
    resumen: str
    accion_sugerida: str


def _llamar_llm(mensaje: str, intentos: int = 5) -> str:
    """Llama al modelo y reintenta con espera creciente si Google esta saturado."""
    for n in range(intentos):
        try:
            resp = client.models.generate_content(
                model=MODELO,
                contents=mensaje,
                config=types.GenerateContentConfig(
                    system_instruction=PROMPT,
                    response_mime_type="application/json",
                    max_output_tokens=1000,
                    temperature=0,
                ),
            )
            return (resp.text or "").strip()
        except (errors.ServerError, errors.ClientError) as e:
            temporal = isinstance(e, errors.ServerError) or getattr(e, "code", None) == 429
            if not temporal or n == intentos - 1:
                raise
            espera = 2 ** (n + 1)
            print(f"  [aviso] Google saturado, reintento en {espera}s...")
            time.sleep(espera)


def clasificar(mensaje: str, reintentos: int = 2) -> Caso:
    ultimo_error = None
    for _ in range(reintentos + 1):
        texto = _llamar_llm(mensaje)
        texto = texto.replace("```json", "").replace("```", "").strip()
        try:
            return Caso(**json.loads(texto))
        except (json.JSONDecodeError, ValidationError) as e:
            ultimo_error = e
    raise ValueError(f"El LLM no devolvió JSON válido: {ultimo_error}")


if __name__ == "__main__":
    prueba = "Hola, necesito una cotización para automatizar mi facturación."
    print(clasificar(prueba).model_dump_json(indent=2))


