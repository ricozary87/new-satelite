from fastapi import FastAPI, Header, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from logic_engine.signal_builder import generate_trading_signal
import logging

# === SETUP LOGGER ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("GPT-S API")

# === FASTAPI INIT ===
app = FastAPI(
    title="GPT-S Smart Market Entry Analyzer API",
    description="API untuk menghasilkan sinyal trading kripto berdasarkan analisis konfluensi SMC, indikator klasik, volume delta, orderbook, dan data on-chain Solana.",
    version="1.0.0"
)

# === API KEY SETUP ===
# Untuk lingkungan produksi, sebaiknya API_KEY diambil dari environment variables
# import os
# API_KEY = os.getenv("GPTS_API_KEY", "your_default_secure_key_here")
API_KEY = "GPTS_SECRET_2024"

# Dependency untuk validasi API Key
async def verify_api_key(authorization: str = Header(...)):
    if authorization != f"Bearer {API_KEY}":
        logger.warning(f"Unauthorized access attempt with token: {authorization}")
        raise HTTPException(status_code=401, detail="Unauthorized: Invalid API Key")
    return True

# === REQUEST MODELS (Refleksi dari Skema OpenAPI yang Sempurna) ===

# Sub-models untuk struktur data yang lebih detail
class IndicatorsData(BaseModel):
    ema_signal: str
    rsi_signal: str
    rsi_divergence: str
    macd_crossover_signal: str
    bb_signal: str
    stoch_signal: str

class SmcData(BaseModel):
    swing_points: Dict[str, Any] # Bisa didetailkan lebih lanjut jika diperlukan
    bos_choch: Dict[str, Any]
    fvg: Dict[str, Any]
    eq_zone: Dict[str, Any]
    order_block: Dict[str, Any]

class VolumeDeltaData(BaseModel):
    current_delta: float
    cvd_trend: str

class OrderbookData(BaseModel):
    bid_wall: Optional[float] = None
    ask_wall: Optional[float] = None
    imbalance_ratio: float
    spoofing_detected: Optional[bool] = None

class OnChainData(BaseModel):
    whale_movement: str
    smart_money_net_flow: float
    significant_transactions: Optional[list[Dict[str, Any]]] = None

class MacroData(BaseModel):
    funding_rate: float
    open_interest_change: str
    news_sentiment: Optional[str] = None

# Model utama untuk permintaan analisis
class AnalysisRequest(BaseModel):
    symbol: str = Field(..., example="BTCUSDT")
    timeframe: str = Field(..., example="5m")
    indicators: IndicatorsData
    smc: SmcData
    volume_delta: VolumeDeltaData
    orderbook: OrderbookData
    on_chain: Optional[OnChainData] = None # Opsional
    macro_data: Optional[MacroData] = None # Opsional

# Model untuk respons sinyal trading (sesuai skema OpenAPI)
class TradingSignalResponse(BaseModel):
    signal: str = Field(..., example="BUY")
    entry: Optional[float] = Field(None, example=20700.0)
    stop_loss: Optional[float] = Field(None, example=20550.0)
    take_profit_1: Optional[float] = Field(None, example=20850.0)
    take_profit_2: Optional[float] = Field(None, example=21000.0)
    take_profit_3: Optional[float] = Field(None, example=21200.0)
    reason: str = Field(..., example="Konfluensi kuat: Bullish BOS, FVG terisi sebagian, Order Block belum dimitigasi, Volume Delta positif, dan pergerakan whale mendukung.")
    confidence_score: Optional[float] = Field(None, example=0.85, description="Skor kepercayaan sinyal (0-1).")

# === ENDPOINT ===
@app.post(
    "/generate_signal",
    response_model=TradingSignalResponse, # Menentukan model respons untuk validasi & dokumentasi
    summary="Bangun sinyal trading dari data analisa yang komprehensif",
    dependencies=[Depends(verify_api_key)] # Menerapkan API Key verification
)
def generate_signal_endpoint(data: AnalysisRequest):
    logger.info(f"🔍 Analyzing signal for {data.symbol} ({data.timeframe}) with full data.")

    # Panggil fungsi generate_trading_signal dengan semua data yang relevan
    signal_result = generate_trading_signal(
        symbol=data.symbol,
        timeframe=data.timeframe,
        classic_indicators=data.indicators.dict(), # Pastikan ini diubah ke dict jika generate_trading_signal menerimanya demikian
        smc_signals=data.smc.dict(),
        volume_delta_data=data.volume_delta.dict(),
        orderbook_data=data.orderbook.dict(),
        on_chain_data=data.on_chain.dict() if data.on_chain else None,
        macro_data=data.macro_data.dict() if data.macro_data else None
    )

    logger.info(f"✅ Signal generated for {data.symbol}: {signal_result['signal']}")

    # FastAPI akan otomatis mengubah dict ke JSON dan memvalidasi dengan response_model
    return signal_result
