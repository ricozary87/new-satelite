# File: logic_engine/analyzers/classic_indicators.py
# Tujuan: Menghitung berbagai indikator teknikal klasik dari data OHLCV.

import pandas as pd
import numpy as np
import logging
import ta # Library untuk indikator teknikal

logger = logging.getLogger(__name__)

def calculate_indicators(df: pd.DataFrame) -> dict:
    """
    Menghitung berbagai indikator teknikal klasik.

    Args:
        df (pd.DataFrame): DataFrame yang berisi data OHLCV dengan kolom 'open', 'high', 'low', 'close', 'volume'.

    Returns:
        dict: Kamus berisi nilai-nilai indikator. Mengembalikan dictionary kosong jika DataFrame tidak valid.
    """
    indicators = {}

    # --- Validasi DataFrame Input ---
    if df.empty:
        logger.error("DataFrame kosong, tidak dapat menghitung indikator.")
        return {} # Mengembalikan kamus kosong jika DataFrame kosong

    required_cols = ['open', 'high', 'low', 'close', 'volume']
    for col in required_cols:
        if col not in df.columns:
            logger.error(f"DataFrame tidak memiliki kolom yang dibutuhkan: '{col}'. Tidak dapat menghitung indikator.")
            return {} # Mengembalikan kamus kosong jika kolom yang dibutuhkan tidak ada
        # Pastikan kolom adalah tipe numerik
        if not pd.api.types.is_numeric_dtype(df[col]):
            logger.warning(f"Kolom '{col}' bukan tipe numerik. Mengonversi...")
            df[col] = pd.to_numeric(df[col], errors='coerce')
            if df[col].isnull().any():
                logger.error(f"Kolom '{col}' berisi nilai non-numerik setelah konversi. Tidak dapat menghitung indikator.")
                return {} # Mengembalikan kamus kosong jika konversi gagal

    # Pastikan ada cukup data untuk perhitungan (misalnya, untuk MA 20 hari, butuh setidaknya 20 data)
    if len(df) < 20: # Ambil nilai minimum untuk MA atau indikator lain yang paling membutuhkan data
        logger.warning(f"Jumlah data ({len(df)} baris) tidak cukup untuk perhitungan beberapa indikator. Membutuhkan minimal 20 baris.")
        # Kita akan tetap mencoba menghitung yang memungkinkan, tapi beberapa mungkin NaN.

    # --- Perhitungan Indikator ---

    # 1. Moving Averages (EMA)
    try:
        df['EMA_20'] = ta.trend.ema_indicator(df['close'], window=20, fillna=True)
        df['EMA_50'] = ta.trend.ema_indicator(df['close'], window=50, fillna=True)
        df['EMA_200'] = ta.trend.ema_indicator(df['close'], window=200, fillna=True) # Perlu candle_limit > 200
        
        # Sinyal EMA (berdasarkan crossover EMA 20 dan 50)
        if len(df) >= 50: # Pastikan ada cukup data untuk EMA_50
            if df['EMA_20'].iloc[-1] > df['EMA_50'].iloc[-1] and df['EMA_20'].iloc[-2] <= df['EMA_50'].iloc[-2]:
                indicators['ema_signal'] = "bullish_crossover"
            elif df['EMA_20'].iloc[-1] < df['EMA_50'].iloc[-1] and df['EMA_20'].iloc[-2] >= df['EMA_50'].iloc[-2]:
                indicators['ema_signal'] = "bearish_crossover"
            elif df['EMA_20'].iloc[-1] > df['EMA_50'].iloc[-1]:
                indicators['ema_signal'] = "bullish"
            else:
                indicators['ema_signal'] = "bearish"
        else:
            indicators['ema_signal'] = "N/A_not_enough_data"
            logger.warning("Tidak cukup data untuk sinyal EMA 20/50.")

        indicators['EMA_20'] = df['EMA_20'].iloc[-1]
        indicators['EMA_50'] = df['EMA_50'].iloc[-1]
        if len(df) >= 200:
            indicators['EMA_200'] = df['EMA_200'].iloc[-1]
        else:
            indicators['EMA_200'] = np.nan # Set NaN jika tidak cukup data

    except Exception as e:
        logger.error(f"Gagal menghitung EMA atau sinyal EMA: {e}")
        indicators['EMA_20'], indicators['EMA_50'], indicators['EMA_200'], indicators['ema_signal'] = np.nan, np.nan, np.nan, "error"

    # 2. Relative Strength Index (RSI)
    try:
        indicators['RSI'] = ta.momentum.rsi(df['close'], window=14, fillna=True).iloc[-1]
        if indicators['RSI'] > 70:
            indicators['rsi_signal'] = "overbought"
        elif indicators['RSI'] < 30:
            indicators['rsi_signal'] = "oversold"
        else:
            indicators['rsi_signal'] = "normal"
    except Exception as e:
        logger.error(f"Gagal menghitung RSI atau sinyal RSI: {e}")
        indicators['RSI'], indicators['rsi_signal'] = np.nan, "error"

    # 3. MACD
    try:
        macd_indicator = ta.trend.MACD(df['close'], window_fast=12, window_slow=26, window_sign=9, fillna=True)
        df['MACD'] = macd_indicator.macd()
        df['MACD_Signal'] = macd_indicator.macd_signal()
        df['MACD_Hist'] = macd_indicator.macd_diff()

        indicators['MACD'] = df['MACD'].iloc[-1]
        indicators['MACD_Signal'] = df['MACD_Signal'].iloc[-1]
        indicators['MACD_Hist'] = df['MACD_Hist'].iloc[-1]

        # Sinyal MACD
        if len(df) >= 26: # Pastikan ada cukup data untuk MACD
            if df['MACD'].iloc[-1] > df['MACD_Signal'].iloc[-1] and df['MACD'].iloc[-2] <= df['MACD_Signal'].iloc[-2]:
                indicators['macd_signal'] = "bullish_crossover"
                indicators['macd_trend'] = "bullish"
            elif df['MACD'].iloc[-1] < df['MACD_Signal'].iloc[-1] and df['MACD'].iloc[-2] >= df['MACD_Signal'].iloc[-2]:
                indicators['macd_signal'] = "bearish_crossover"
                indicators['macd_trend'] = "bearish"
            elif df['MACD'].iloc[-1] > df['MACD_Signal'].iloc[-1]:
                indicators['macd_trend'] = "bullish"
                indicators['macd_signal'] = "bullish"
            elif df['MACD'].iloc[-1] < df['MACD_Signal'].iloc[-1]:
                indicators['macd_trend'] = "bearish"
                indicators['macd_signal'] = "bearish"
            else:
                indicators['macd_trend'] = "neutral"
                indicators['macd_signal'] = "neutral"
        else:
            indicators['macd_signal'] = "N/A_not_enough_data"
            indicators['macd_trend'] = "N/A_not_enough_data"
            logger.warning("Tidak cukup data untuk sinyal MACD.")

    except Exception as e:
        logger.error(f"Gagal menghitung MACD atau sinyal MACD: {e}")
        indicators['MACD'], indicators['MACD_Signal'], indicators['MACD_Hist'], indicators['macd_signal'], indicators['macd_trend'] = np.nan, np.nan, np.nan, "error", "error"

    # 4. Bollinger Bands (BB)
    try:
        bb_indicator = ta.volatility.BollingerBands(df['close'], window=20, window_dev=2, fillna=True)
        df['BB_middle'] = bb_indicator.bollinger_mavg()
        df['BB_upper'] = bb_indicator.bollinger_hband()
        df['BB_lower'] = bb_indicator.bollinger_lband()

        indicators['BB_middle'] = df['BB_middle'].iloc[-1]
        indicators['BB_upper'] = df['BB_upper'].iloc[-1]
        indicators['BB_lower'] = df['BB_lower'].iloc[-1]

        # Sinyal BB (sederhana)
        if len(df) >= 20: # Pastikan ada cukup data untuk BB
            last_close = df['close'].iloc[-1]
            prev_close = df['close'].iloc[-2]
            
            if last_close > indicators['BB_middle'] and prev_close <= indicators['BB_middle']:
                indicators['bb_signal'] = "cross_above_middle"
            elif last_close < indicators['BB_middle'] and prev_close >= indicators['BB_middle']:
                indicators['bb_signal'] = "cross_below_middle"
            elif last_close < indicators['BB_lower']:
                indicators['bb_signal'] = "outside_lower_band"
            elif last_close > indicators['BB_upper']:
                indicators['bb_signal'] = "outside_upper_band"
            elif last_close > indicators['BB_lower'] and prev_close < indicators['BB_lower']:
                indicators['bb_signal'] = "bounce_from_lower"
            elif last_close < indicators['BB_upper'] and prev_close > indicators['BB_upper']:
                indicators['bb_signal'] = "bounce_from_upper"
            else:
                indicators['bb_signal'] = "normal"
        else:
            indicators['bb_signal'] = "N/A_not_enough_data"
            logger.warning("Tidak cukup data untuk sinyal Bollinger Bands.")

    except Exception as e:
        logger.error(f"Gagal menghitung Bollinger Bands atau sinyal BB: {e}")
        indicators['BB_middle'], indicators['BB_upper'], indicators['BB_lower'], indicators['bb_signal'] = np.nan, np.nan, np.nan, "error"
    
    # 5. Stochastic RSI (Stoch RSI)
    try:
        stoch_rsi_indicator = ta.momentum.StochRSI(df['close'], window=14, smooth1=3, smooth2=3, fillna=True)
        df['StochRSI_K'] = stoch_rsi_indicator.stochrsi_k()
        df['StochRSI_D'] = stoch_rsi_indicator.stochrsi_d()
        
        indicators['StochRSI_K'] = df['StochRSI_K'].iloc[-1]
        indicators['StochRSI_D'] = df['StochRSI_D'].iloc[-1]

        # Sinyal Stoch RSI
        if len(df) >= 14: # StochRSI membutuhkan RSI, yang membutuhkan 14 candle
            # Pastikan nilai tidak NaN (terjadi jika ada NaN di close atau data tidak cukup)
            if not np.isnan(indicators['StochRSI_K']) and not np.isnan(indicators['StochRSI_D']):
                if indicators['StochRSI_K'] > indicators['StochRSI_D'] and df['StochRSI_K'].iloc[-2] <= df['StochRSI_D'].iloc[-2]:
                    if indicators['StochRSI_K'] < 20:
                        indicators['stoch_signal'] = "oversold_bullish_cross"
                    else:
                        indicators['stoch_signal'] = "bullish_crossover"
                elif indicators['StochRSI_K'] < indicators['StochRSI_D'] and df['StochRSI_K'].iloc[-2] >= df['StochRSI_D'].iloc[-2]:
                    if indicators['StochRSI_K'] > 80:
                        indicators['stoch_signal'] = "overbought_bearish_cross"
                    else:
                        indicators['stoch_signal'] = "bearish_crossover"
                elif indicators['StochRSI_K'] > 80:
                    indicators['stoch_signal'] = "overbought"
                elif indicators['StochRSI_K'] < 20:
                    indicators['stoch_signal'] = "oversold"
                else:
                    indicators['stoch_signal'] = "normal"
            else:
                indicators['stoch_signal'] = "N/A_nan_values"
                logger.warning("Stoch RSI menghasilkan NaN, sinyal tidak tersedia.")
        else:
            indicators['stoch_signal'] = "N/A_not_enough_data"
            logger.warning("Tidak cukup data untuk sinyal Stoch RSI.")

    except Exception as e:
        logger.error(f"Gagal menghitung Stoch RSI atau sinyal Stoch RSI: {e}")
        indicators['StochRSI_K'], indicators['StochRSI_D'], indicators['stoch_signal'] = np.nan, np.nan, "error"


    logger.info("Perhitungan indikator klasik selesai.")
    return indicators

# --- Contoh Penggunaan (untuk pengujian mandiri modul ini) ---
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

    # Membuat DataFrame dummy untuk pengujian
    # Harus memiliki setidaknya 200 baris untuk EMA_200, atau sesuaikan candle_limit di analyzer_entry
    # Jika menggunakan 100 candle, EMA_200 akan NaN.
    dummy_data = {
        'open': np.random.rand(300) * 1000 + 50000,
        'high': np.random.rand(300) * 1000 + 50500,
        'low': np.random.rand(300) * 1000 + 49500,
        'close': np.random.rand(300) * 1000 + 50000,
        'volume': np.random.rand(300) * 10000 + 1000
    }
    dummy_df = pd.DataFrame(dummy_data)
    dummy_df.index = pd.to_datetime(pd.date_range(start='2023-01-01', periods=300, freq='h'))

    print("\n--- Menguji calculate_indicators dengan data lengkap ---")
    calculated_indicators = calculate_indicators(dummy_df.copy())
    for key, value in calculated_indicators.items():
        if isinstance(value, (int, float)):
            print(f"{key}: {value:.2f}")
        else:
            print(f"{key}: {value}")

    print("\n--- Menguji calculate_indicators dengan DataFrame kosong ---")
    empty_df = pd.DataFrame()
    calculated_indicators_empty = calculate_indicators(empty_df)
    print(f"Hasil: {calculated_indicators_empty}")

    print("\n--- Menguji calculate_indicators dengan kolom hilang ('close' hilang) ---")
    missing_col_df = dummy_df.drop(columns=['close']).copy()
    calculated_indicators_missing_col = calculate_indicators(missing_col_df)
    print(f"Hasil: {calculated_indicators_missing_col}")

    print("\n--- Menguji calculate_indicators dengan data tidak cukup (10 baris) ---")
    not_enough_data_df = dummy_df.iloc[:10].copy()
    calculated_indicators_not_enough = calculate_indicators(not_enough_data_df)
    for key, value in calculated_indicators_not_enough.items():
        if isinstance(value, (int, float)):
            print(f"{key}: {value:.2f}")
        else:
            print(f"{key}: {value}")
