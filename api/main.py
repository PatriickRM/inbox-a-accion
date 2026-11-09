import hmac
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from clasificador import clasificar  # noqa: E402  (despues de cargar el .env)

TOKEN = os.getenv("API_TOKEN")
if not TOKEN:
    raise RuntimeError("Falta API_TOKEN en el .env")

app = FastAPI(title="Inbox a Acción")
CASOS: list[dict] = []  # en memoria: se pierde al reiniciar. Luego va a Firestore.


class Entrada(BaseModel):
    mensaje: str = Field(min_length=1, max_length=5000)
    origen: str = "correo"


def verificar_token(x_api_token: str) -> None:
    # compare_digest evita filtrar el token por diferencias de tiempo
    if not hmac.compare_digest(x_api_token.encode(), TOKEN.encode()):
        raise HTTPException(status_code=401, detail="No autorizado")


@app.get("/salud")
def salud():
    return {"estado": "ok"}


@app.post("/procesar")
def procesar(entrada: Entrada, x_api_token: str = Header(default="")):
    verificar_token(x_api_token)
    try:
        caso = clasificar(entrada.mensaje)
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception:
        raise HTTPException(status_code=503, detail="El servicio de IA no está disponible, intenta de nuevo")

    registro = {
        "id": str(uuid.uuid4()),
        **caso.model_dump(),
        "origen": entrada.origen,
        "fecha": datetime.now(timezone.utc).isoformat(),
    }
    CASOS.append(registro)
    # Aqui el agente llamara a las herramientas MCP segun caso.tipo
    return registro


@app.get("/casos")
def listar_casos(x_api_token: str = Header(default="")):
    verificar_token(x_api_token)
    return CASOS
