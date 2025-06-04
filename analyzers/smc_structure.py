import pandas as pd
import numpy as np
import logging
import os # Import os untuk setup_logger

logger = logging.getLogger(__name__)

def find_significant_swing_points(df: pd.DataFrame, min_bars_between_swings: int = 5) -> dict:
    """
    Mendeteksi swing high dan swing low yang lebih signifikan.
    Ini adalah implementasi yang lebih canggih daripada window-based sederhana,
    mencoba mengidentifikasi swing yang lebih "struktural".
    """
    logger.debug(f"Mencari significant swing points dengan min_bars_between_swings: {min_bars_between_swings}")
    
    swing_highs = []
    swing_lows = []
    
    # Deteksi swing points awal menggunakan metode lokal (mirip window, tapi dengan filter)
    # Ini adalah langkah awal untuk menemukan titik balik potensial
    is_swing_high = df['high'] == df['high'].rolling(window=min_bars_between_swings*2 + 1, center=True).max()
    is_swing_low = df['low'] == df['low'].rolling(window=min_bars_between_swings*2 + 1, center=True).min()

    potential_highs = df[is_swing_high].index.tolist()
    potential_lows = df[is_swing_low].index.tolist()

    last_swing_type = None # Untuk memastikan swing bergantian (H-L-H-L)
    last_swing_idx = None

    all_potential_swings = sorted(potential_highs + potential_lows)

    for current_idx in all_potential_swings:
        current_candle = df.loc[current_idx]
        is_current_high = current_idx in potential_highs
        is_current_low = current_idx in potential_lows

        if last_swing_idx is None:
            # Inisialisasi swing pertama
            if is_current_high:
                swing_highs.append(current_idx)
                last_swing_type = 'high'
            elif is_current_low:
                swing_lows.append(current_idx)
                last_swing_type = 'low'
            last_swing_idx = current_idx
            continue

        # Filter untuk memastikan swing bergantian dan ada jarak minimal
        if (current_idx - last_swing_idx).total_seconds() / (df.index[1] - df.index[0]).total_seconds() < min_bars_between_swings:
            # Terlalu dekat, abaikan atau perbarui jika swing saat ini lebih ekstrem
            if is_current_high and last_swing_type == 'high' and current_candle['high'] > df.loc[last_swing_idx]['high']:
                swing_highs[-1] = current_idx # Perbarui swing high
                last_swing_idx = current_idx
            elif is_current_low and last_swing_type == 'low' and current_candle['low'] < df.loc[last_swing_idx]['low']:
                swing_lows[-1] = current_idx # Perbarui swing low
                last_swing_idx = current_idx
            continue

        if is_current_high and last_swing_type != 'high':
            swing_highs.append(current_idx)
            last_swing_type = 'high'
            last_swing_idx = current_idx
        elif is_current_low and last_swing_type != 'low':
            swing_lows.append(current_idx)
            last_swing_type = 'low'
            last_swing_idx = current_idx
    
    logger.debug(f"Total significant swing high terdeteksi: {len(swing_highs)}")
    logger.debug(f"Total significant swing low terdeteksi: {len(swing_lows)}")
    return {"swing_highs": swing_highs, "swing_lows": swing_lows}


def detect_bos_choch(df: pd.DataFrame, swing_points: dict, min_break_threshold: float = 0.0001) -> dict:
    """
    Mendeteksi Break of Structure (BOS) atau Change of Character (CHoCH) dengan logika yang lebih ketat.
    Mempertimbangkan penutupan harga di atas/bawah swing high/low sebelumnya.
    Juga mencoba menentukan bias struktural.
    """
    logger.debug("--- DEBUG: detect_bos_choch ---")
    bos_info = {"type": "no_signal", "level": None, "direction": None, "timestamp": None, "current_bias": "ranging"}

    current_candle_time = df.index[-1]
    current_close = df['close'].iloc[-1]

    # Filter swing points yang terjadi sebelum candle saat ini
    relevant_highs_timestamps = [ts for ts in swing_points['swing_highs'] if ts < current_candle_time]
    relevant_lows_timestamps = [ts for ts in swing_points['swing_lows'] if ts < current_candle_time]

    if len(relevant_highs_timestamps) < 2 or len(relevant_lows_timestamps) < 2:
        logger.debug("Tidak cukup swing points relevan (minimal 2 high dan 2 low) untuk BOS/CHoCH.")
        return bos_info

    # Identifikasi swing terakhir
    last_swing_high_time = relevant_highs_timestamps[-1]
    second_last_swing_high_time = relevant_highs_timestamps[-2]
    last_swing_low_time = relevant_lows_timestamps[-1]
    second_last_swing_low_time = relevant_lows_timestamps[-2]

    last_swing_high_price = df.loc[last_swing_high_time]['high']
    second_last_swing_high_price = df.loc[second_last_swing_high_time]['high']
    last_swing_low_price = df.loc[last_swing_low_time]['low']
    second_last_swing_low_price = df.loc[second_last_swing_low_time]['low']
    
    logger.debug(f"Last Swing High: {last_swing_high_price:.4f} (at {last_swing_high_time})")
    logger.debug(f"2nd Last Swing High: {second_last_swing_high_price:.4f} (at {second_last_swing_high_time})")
    logger.debug(f"Last Swing Low: {last_swing_low_price:.4f} (at {last_swing_low_time})")
    logger.debug(f"2nd Last Swing Low: {second_last_swing_low_price:.4f} (at {second_last_swing_low_time})")
    logger.debug(f"Current Close: {current_close:.4f}")

    # Menentukan Bias Pasar (Market Structure Bias)
    # Ini adalah penentuan bias yang lebih robust, bukan hanya dari 2 swing terakhir.
    # Jika kita punya serangkaian Higher Highs (HH) dan Higher Lows (HL) -> Bullish
    # Jika kita punya serangkaian Lower Lows (LL) dan Lower Highs (LH) -> Bearish
    
    # Pendekatan sederhana untuk bias: Bandingkan 2 swing high terakhir dan 2 swing low terakhir
    is_bullish_structure = (last_swing_high_price > second_last_swing_high_price) and \
                           (last_swing_low_price > second_last_swing_low_price)
    is_bearish_structure = (last_swing_high_price < second_last_swing_high_price) and \
                           (last_swing_low_price < second_last_swing_low_price)
    
    if is_bullish_structure:
        bos_info['current_bias'] = 'bullish'
    elif is_bearish_structure:
        bos_info['current_bias'] = 'bearish'
    else:
        bos_info['current_bias'] = 'ranging' # Atau Complex/Indecisive

    logger.debug(f"Current Market Bias: {bos_info['current_bias']}")

    # Deteksi BOS/CHoCH
    # Ambang batas untuk penutupan di luar swing point agar dianggap valid
    
    # Bullish Break (Harga menembus ke atas swing high terakhir)
    if current_close > last_swing_high_price * (1 + min_break_threshold):
        if bos_info['current_bias'] == "bullish":
            bos_info.update({"type": "bullish_bos", "level": float(last_swing_high_price), 
                             "direction": "up", "timestamp": current_candle_time})
            logger.debug(f"Bullish BOS Ditemukan (Konfirmasi Tren Naik): {last_swing_high_price:.4f}")
        elif bos_info['current_bias'] in ["bearish", "ranging"]:
            bos_info.update({"type": "bullish_choch", "level": float(last_swing_high_price), 
                             "direction": "up", "timestamp": current_candle_time})
            logger.debug(f"Bullish CHoCH Ditemukan (Potensi Pembalikan Tren): {last_swing_high_price:.4f}")

    # Bearish Break (Harga menembus ke bawah swing low terakhir)
    elif current_close < last_swing_low_price * (1 - min_break_threshold):
        if bos_info['current_bias'] == "bearish":
            bos_info.update({"type": "bearish_bos", "level": float(last_swing_low_price), 
                             "direction": "down", "timestamp": current_candle_time})
            logger.debug(f"Bearish BOS Ditemukan (Konfirmasi Tren Turun): {last_swing_low_price:.4f}")
        elif bos_info['current_bias'] in ["bullish", "ranging"]:
            bos_info.update({"type": "bearish_choch", "level": float(last_swing_low_price), 
                             "direction": "down", "timestamp": current_candle_time})
            logger.debug(f"Bearish CHoCH Ditemukan (Potensi Pembalikan Tren): {last_swing_low_price:.4f}")
    
    logger.debug(f"Sinyal akhir BOS/CHoCH: {bos_info}")
    logger.debug("--- END DEBUG: detect_bos_choch ---")
    return bos_info

def detect_fvg(df: pd.DataFrame) -> dict:
    """
    Mendeteksi Fair Value Gap (FVG) atau imbalance.
    Melacak FVG yang belum dimitigasi.
    """
    logger.debug("🔍 Mendeteksi Fair Value Gap (FVG)...")
    fvg_info = {"type": "no_fvg", "zone": None, "timestamp": None, "all_unmitigated_fvg": []}

    if len(df) < 3:
        logger.debug("Tidak cukup data untuk FVG.")
        return fvg_info

    # Iterasi dari belakang untuk menemukan FVG terbaru dan melacak yang belum dimitigasi
    unmitigated_fvg_list = []

    for i in range(len(df) - 3, -1, -1): # Mulai dari lilin ke-3 dari belakang
        candle1 = df.iloc[i]
        candle2 = df.iloc[i+1]
        candle3 = df.iloc[i+2]
        
        fvg_found = False
        fvg_zone = None
        fvg_type = None

        # Bullish FVG: High lilin 1 < Low lilin 3
        if candle1['high'] < candle3['low']:
            fvg_zone = [float(candle1['high']), float(candle3['low'])]
            fvg_type = "bullish_fvg"
            fvg_found = True
        # Bearish FVG: Low lilin 1 > High lilin 3
        elif candle1['low'] > candle3['high']:
            fvg_zone = [float(candle3['high']), float(candle1['low'])]
            fvg_type = "bearish_fvg"
            fvg_found = True
        
        if fvg_found:
            # Cek mitigasi: Apakah ada lilin setelah FVG yang masuk ke dalam zona FVG?
            # Iterasi ke depan dari lilin ke-4 (i+3) hingga akhir DataFrame
            is_mitigated = False
            for j in range(i + 3, len(df)):
                test_candle = df.iloc[j]
                if fvg_type == "bullish_fvg":
                    if test_candle['low'] <= fvg_zone[1] and test_candle['high'] >= fvg_zone[0]: # Jika lilin masuk atau melewati FVG
                        is_mitigated = True
                        break
                elif fvg_type == "bearish_fvg":
                    if test_candle['high'] >= fvg_zone[0] and test_candle['low'] <= fvg_zone[1]: # Jika lilin masuk atau melewati FVG
                        is_mitigated = True
                        break
            
            if not is_mitigated:
                unmitigated_fvg_list.append({
                    "type": fvg_type,
                    "zone": fvg_zone,
                    "timestamp": df.index[i+1] # Timestamp candle tengah FVG
                })
                # FVG terbaru yang belum dimitigasi akan menjadi yang pertama dalam list
                if fvg_info["type"] == "no_fvg": # Hanya simpan FVG terbaru sebagai 'fvg'
                    fvg_info["type"] = fvg_type
                    fvg_info["zone"] = fvg_zone
                    fvg_info["timestamp"] = df.index[i+1] # Timestamp lilin tengah
                    logger.debug(f"FVG Terbaru (Unmitigated) terdeteksi: {fvg_info['zone']}")

    fvg_info["all_unmitigated_fvg"] = unmitigated_fvg_list[::-1] # Urutkan dari yang paling lama ke paling baru

    logger.debug(f"FVG deteksi selesai. Total unmitigated FVG: {len(fvg_info['all_unmitigated_fvg'])}")
    return fvg_info

def detect_eq_zone(df: pd.DataFrame, swing_points: dict, tolerance_percent: float = 0.0005) -> dict:
    """
    Mendeteksi Equal Highs/Lows (EQ Zone) dari swing points yang terdeteksi.
    Ini adalah penarik likuiditas penting.
    """
    logger.debug("🔍 Mendeteksi Equilibrium (EQ) Zone (Equal Highs/Lows)...")
    eq_zone_info = {"eq_high": [], "eq_low": []}
    
    # Fungsi pembantu untuk mengelompokkan harga yang 'sama' dalam toleransi
    def group_equal_prices(prices, is_high_group):
        if not prices:
            return []
        
        groups = []
        current_group = [prices[0]]

        for i in range(1, len(prices)):
            # Cek apakah harga saat ini dalam toleransi dari rata-rata grup saat ini
            group_mean = np.mean(current_group)
            if abs(prices[i] - group_mean) / group_mean <= tolerance_percent:
                current_group.append(prices[i])
            else:
                if len(current_group) >= 2: # Minimal 2 titik untuk dianggap "equal"
                    groups.append(float(np.mean(current_group)))
                current_group = [prices[i]]
        
        if len(current_group) >= 2:
            groups.append(float(np.mean(current_group)))
        return groups

    # Equal Highs
    high_prices_from_swings = [df.loc[ts]['high'] for ts in swing_points['swing_highs'] if ts in df.index]
    eq_zone_info['eq_high'] = group_equal_prices(sorted(high_prices_from_swings), True)

    # Equal Lows
    low_prices_from_swings = [df.loc[ts]['low'] for ts in swing_points['swing_lows'] if ts in df.index]
    eq_zone_info['eq_low'] = group_equal_prices(sorted(low_prices_from_swings), False)
    
    logger.debug(f"EQ Zone deteksi selesai: Highs: {eq_zone_info['eq_high']}, Lows: {eq_zone_info['eq_low']}")
    return eq_zone_info


def detect_order_block(df: pd.DataFrame, smc_results: dict) -> dict:
    """
    Mendeteksi Order Block (OB) yang relevan berdasarkan struktur pasar (BOS/CHoCH) dan FVG.
    Ini adalah implementasi OB yang lebih mendekati definisi SMC.
    Bullish OB: Lilin bearish terakhir sebelum pergerakan impulsif yang menyebabkan BOS/CHoCH bullish dan FVG.
    Bearish OB: Lilin bullish terakhir sebelum pergerakan impulsif yang menyebabkan BOS/CHoCH bearish dan FVG.
    """
    logger.debug("🔍 Mendeteksi Order Block (OB) yang lebih canggih...")
    order_block_info = {"bullish_ob": None, "bearish_ob": None}

    bos_choch_info = smc_results.get('bos_choch', {})
    fvg_info = smc_results.get('fvg', {})
    
    current_candle_time = df.index[-1]

    # Cari Bullish OB
    if bos_choch_info.get('type') in ["bullish_bos", "bullish_choch"] and fvg_info.get('type') == "bullish_fvg":
        break_level_time = bos_choch_info.get('timestamp')
        fvg_timestamp = fvg_info.get('timestamp')

        if break_level_time and fvg_timestamp and break_level_time in df.index and fvg_timestamp in df.index:
            # Asumsi: FVG terjadi bersamaan atau setelah BOS/CHoCH
            # Cari lilin bearish terakhir sebelum FVG / pergerakan BOS/CHoCH
            
            # Cari indeks dari lilin BOS/CHoCH
            idx_break = df.index.get_loc(break_level_time)

            # Batasi pencarian OB pada area sebelum BOS/CHoCH dan FVG
            # Kita mencari lilin bearish yang *segera* mendahului pergerakan impulsif.
            search_window_start = max(0, idx_break - 10) # Cari dalam 10 candle sebelum BOS
            search_df = df.iloc[search_window_start : idx_break + 1] # Termasuk candle BOS/CHoCH

            bullish_ob_candidate = None
            for i in range(len(search_df) -1, -1, -1):
                candle = search_df.iloc[i]
                # Lilin bearish (close < open)
                if candle['close'] < candle['open']:
                    # Ini adalah lilin bearish. Sekarang cek apakah pergerakan setelahnya impulsif
                    # Kita bisa lihat apakah ada FVG setelahnya atau pergerakan harga yang signifikan
                    # Untuk kesempurnaan, kita harus cek apakah candle ini adalah 'last down candle'
                    # sebelum pergerakan 'up' yang kuat.
                    bullish_ob_candidate = candle
                    break
            
            if bullish_ob_candidate is not None:
                # Validasi OB: Pastikan OB belum dimitigasi oleh harga saat ini
                if current_candle_time > bullish_ob_candidate.name:
                    if not (df.loc[bullish_ob_candidate.name:current_candle_time]['low'] <= bullish_ob_candidate['high']).any():
                        order_block_info['bullish_ob'] = {
                            "start_time": bullish_ob_candidate.name,
                            "high": float(bullish_ob_candidate['high']),
                            "low": float(bullish_ob_candidate['low']),
                            "type": "bullish",
                            "candle_type": "bearish_candle_before_bullish_move",
                            "mitigated": False # Asumsi belum dimitigasi oleh pergerakan saat ini
                        }
                        logger.debug(f"Bullish OB terdeteksi: {order_block_info['bullish_ob']}")
    
    # Cari Bearish OB
    if bos_choch_info.get('type') in ["bearish_bos", "bearish_choch"] and fvg_info.get('type') == "bearish_fvg":
        break_level_time = bos_choch_info.get('timestamp')
        fvg_timestamp = fvg_info.get('timestamp')

        if break_level_time and fvg_timestamp and break_level_time in df.index and fvg_timestamp in df.index:
            idx_break = df.index.get_loc(break_level_time)
            search_window_start = max(0, idx_break - 10)
            search_df = df.iloc[search_window_start : idx_break + 1]

            bearish_ob_candidate = None
            for i in range(len(search_df) -1, -1, -1):
                candle = search_df.iloc[i]
                # Lilin bullish (close > open)
                if candle['close'] > candle['open']:
                    bearish_ob_candidate = candle
                    break
            
            if bearish_ob_candidate is not None:
                # Validasi OB: Pastikan OB belum dimitigasi
                if current_candle_time > bearish_ob_candidate.name:
                    if not (df.loc[bearish_ob_candidate.name:current_candle_time]['high'] >= bearish_ob_candidate['low']).any():
                        order_block_info['bearish_ob'] = {
                            "start_time": bearish_ob_candidate.name,
                            "high": float(bearish_ob_candidate['high']),
                            "low": float(bearish_ob_candidate['low']),
                            "type": "bearish",
                            "candle_type": "bullish_candle_before_bearish_move",
                            "mitigated": False
                        }
                        logger.debug(f"Bearish OB terdeteksi: {order_block_info['bearish_ob']}")

    logger.debug(f"Order Block deteksi selesai: {order_block_info}")
    return order_block_info


def analyze_smc_structure(df: pd.DataFrame) -> dict:
    """
    Fungsi utama untuk menganalisis seluruh struktur Smart Money Concepts (SMC).
    Menggabungkan semua deteksi SMC ke dalam satu output.
    """
    if df.empty:
        logger.warning("DataFrame kosong, tidak dapat menganalisis struktur SMC.")
        return {}

    # Pastikan kolom adalah numerik
    for col in ['open', 'high', 'low', 'close', 'volume']:
        if col not in df.columns:
            logger.error(f"Kolom '{col}' tidak ditemukan di DataFrame untuk SMC analisis.")
            return {}
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    smc_results = {}

    # 1. Deteksi Significant Swing Points
    # Menggunakan min_bars_between_swings untuk memastikan swing yang terpisah dan signifikan
    # Ini adalah langkah awal untuk menentukan struktur pasar yang valid
    smc_results['swing_points'] = find_significant_swing_points(df, min_bars_between_swings=5)

    # 2. Deteksi BOS/CHoCH - sangat bergantung pada swing points
    # Min_break_threshold: persentase minimal penembusan untuk dianggap BOS/CHoCH valid
    smc_results['bos_choch'] = detect_bos_choch(df, smc_results['swing_points'], min_break_threshold=0.0002) # 0.02% break

    # 3. Deteksi FVG - Sekarang melacak FVG yang belum dimitigasi
    smc_results['fvg'] = detect_fvg(df)

    # 4. Deteksi Equal Highs/Lows (EQ Zone)
    smc_results['eq_zone'] = detect_eq_zone(df, smc_results['swing_points'], tolerance_percent=0.0005) # 0.05% tolerance

    # 5. Deteksi Order Block - Sekarang lebih tergantung pada BOS/CHoCH dan FVG
    smc_results['order_block'] = detect_order_block(df, smc_results)

    logger.info("✅ Analisis struktur SMC selesai.")
    return smc_results

# Contoh penggunaan (bisa dihapus jika hanya diimpor)
if __name__ == '__main__':
    # Pastikan utils.logger ada di path
    import sys
    import os
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from utils.logger import setup_logger
    
    main_logger = setup_logger("SMC_Analyzer_Test", log_level=logging.DEBUG)

    # Data dummy yang lebih panjang dan bervariasi untuk pengujian SMC
    # Data ini perlu cukup panjang untuk mendeteksi swing points yang signifikan
    # dan pola BOS/CHoCH yang valid.
    num_candles = 200
    dates = pd.to_datetime(pd.date_range(start='2025-05-01', periods=num_candles, freq='5min'))
    
    np.random.seed(42) # For reproducibility
    # Simulate a general uptrend with some corrections
    base_price = 100.0
    prices = [base_price + np.random.uniform(-1, 1)]
    for _ in range(1, num_candles):
        change = np.random.normal(0.0, 0.5) # Small random change
        if _ % 50 < 25: # Create some oscillating movement
            change += 0.2 # General uptrend
        else:
            change -= 0.1 # Small pullbacks
        
        # Add some significant moves for BOS/CHoCH/FVG
        if _ == 70: change += 5.0 # Impulsive move up
        if _ == 120: change -= 7.0 # Impulsive move down
        
        prices.append(prices[-1] + change)

    prices = np.array(prices)
    
    df_test_data = {
        'open': prices,
        'high': prices + np.random.uniform(0, 1, num_candles),
        'low': prices - np.random.uniform(0, 1, num_candles),
        'close': prices + np.random.uniform(-0.5, 0.5, num_candles),
        'volume': np.random.randint(500, 2000, num_candles)
    }
    # Ensure high >= close, open, low
    df_test_data['high'] = np.maximum(df_test_data['high'], np.maximum(df_test_data['open'], df_test_data['close']))
    # Ensure low <= close, open, high
    df_test_data['low'] = np.minimum(df_test_data['low'], np.minimum(df_test_data['open'], df_test_data['close']))

    test_df = pd.DataFrame(df_test_data, index=dates)
    
    print("\n--- [TEST] SMC Structure Analysis ---")
    smc_results = analyze_smc_structure(test_df.copy())
    print("\nHasil Analisis SMC:")
    for key, value in smc_results.items():
        if isinstance(value, dict):
            print(f"  {key}:")
            for sub_key, sub_value in value.items():
                print(f"    {sub_key}: {sub_value}")
        else:
            print(f"  {key}: {value}")
