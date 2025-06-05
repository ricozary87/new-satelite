# === FILE: logic_engine/confluence_checker.py ===
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__) # Mendapatkan logger untuk modul ini

def _is_price_in_zone(current_price: float, zone: list) -> bool:
    """Helper: Memeriksa apakah harga saat ini berada di dalam zona yang diberikan."""
    if zone is None or len(zone) != 2:
        return False
    zone_min, zone_max = sorted(zone)
    return zone_min <= current_price <= zone_max

def _is_price_near_zone(current_price: float, zone: list, tolerance_percent: float = 0.001) -> bool:
    """Helper: Memeriksa apakah harga saat ini mendekati zona yang diberikan dalam toleransi."""
    if zone is None or len(zone) != 2:
        return False
    zone_min, zone_max = sorted(zone)
    
    # Perhitungan toleransi berdasarkan kisaran zona atau harga saat ini
    price_range = abs(zone_max - zone_min)
    if price_range == 0: # Jika zona adalah satu titik (misal: equal high/low)
        abs_tolerance = current_price * tolerance_percent
    else: # Jika zona memiliki kisaran
        abs_tolerance = price_range * tolerance_percent
    
    return (current_price >= (zone_min - abs_tolerance) and current_price <= (zone_max + abs_tolerance))

def _is_price_entering_zone(open_price: float, close_price: float, zone: list) -> bool:
    """Helper: Memeriksa apakah lilin saat ini masuk ke dalam zona dari luar."""
    if zone is None or len(zone) != 2:
        return False
    zone_min, zone_max = sorted(zone)

    # Lilin bullish masuk zona dari bawah (open di bawah, close di dalam/melalui)
    bullish_entry = (open_price < zone_min and close_price >= zone_min)

    # Lilin bearish masuk zona dari atas (open di atas, close di dalam/melalui)
    bearish_entry = (open_price > zone_max and close_price <= zone_max)
    
    return bullish_entry or bearish_entry


def check_buy_confluence(classic_indicators: dict, smc_signals: dict, current_price: float, current_open_price: float) -> dict:
    """
    Menentukan sinyal BELI berdasarkan konfluensi antara indikator klasik dan sinyal SMC.
    Mengembalikan dictionary dengan level kekuatan sinyal.
    """
    logger.debug("🧐 Mengecek kondisi beli...")
    signal_strength = {'type': 'no_signal', 'reason': []}

    # --- Ambil Data Indikator Klasik ---
    ema_signal = classic_indicators.get("ema_signal")
    macd_trend = classic_indicators.get("macd_trend")
    rsi_signal = classic_indicators.get("rsi_signal")
    stoch_signal = classic_indicators.get("stoch_signal")
    bb_signal = classic_indicators.get("bb_signal")
    rsi_value = classic_indicators.get("rsi")
    
    # --- Ambil Data Sinyal SMC ---
    bos_choch = smc_signals.get("bos_choch", {})
    fvg_data = smc_signals.get("fvg", {})
    order_block_data = smc_signals.get("order_block", {})
    eq_zone_data = smc_signals.get("eq_zone", {})

    # Inisialisasi status konfluensi
    confluences = {
        'ema_bullish_trend': False,
        'macd_bullish_momentum': False,
        'rsi_not_overbought': False, # Ini berarti RSI tidak di atas 70 (normal/oversold)
        'stoch_bullish_momentum': False,
        'smc_structure_break': False,
        'fvg_bullish_presence': False,
        'ob_bullish_presence': False,
        'price_reacting_to_fvg': False,
        'price_reacting_to_ob': False,
        'liquidity_grab_low': False,
        'bb_bullish_signal': False
    }

    # --- Evaluasi Indikator Klasik ---
    if ema_signal in ["strong_bullish", "bullish"]:
        confluences['ema_bullish_trend'] = True
        signal_strength['reason'].append(f"EMA: {ema_signal.replace('_', ' ').title()} Trend")
    
    if macd_trend == "bullish":
        confluences['macd_bullish_momentum'] = True
        signal_strength['reason'].append("MACD: Bullish Momentum")
    
    # RSI: Tidak overbought dan di atas level oversolde
    # Jika RSI di bawah 70 (tidak overbought) ATAU jika RSI oversold (potensi reversal)
    if rsi_value < 70: # Not overbought (bisa normal atau oversold)
        confluences['rsi_not_overbought'] = True
        signal_strength['reason'].append(f"RSI: Not Overbought ({rsi_value:.2f})")
        if rsi_value < 30: # Tambahan detail jika oversold
            signal_strength['reason'].append(f"RSI: Oversold ({rsi_value:.2f}) - Potential Reversal")
    
    if stoch_signal in ["bullish", "oversold_bullish_cross"]:
        confluences['stoch_bullish_momentum'] = True
        signal_strength['reason'].append("Stoch RSI: Bullish Momentum/Crossover")

    if bb_signal in ["cross_above_middle", "bounce_from_lower", "cross_above_lower_band", "outside_lower_band"]:
        confluences['bb_bullish_signal'] = True
        signal_strength['reason'].append(f"BB: {bb_signal.replace('_', ' ').title()}")

    # --- Evaluasi Sinyal SMC ---
    bos_type = bos_choch.get("type")
    if bos_type in ["bullish_bos", "bullish_choch", "bullish_choch_potential"]:
        confluences['smc_structure_break'] = True
        signal_strength['reason'].append(f"SMC: {bos_type.replace('_', ' ').title()} Detected")

    if fvg_data and fvg_data.get("type") == "bullish_fvg" and fvg_data.get("zone"):
        fvg_zone = fvg_data['zone']
        confluences['fvg_bullish_presence'] = True
        signal_strength['reason'].append("SMC: Bullish FVG Present")
        # Harga bereaksi: saat ini di dalam FVG, atau baru masuk ke FVG
        if _is_price_in_zone(current_price, fvg_zone) or \
           _is_price_entering_zone(current_open_price, current_price, fvg_zone):
            confluences['price_reacting_to_fvg'] = True
            signal_strength['reason'].append("SMC: Price in/entering Bullish FVG (reaction)")

    bullish_ob_data = order_block_data.get("bullish_ob")
    if bullish_ob_data and bullish_ob_data.get('low') is not None and bullish_ob_data.get('high') is not None:
        ob_zone = [bullish_ob_data['low'], bullish_ob_data['high']]
        confluences['ob_bullish_presence'] = True
        signal_strength['reason'].append("SMC: Bullish OB Present")
        # Harga bereaksi: saat ini di dekat/dalam OB, atau baru masuk ke OB
        if _is_price_near_zone(current_price, ob_zone, tolerance_percent=0.005) or \
           _is_price_entering_zone(current_open_price, current_price, ob_zone):
            confluences['price_reacting_to_ob'] = True
            signal_strength['reason'].append("SMC: Price near/in/entering Bullish OB (reaction)")
            
    if eq_zone_data.get('eq_low') and len(eq_zone_data['eq_low']) > 0:
        # Cek apakah harga telah "menyapu" (sweep) equal low dan mulai berbalik
        last_eq_low_level = max(eq_zone_data['eq_low']) # Ambil equal low yang paling tinggi/terbaru
        # Jika lilin menembus equal low dan kemudian close di atasnya (reversal)
        if current_open_price < last_eq_low_level and current_price > last_eq_low_level:
            confluences['liquidity_grab_low'] = True
            signal_strength['reason'].append(f"SMC: Equal Low ({last_eq_low_level:.2f}) swept (liquidity grab).")
        elif _is_price_near_zone(current_price, [last_eq_low_level, last_eq_low_level], tolerance_percent=0.001):
            confluences['liquidity_grab_low'] = True # Masih di dekatnya, potensi penarikan
            signal_strength['reason'].append(f"SMC: Price near Equal Low ({last_eq_low_level:.2f}) (potential liquidity).")


    # --- Kombinasi Logika Konfluensi untuk Sinyal BELI ---
    # Sinyal Sangat Kuat (Strong Buy)
    # Membutuhkan tren bullish, momentum, struktur break, DAN reaksi di POI (OB/FVG)
    # Serta konfirmasi dari likuiditas atau BB
    if (confluences['ema_bullish_trend'] and
        confluences['macd_bullish_momentum'] and
        confluences['rsi_not_overbought'] and # RSI tidak overbought (bisa normal/oversold)
        confluences['stoch_bullish_momentum'] and
        confluences['smc_structure_break'] and
        (confluences['price_reacting_to_ob'] or confluences['price_reacting_to_fvg']) and
        (confluences['liquidity_grab_low'] or confluences['bb_bullish_signal'])): # Tambahan konfirmasi
        
        signal_strength['type'] = 'strong_buy'
        signal_strength['reason'].append("Strong Confluence: All major conditions met (Trend, Momentum, Structure Break, POI reaction, Liquidity/BB).")
        logger.debug("Strong Buy Signal Detected!")
        return signal_strength

    # Sinyal Kuat (Moderate Buy)
    # Membutuhkan tren bullish, struktur break, dan setidaknya satu momentum/BB positif,
    # PLUS reaksi di POI, ATAU likuiditas terambil.
    if (confluences['ema_bullish_trend'] and
        confluences['smc_structure_break'] and
        (confluences['macd_bullish_momentum'] or confluences['stoch_bullish_momentum'] or confluences['bb_bullish_signal']) and
        (confluences['price_reacting_to_ob'] or confluences['price_reacting_to_fvg'] or confluences['liquidity_grab_low'])):
        
        signal_strength['type'] = 'moderate_buy'
        signal_strength['reason'].append("Moderate Confluence: Trend, Structure, Momentum/BB alignment, with POI/Liquidity interaction.")
        logger.debug("Moderate Buy Signal Detected.")
        return signal_strength

    # Sinyal Potensial (Weak Buy / Entry Confirmation)
    # Membutuhkan reaksi di POI DENGAN momentum positif ATAU likuiditas terambil
    if (confluences['price_reacting_to_ob'] or confluences['price_reacting_to_fvg'] or confluences['liquidity_grab_low']) and \
       (confluences['rsi_not_overbought'] or confluences['stoch_bullish_momentum'] or confluences['bb_bullish_signal']):
        
        signal_strength['type'] = 'potential_buy'
        signal_strength['reason'].append("Potential Confluence: Price reacting at POI/Liquidity with momentum/BB confirmation.")
        logger.debug("Potential Buy Signal Detected.")
        return signal_strength

    logger.debug("No Buy Signal based on current confluence.")
    return signal_strength


def check_sell_confluence(classic_indicators: dict, smc_signals: dict, current_price: float, current_open_price: float) -> dict:
    """
    Menentukan sinyal JUAL berdasarkan konfluensi antara indikator klasik dan sinyal SMC.
    Mengembalikan dictionary dengan level kekuatan sinyal.
    """
    logger.debug("🧐 Mengecek kondisi jual...")
    signal_strength = {'type': 'no_signal', 'reason': []}

    # --- Ambil Data Indikator Klasik ---
    ema_signal = classic_indicators.get("ema_signal")
    macd_trend = classic_indicators.get("macd_trend")
    rsi_signal = classic_indicators.get("rsi_signal")
    stoch_signal = classic_indicators.get("stoch_signal")
    bb_signal = classic_indicators.get("bb_signal")
    rsi_value = classic_indicators.get("rsi")

    # --- Ambil Data Sinyal SMC ---
    bos_choch = smc_signals.get("bos_choch", {})
    fvg_data = smc_signals.get("fvg", {})
    order_block_data = smc_signals.get("order_block", {})
    eq_zone_data = smc_signals.get("eq_zone", {})

    # Inisialisasi status konfluensi
    confluences = {
        'ema_bearish_trend': False,
        'macd_bearish_momentum': False,
        'rsi_not_oversold': False, # Ini berarti RSI tidak di bawah 30 (normal/overbought)
        'stoch_bearish_momentum': False,
        'smc_structure_break': False,
        'fvg_bearish_presence': False,
        'ob_bearish_presence': False,
        'price_reacting_to_fvg': False,
        'price_reacting_to_ob': False,
        'liquidity_grab_high': False,
        'bb_bearish_signal': False
    }

    # --- Evaluasi Indikator Klasik ---
    if ema_signal in ["strong_bearish", "bearish"]:
        confluences['ema_bearish_trend'] = True
        signal_strength['reason'].append(f"EMA: {ema_signal.replace('_', ' ').title()} Trend")
    
    if macd_trend == "bearish":
        confluences['macd_bearish_momentum'] = True
        signal_strength['reason'].append("MACD: Bearish Momentum")
    
    # RSI: Tidak oversold dan di bawah level overbought
    # Jika RSI di atas 30 (tidak oversold) ATAU jika RSI overbought (potensi reversal)
    if rsi_value > 30: # Not oversold (bisa normal atau overbought)
        confluences['rsi_not_oversold'] = True
        signal_strength['reason'].append(f"RSI: Not Oversold ({rsi_value:.2f})")
        if rsi_value > 70: # Tambahan detail jika overbought
            signal_strength['reason'].append(f"RSI: Overbought ({rsi_value:.2f}) - Potential Reversal")
    
    if stoch_signal in ["bearish", "overbought_bearish_cross"]:
        confluences['stoch_bearish_momentum'] = True
        signal_strength['reason'].append("Stoch RSI: Bearish Momentum/Crossover")

    if bb_signal in ["cross_below_middle", "bounce_from_upper", "cross_below_upper_band", "outside_upper_band"]:
        confluences['bb_bearish_signal'] = True
        signal_strength['reason'].append(f"BB: {bb_signal.replace('_', ' ').title()}")

    # --- Evaluasi Sinyal SMC ---
    bos_type = bos_choch.get("type")
    if bos_type in ["bearish_bos", "bearish_choch", "bearish_choch_potential"]:
        confluences['smc_structure_break'] = True
        signal_strength['reason'].append(f"SMC: {bos_type.replace('_', ' ').title()} Detected")

    if fvg_data and fvg_data.get("type") == "bearish_fvg" and fvg_data.get("zone"):
        fvg_zone = fvg_data['zone']
        confluences['fvg_bearish_presence'] = True
        signal_strength['reason'].append("SMC: Bearish FVG Present")
        # Harga bereaksi: saat ini di dalam FVG, atau baru masuk ke FVG
        if _is_price_in_zone(current_price, fvg_zone) or \
           _is_price_entering_zone(current_open_price, current_price, fvg_zone):
            confluences['price_reacting_to_fvg'] = True
            signal_strength['reason'].append("SMC: Price in/entering Bearish FVG (reaction)")

    bearish_ob_data = order_block_data.get("bearish_ob")
    if bearish_ob_data and bearish_ob_data.get('low') is not None and bearish_ob_data.get('high') is not None:
        ob_zone = [bearish_ob_data['low'], bearish_ob_data['high']]
        confluences['ob_bearish_presence'] = True
        signal_strength['reason'].append("SMC: Bearish OB Present")
        # Harga bereaksi: saat ini di dekat/dalam OB, atau baru masuk ke OB
        if _is_price_near_zone(current_price, ob_zone, tolerance_percent=0.005) or \
           _is_price_entering_zone(current_open_price, current_price, ob_zone):
            confluences['price_reacting_to_ob'] = True
            signal_strength['reason'].append("SMC: Price near/in/entering Bearish OB (reaction)")
            
    if eq_zone_data.get('eq_high') and len(eq_zone_data['eq_high']) > 0:
        # Cek apakah harga telah "menyapu" (sweep) equal high dan mulai berbalik
        last_eq_high_level = min(eq_zone_data['eq_high']) # Ambil equal high yang paling rendah/terbaru
        # Jika lilin menembus equal high dan kemudian close di bawahnya (reversal)
        if current_open_price > last_eq_high_level and current_price < last_eq_high_level:
            confluences['liquidity_grab_high'] = True
            signal_strength['reason'].append(f"SMC: Equal High ({last_eq_high_level:.2f}) swept (liquidity grab).")
        elif _is_price_near_zone(current_price, [last_eq_high_level, last_eq_high_level], tolerance_percent=0.001):
            confluences['liquidity_grab_high'] = True # Masih di dekatnya, potensi penarikan
            signal_strength['reason'].append(f"SMC: Price near Equal High ({last_eq_high_level:.2f}) (potential liquidity).")


    # --- Kombinasi Logika Konfluensi untuk Sinyal JUAL ---
    # Sinyal Sangat Kuat (Strong Sell)
    if (confluences['ema_bearish_trend'] and
        confluences['macd_bearish_momentum'] and
        confluences['rsi_not_oversold'] and # RSI tidak oversold (bisa normal/overbought)
        confluences['stoch_bearish_momentum'] and
        confluences['smc_structure_break'] and
        (confluences['price_reacting_to_ob'] or confluences['price_reacting_to_fvg']) and
        (confluences['liquidity_grab_high'] or confluences['bb_bearish_signal'])):
        
        signal_strength['type'] = 'strong_sell'
        signal_strength['reason'].append("Strong Confluence: All major conditions met (Trend, Momentum, Structure Break, POI reaction, Liquidity/BB).")
        logger.debug("Strong Sell Signal Detected!")
        return signal_strength

    # Sinyal Kuat (Moderate Sell)
    if (confluences['ema_bearish_trend'] and
        confluences['smc_structure_break'] and
        (confluences['macd_bearish_momentum'] or confluences['stoch_bearish_momentum'] or confluences['bb_bearish_signal']) and
        (confluences['price_reacting_to_ob'] or confluences['price_reacting_to_fvg'] or confluences['liquidity_grab_high'])):
        
        signal_strength['type'] = 'moderate_sell'
        signal_strength['reason'].append("Moderate Confluence: Trend, Structure, Momentum/BB alignment, with POI/Liquidity interaction.")
        logger.debug("Moderate Sell Signal Detected.")
        return signal_strength

    # Sinyal Potensial (Weak Sell / Entry Confirmation)
    if (confluences['price_reacting_to_ob'] or confluences['price_reacting_to_fvg'] or confluences['liquidity_grab_high']) and \
       (confluences['rsi_not_oversold'] or confluences['stoch_bearish_momentum'] or confluences['bb_bearish_signal']):
        
        signal_strength['type'] = 'potential_sell'
        signal_strength['reason'].append("Potential Confluence: Price reacting at POI/Liquidity with momentum/BB confirmation.")
        logger.debug("Potential Sell Signal Detected.")
        return signal_strength

    logger.debug("No Sell Signal based on current confluence.")
    return signal_strength

# === FILE: logic_engine/confluence_checker.py (LANJUTAN) ===

def evaluate_confluence(classic_indicators: dict, smc_signals: dict, current_price: float, current_open_price: float) -> tuple[str, list]:
    """
    Mengevaluasi konfluensi keseluruhan berdasarkan indikator klasik dan sinyal SMC.
    Ini adalah fungsi yang akan dipanggil dari modul lain (misalnya, core/analyzer_entry.py).

    Args:
        classic_indicators (dict): Hasil dari analisis indikator klasik.
        smc_signals (dict): Hasil dari analisis struktur SMC.
        current_price (float): Harga penutupan candle saat ini.
        current_open_price (float): Harga pembukaan candle saat ini.

    Returns:
        tuple[str, list]: Kekuatan sinyal (misalnya, 'strong_buy', 'no_signal')
                          dan daftar alasan yang mendukung sinyal.
    """
    logger.info("🔍 Mengevaluasi konfluensi sinyal...")

    buy_strength_result = check_buy_confluence(classic_indicators, smc_signals, current_price, current_open_price)
    sell_strength_result = check_sell_confluence(classic_indicators, smc_signals, current_price, current_open_price)

    final_signal_type = 'no_signal'
    final_reason = []

    # Logika sederhana untuk memilih sinyal terbaik
    # Anda bisa membuat logika ini lebih canggih jika diperlukan (misalnya, prioritas tertentu)
    if buy_strength_result['type'] != 'no_signal' and sell_strength_result['type'] == 'no_signal':
        final_signal_type = buy_strength_result['type']
        final_reason = buy_strength_result['reason']
    elif sell_strength_result['type'] != 'no_signal' and buy_strength_result['type'] == 'no_signal':
        final_signal_type = sell_strength_result['type']
        final_reason = sell_strength_result['reason']
    elif buy_strength_result['type'] != 'no_signal' and sell_strength_result['type'] != 'no_signal':
        # Jika ada sinyal beli dan jual, perlu ada logika untuk memilih salah satu
        # Misalnya, prioritaskan sinyal yang lebih kuat, atau abaikan keduanya jika kontradiktif
        logger.warning(f"Sinyal beli ({buy_strength_result['type']}) dan jual ({sell_strength_result['type']}) terdeteksi. Memilih salah satu atau tidak sama sekali.")
        # Contoh: Jika strong_buy dan strong_sell terdeteksi, mungkin lebih baik no_signal karena konflik
        if 'strong_buy' in buy_strength_result['type'] and 'strong_sell' in sell_strength_result['type']:
            final_signal_type = 'no_signal'
            final_reason.append("Conflicting strong buy and strong sell signals.")
        elif 'strong_buy' in buy_strength_result['type']:
            final_signal_type = buy_strength_result['type']
            final_reason = buy_strength_result['reason']
        elif 'strong_sell' in sell_strength_result['type']:
            final_signal_type = sell_strength_result['type']
            final_reason = sell_strength_result['reason']
        # Anda bisa tambahkan logika prioritas di sini
        else:
            # Ini adalah contoh sederhana. Anda mungkin ingin logika yang lebih kompleks
            # untuk memilih antara moderate/potential buy/sell jika keduanya ada.
            # Untuk saat ini, kita bisa prioritaskan 'buy' jika ada, atau 'sell' jika tidak ada 'buy' yang kuat.
            if buy_strength_result['type'] == 'moderate_buy' or buy_strength_result['type'] == 'potential_buy':
                final_signal_type = buy_strength_result['type']
                final_reason = buy_strength_result['reason']
            elif sell_strength_result['type'] == 'moderate_sell' or sell_strength_result['type'] == 'potential_sell':
                final_signal_type = sell_strength_result['type']
                final_reason = sell_strength_result['reason']
            else:
                final_signal_type = 'no_signal'
                final_reason.append("No clear dominant signal amidst conflicting potential/moderate signals.")
            
    logger.info(f"Hasil Konfluensi: Tipe: {final_signal_type}, Alasan: {final_reason}")
    return final_signal_type, final_reason

# Jika ingin menguji checker secara terpisah, Anda bisa tambahkan blok if __name__ == "__main__": di sini.
if __name__ == "__main__":
    # Contoh penggunaan dummy untuk pengujian
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
    
    print("\n--- Menguji Confluence Checker ---")

    # Data indikator dan SMC dummy
    dummy_classic_indicators = {
        "ema_signal": "bullish",
        "macd_trend": "bullish",
        "rsi_signal": "normal",
        "rsi": 55.0,
        "stoch_signal": "bullish",
        "bb_signal": "cross_above_middle"
    }
    dummy_smc_signals = {
        "bos_choch": {"type": "bullish_choch"},
        "fvg": {"type": "bullish_fvg", "zone": [190.0, 195.0]},
        "order_block": {"bullish_ob": {"low": 188.0, "high": 192.0}, "bearish_ob": None},
        "eq_zone": {"eq_low": [180.0, 180.5], "eq_high": []}
    }
    current_price = 193.0
    current_open_price = 191.0

    print("\n--- Skenario BELI ---")
    signal_type, reasons = evaluate_confluence(
        dummy_classic_indicators,
        dummy_smc_signals,
        current_price,
        current_open_price
    )
    print(f"Sinyal Beli yang Terdeteksi: {signal_type}, Alasan: {reasons}")

    print("\n--- Skenario JUAL ---")
    # Mengubah dummy data untuk skenario jual
    dummy_classic_indicators_sell = {
        "ema_signal": "bearish",
        "macd_trend": "bearish",
        "rsi_signal": "normal",
        "rsi": 45.0,
        "stoch_signal": "bearish",
        "bb_signal": "cross_below_middle"
    }
    dummy_smc_signals_sell = {
        "bos_choch": {"type": "bearish_choch"},
        "fvg": {"type": "bearish_fvg", "zone": [205.0, 210.0]},
        "order_block": {"bullish_ob": None, "bearish_ob": {"low": 208.0, "high": 212.0}},
        "eq_zone": {"eq_low": [], "eq_high": [220.0, 220.5]}
    }
    current_price_sell = 207.0
    current_open_price_sell = 209.0

    signal_type_sell, reasons_sell = evaluate_confluence(
        dummy_classic_indicators_sell,
        dummy_smc_signals_sell,
        current_price_sell,
        current_open_price_sell
    )
    print(f"Sinyal Jual yang Terdeteksi: {signal_type_sell}, Alasan: {reasons_sell}")

    print("\n--- Skenario NO_SIGNAL ---")
    no_signal_classic = {
        "ema_signal": "neutral",
        "macd_trend": "neutral",
        "rsi_signal": "normal",
        "rsi": 50.0,
        "stoch_signal": "neutral",
        "bb_signal": "normal"
    }
    no_signal_smc = {
        "bos_choch": {"type": "no_break"},
        "fvg": {},
        "order_block": {},
        "eq_zone": {}
    }
    signal_type_no, reasons_no = evaluate_confluence(
        no_signal_classic,
        no_signal_smc,
        100.0,
        100.0
    )
    print(f"Sinyal No_Signal yang Terdeteksi: {signal_type_no}, Alasan: {reasons_no}")
