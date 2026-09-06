import os

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/shipping", tags=["shipping"])

MELHOR_ENVIO_TOKEN = os.getenv("MELHOR_ENVIO_TOKEN", "")
MELHOR_ENVIO_URL = "https://melhorenvio.com.br/api/v2/me/shipment/calculate"
ORIGIN_CEP = "08576230"

ITEM_HEIGHT = 10
ITEM_WIDTH = 12
ITEM_LENGTH = 17
ITEM_WEIGHT_KG = 0.2


class ShippingRequest(BaseModel):
    cep: str
    quantity: int = 1


@router.post("/calculate")
async def calculate_shipping(payload: ShippingRequest):
    if not MELHOR_ENVIO_TOKEN:
        raise HTTPException(500, "Token do Melhor Envio não configurado")

    cep = payload.cep.replace("-", "").replace(".", "").strip()
    if len(cep) != 8 or not cep.isdigit():
        raise HTTPException(400, "CEP inválido")

    qty = max(1, payload.quantity)
    weight = round(qty * ITEM_WEIGHT_KG, 2)

    body = {
        "from": {"postal_code": ORIGIN_CEP},
        "to": {"postal_code": cep},
        "package": {
            "height": ITEM_HEIGHT,
            "width": ITEM_WIDTH,
            "length": ITEM_LENGTH,
            "weight": weight,
        },
        "options": {
            "receipt": False,
            "own_hand": False,
        },
    }

    headers = {
        "Authorization": f"Bearer {MELHOR_ENVIO_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Arpus JDM (samueldesenvolvedor36@gmail.com)",
    }

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(MELHOR_ENVIO_URL, json=body, headers=headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(502, f"Erro ao consultar Melhor Envio: {e.response.text}")
        except Exception as e:
            raise HTTPException(502, f"Erro na consulta de frete: {str(e)}")

    options = []
    for service in data:
        if service.get("error") or service.get("price") is None:
            continue
        options.append({
            "id": service.get("id"),
            "name": service.get("name"),
            "company": service.get("company", {}).get("name", ""),
            "price": float(service["price"]),
            "delivery_time": service.get("delivery_time"),
        })

    options.sort(key=lambda x: x["price"])
    return options
