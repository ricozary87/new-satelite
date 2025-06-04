# data_sources/coinglass_fetcher.py

import os
import httpx
from dotenv import load_dotenv
from pathlib import Path

# Load .env
env_path = Path('.') / '.env'
load_dotenv(dotenv_path=env_path)

COINGLASS_API_KEY = os.getenv("COINGLASS_API_KEY")
if not COINGLASS_API_KEY:
    raise ValueError("❌ COINGLASS_API_KEY tidak ditemukan di .env")

print("🔑 Loaded COINGLASS API KEY")

# ✅ FIX: NO v4 in BASE_URL
BASE_URL = "https://open-api-v4.coinglass.com/api"
HEADERS = {
    "accept": "application/json",
    "CG-API-KEY": COINGLASS_API_KEY
}

async def _fetch(endpoint: str, params: dict = None):
    url = f"{BASE_URL}{endpoint}"
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(url, headers=HEADERS, params=params)
            response.raise_for_status()
            data = response.json()

            if data.get("code") != "0":
                print(f"⚠️ API ERROR [{endpoint}]: {data.get('msg')}")
                return []

            return data.get("data", [])

    except httpx.HTTPStatusError as e:
        print(f"❌ HTTP ERROR [{endpoint}]: {e.response.status_code} - {e.response.text}")
        return []
    except Exception as e:
        print(f"❌ EXCEPTION [{endpoint}]: {e}")
        return []

