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
    
    price_range = abs(zone_max - zone_min)
    if price_range == 0:
        abs_tolerance = current_price * tolerance_percent
    else:
        abs_tolerance = price_range * tolerance_percent
    
    return (current_price >= (zone_min - abs_tolerance) and current_price <= (zone_max + abs_tolerance))

def _is_price_entering_zone(open_price: float, close_price: float, zone: list) -> bool:
    """Helper: Memeriksa apakah lilin saat ini masuk ke dalam zona dari luar."""
    if zone is None or len(zone) != 2:
        return False
    zone_min, zone_max = sorted(zone)

    # Harga memasuki zona jika open di luar zona DAN close di dalam zona
    # atau sebaliknya (open di dalam, close di luar, tapi kita fokus pada masuk)
    
    # Lilin bullish masuk zona dari bawah
    bullish_entry = (open_price < zone_min and close_price >= zone_min and close_price <= zone_max)
    # Lilin bearish masuk zona dari atas
    bearish_entry = (open_price > zone_max and close_price <= zone_max and close_price >= zone_min)
    
    # Atau jika lilin besar menembus zona dari satu sisi ke sisi lain
    overshoot_entry_bullish = (open_price < zone_min and close_price > zone_max)
    overshoot_entry_bearish = (open_price > zone_max and close_price < zone_min)

    # Pertimbangkan juga jika bagian dari lilin (misal low/high) menyentuh zona
    # (Ini bisa ditambahkan dengan memeriksa low/high lilin terakhir juga)
    
    return bullish_entry or bearish_entry or overshoot_entry_bullish or overshoot_entry_bearish


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
        'rsi_not_overbought': False,
        'stoch_bullish_momentum': False,
        'smc_structure_break': False, # BOS atau CHoCH
        'fvg_bullish_presence': False,
        'ob_bullish_presence': False,
        'price_reacting_to_fvg': False, # Harga masuk atau bereaksi di dalam FVG
        'price_reacting_to_ob': False, # Harga masuk atau bereaksi di dalam OB
        'liquidity_grab_low': False, # Likuiditas (Equal Lows) diambil
        'bb_bullish_signal': False # Sinyal dari Bollinger Bands
    }

    # --- Evaluasi Indikator Klasik ---
    if ema_signal in ["strong_bullish", "bullish"]:
        confluences['ema_bullish_trend'] = True
        signal_strength['reason'].append(f"EMA: {ema_signal.replace('_', ' ').title()} Trend")
    
    if macd_trend == "bullish":
        confluences['macd_bullish_momentum'] = True
        signal_strength['reason'].append("MACD: Bullish Momentum")
    
    # RSI: Tidak overbought dan di atas level oversolde
    if rsi_signal != "overbought" and rsi_value < 70 and rsi_value > 30: # 30-70 dianggap netral
        confluences['rsi_not_overbought'] = True
        signal_strength['reason'].append(f"RSI: Not Overbought ({rsi_value:.2f})")
    elif rsi_signal == "oversold" and rsi_value < 30: # RSI oversold, potensi reversal
        confluences['rsi_not_overbought'] = True # Untuk tujuan konfluensi, ini juga kondisi baik
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
        confluences['fvg_bullish_presence'] = True
        signal_strength['reason'].append("SMC: Bullish FVG Present")
        # Harga bereaksi: saat ini di dalam FVG, atau baru masuk ke FVG
        if _is_price_in_zone(current_price, fvg_data['zone']) or \
           _is_price_entering_zone(current_open_price, current_price, fvg_data['zone']):
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
        confluences['rsi_not_overbought'] and
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
        'rsi_not_oversold': False,
        'stoch_bearish_momentum': False,
        'smc_structure_break': False, # BOS atau CHoCH
        'fvg_bearish_presence': False,
        'ob_bearish_presence': False,
        'price_reacting_to_fvg': False,
        'price_reacting_to_ob': False,
        'liquidity_grab_high': False, # Likuiditas (Equal Highs) diambil
        'bb_bearish_signal': False # Sinyal dari Bollinger Bands
    }

    # --- Evaluasi Indikator Klasik ---
    if ema_signal in ["strong_bearish", "bearish"]:
        confluences['ema_bearish_trend'] = True
        signal_strength['reason'].append(f"EMA: {ema_signal.replace('_', ' ').title()} Trend")
    
    if macd_trend == "bearish":
        confluences['macd_bearish_momentum'] = True
        signal_strength['reason'].append("MACD: Bearish Momentum")
    
    # RSI: Tidak oversold dan di bawah level overbought
    if rsi_signal != "oversold" and rsi_value > 30 and rsi_value < 70: # 30-70 dianggap netral
        confluences['rsi_not_oversold'] = True
        signal_strength['reason'].append(f"RSI: Not Oversold ({rsi_value:.2f})")
    elif rsi_signal == "overbought" and rsi_value > 70: # RSI overbought, potensi reversal
        confluences['rsi_not_oversold'] = True # Untuk tujuan konfluensi, ini juga kondisi baik
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
        confluences['fvg_bearish_presence'] = True
        signal_strength['reason'].append("SMC: Bearish FVG Present")
        # Harga bereaksi: saat ini di dalam FVG, atau baru masuk ke FVG
        if _is_price_in_zone(current_price, fvg_data['zone']) or \
           _is_price_entering_zone(current_open_price, current_price, fvg_data['zone']):
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
        confluences['rsi_not_oversold'] and
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

# Jika ingin menguji checker secara terpisah, Anda bisa tambahkan blok if __name__ == "__main__": di sini.
