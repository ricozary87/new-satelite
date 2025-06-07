# File: logic_engine/signals/signal_builder.py
# Tujuan: Membangun rencana sinyal trading berdasarkan berbagai input analisis.

import logging
import pandas as pd
import numpy as np

# Impor dari lokasi baru
from ..analyzers.classic_indicators import calculate_indicators # Contoh impor jika diperlukan
from ..analyzers.smc_structure import analyze_smc_structure   # Contoh impor jika diperlukan
from ..confluence_checker import evaluate_market_confluence # Contoh impor jika diperlukan

logger = logging.getLogger(__name__)

def generate_trading_signal(
    symbol: str,
    timeframe: str,
    classic_indicators: dict,
    smc_signals: dict,
    df: pd.DataFrame,
    current_price: float,
    current_open_price: float,
    confluence_result: dict # Sekarang menerima hasil konfluensi
) -> dict:
    """
    Membangun rencana sinyal trading berdasarkan analisis yang dilakukan.

    Args:
        symbol (str): Simbol pasangan perdagangan.
        timeframe (str): Timeframe analisis.
        classic_indicators (dict): Hasil dari analisis indikator klasik.
        smc_signals (dict): Hasil dari analisis struktur SMC.
        df (pd.DataFrame): DataFrame OHLCV yang digunakan untuk analisis.
        current_price (float): Harga penutupan candle saat ini.
        current_open_price (float): Harga pembukaan candle saat ini.
        confluence_result (dict): Hasil dari evaluasi konfluensi.

    Returns:
        dict: Kamus yang berisi rencana sinyal trading (misalnya, 'signal', 'entry', 'stop_loss', 'take_profit', 'reason').
    """
    logger.info(f"Membangun sinyal trading untuk {symbol} di {timeframe}...")

    signal = "HOLD"
    entry_price = current_price
    stop_loss = None
    take_profit = None
    signal_reason = ["No clear signal generated."]
    risk_reward_ratio = None

    overall_sentiment = confluence_result.get("overall_sentiment", "NEUTRAL")
    confluence_reasons = confluence_result.get("signals", [])

    logger.info(f"Sentimen konfluensi keseluruhan: {overall_sentiment}")

    # Contoh logika sinyal sederhana berdasarkan sentimen konfluensi
    if overall_sentiment == "BULLISH":
        signal = "BUY"
        signal_reason = ["Strong bullish confluence detected."] + confluence_reasons
        
        # Contoh penentuan SL/TP (perlu disesuaikan dengan strategi nyata)
        # Ambil harga terendah dari beberapa candle terakhir untuk SL
        # Asumsi df memiliki kolom 'low'
        if not df.empty:
            lows = df['low'].iloc[-5:-1].min() # Low 4 candle sebelumnya
            stop_loss = max(lows * 0.99, current_price * 0.98) # Misal 1-2% di bawah harga saat ini atau di bawah low sebelumnya

            # Take profit berdasarkan TP/SL simetris atau resistance terdekat
            take_profit = current_price * 1.02 # Target 2% keuntungan

        logger.info(f"Sinyal BUY dihasilkan. Entry: {entry_price}, SL: {stop_loss}, TP: {take_profit}")

    elif overall_sentiment == "BEARISH":
        signal = "SELL"
        signal_reason = ["Strong bearish confluence detected."] + confluence_reasons
        
        if not df.empty:
            highs = df['high'].iloc[-5:-1].max() # High 4 candle sebelumnya
            stop_loss = min(highs * 1.01, current_price * 1.02) # Misal 1-2% di atas harga saat ini atau di atas high sebelumnya

            take_profit = current_price * 0.98 # Target 2% keuntungan

        logger.info(f"Sinyal SELL dihasilkan. Entry: {entry_price}, SL: {stop_loss}, TP: {take_profit}")

    elif overall_sentiment == "CONFLICTING":
        signal = "HOLD"
        signal_reason = ["Conflicting signals detected. Advise to wait for clearer market direction."] + confluence_reasons
        logger.warning("Sinyal konflik terdeteksi. Disarankan untuk HOLD.")

    else: # NEUTRAL atau NO_DATA
        signal = "HOLD"
        signal_reason = ["Market is neutral or no strong signals detected."] + confluence_reasons
        logger.info("Tidak ada sinyal kuat, disarankan untuk HOLD.")

    # Hitung Risk-Reward Ratio jika SL dan TP tersedia
    if stop_loss is not None and take_profit is not None:
        if signal == "BUY":
            risk = abs(entry_price - stop_loss)
            reward = abs(take_profit - entry_price)
        elif signal == "SELL":
            risk = abs(stop_loss - entry_price)
            reward = abs(entry_price - take_profit)
        else:
            risk = 0
            reward = 0

        if risk > 0:
            risk_reward_ratio = reward / risk
            logger.info(f"Risk-Reward Ratio: {risk_reward_ratio:.2f}")
        else:
            risk_reward_ratio = float('inf') if reward > 0 else 0.0 # Jika risk 0, reward bisa sangat tinggi
            logger.warning("Risk calculation resulted in zero. Check stop loss logic.")


    plan = {
        "signal": signal,
        "symbol": symbol,
        "timeframe": timeframe,
        "entry_price": f"{entry_price:.4f}" if entry_price is not None else "N/A",
        "stop_loss": f"{stop_loss:.4f}" if stop_loss is not None else "N/A",
        "take_profit": f"{take_profit:.4f}" if take_profit is not None else "N/A",
        "risk_reward_ratio": f"{risk_reward_ratio:.2f}" if risk_reward_ratio is not None else "N/A",
        "reason": signal_reason, # List of strings
        "confluence_sentiment": overall_sentiment,
        "current_price": f"{current_price:.4f}"
    }
    return plan

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Contoh data dummy untuk pengujian
    dummy_df = pd.DataFrame({
        'open': [100, 102, 101, 103, 105],
        'high': [103, 105, 103, 106, 108],
        'low': [98, 100, 99, 101, 103],
        'close': [102, 101, 103, 105, 107],
        'volume': [1000, 1200, 1100, 1300, 1500]
    }, index=pd.to_datetime(pd.date_range(start='2023-01-01', periods=5, freq='h')))

    # Skenario Bullish
    confluence_bullish = {
        "overall_sentiment": "BULLISH",
        "signals": ["EMA: Bullish Trend", "MACD: Bullish Momentum", "SMC: Bullish CHoCH Detected"]
    }
    signal_plan_buy = generate_trading_signal(
        symbol="BTCUSDT",
        timeframe="1h",
        classic_indicators={"RSI": 60, "ema_signal": "bullish"},
        smc_signals={"bos_choch": {"type": "bullish_choch"}},
        df=dummy_df,
        current_price=dummy_df['close'].iloc[-1],
        current_open_price=dummy_df['open'].iloc[-1],
        confluence_result=confluence_bullish
    )
    print("\n--- Sinyal BELI ---")
    for k, v in signal_plan_buy.items():
        print(f"{k}: {v}")

    # Skenario Bearish
    confluence_bearish = {
        "overall_sentiment": "BEARISH",
        "signals": ["EMA: Bearish Trend", "Funding Rate: Negative (Bearish Sentiment)"]
    }
    signal_plan_sell = generate_trading_signal(
        symbol="ETHUSDT",
        timeframe="4h",
        classic_indicators={"RSI": 40, "ema_signal": "bearish"},
        smc_signals={"bos_choch": {"type": "bearish_choch"}},
        df=dummy_df, # Menggunakan dummy_df yang sama untuk contoh
        current_price=dummy_df['close'].iloc[-1],
        current_open_price=dummy_df['open'].iloc[-1],
        confluence_result=confluence_bearish
    )
    print("\n--- Sinyal JUAL ---")
    for k, v in signal_plan_sell.items():
        print(f"{k}: {v}")

    # Skenario Neutral
    confluence_neutral = {
        "overall_sentiment": "NEUTRAL",
        "signals": ["No clear dominant confluence signal detected."]
    }
    signal_plan_hold = generate_trading_signal(
        symbol="XRPUSDT",
        timeframe="1d",
        classic_indicators={"RSI": 50, "ema_signal": "neutral"},
        smc_signals={"bos_choch": {"type": "no_break"}},
        df=dummy_df,
        current_price=dummy_df['close'].iloc[-1],
        current_open_price=dummy_df['open'].iloc[-1],
        confluence_result=confluence_neutral
    )
    print("\n--- Sinyal HOLD ---")
    for k, v in signal_plan_hold.items():
        print(f"{k}: {v}")
