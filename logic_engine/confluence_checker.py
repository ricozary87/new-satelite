# === FILE: logic_engine/confluence_checker.py ===
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__) # Mendapatkan logger untuk modul ini
# Mengatur level logger modul ini ke DEBUG untuk melihat semua pesan log
# Anda bisa mengubahnya ke INFO atau WARNING di produksi
# logger.setLevel(logging.DEBUG)


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
    
    # Hitung toleransi absolut berdasarkan harga saat ini (lebih konsisten)
    # Ini menghindari toleransi yang sangat kecil jika zona range-nya kecil
    abs_tolerance = current_price * tolerance_percent 
    
    return (current_price >= (zone_min - abs_tolerance) and current_price <= (zone_max + abs_tolerance))

def _is_price_entering_zone(open_price: float, close_price: float, zone: list) -> bool:
    """Helper: Memeriksa apakah lilin saat ini masuk ke dalam zona dari luar."""
    if zone is None or len(zone) != 2:
        return False
    zone_min, zone_max = sorted(zone)

    # Lilin bullish masuk zona dari bawah (open di bawah, close di dalam/melalui)
    bullish_entry = (open_price < zone_min and close_price >= zone_min and close_price <= zone_max)

    # Lilin bearish masuk zona dari atas (open di atas, close di dalam/melalui)
    bearish_entry = (open_price > zone_max and close_price <= zone_max and close_price >= zone_min)
    
    return bullish_entry or bearish_entry


def check_buy_confluence(classic_indicators: dict, smc_signals: dict, current_price: float, current_open_price: float, market_data_additional: dict) -> dict:
    """
    Menentukan sinyal BELI berdasarkan konfluensi antara indikator klasik, sinyal SMC,
    dan data pasar tambahan (orderbook, funding, OI, dll.).
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

    # --- Ambil Data Market Tambahan ---
    binance_spot_data = market_data_additional.get("binance_spot", {})
    binance_futures_data = market_data_additional.get("binance_futures", {})
    bybit_data = market_data_additional.get("bybit", {})

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
        'bb_bullish_signal': False,
        # Sinyal dari data market tambahan
        'ob_support_strong': False, # Orderbook support kuat (dinding beli)
        'funding_rate_bullish': False,
        'oi_increasing_with_price': False,
        'long_short_ratio_bullish_divergence': False, # Misal, rasio long terlalu rendah/berbalik naik
        'taker_buy_volume_dominant': False
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
    if rsi_value is not None and rsi_value < 70: # Not overbought (bisa normal atau oversold)
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
        last_eq_low_level = max(eq_zone_data['eq_low']) # Ambil equal low yang paling tinggi/terbaru
        # Jika lilin menembus equal low dan kemudian close di atasnya (reversal)
        if current_open_price < last_eq_low_level and current_price > last_eq_low_level and current_price < (last_eq_low_level * 1.005): # Close sedikit di atas
            confluences['liquidity_grab_low'] = True
            signal_strength['reason'].append(f"SMC: Equal Low ({last_eq_low_level:.2f}) swept and reversed (liquidity grab).")
        elif _is_price_near_zone(current_price, [last_eq_low_level, last_eq_low_level], tolerance_percent=0.001):
            confluences['liquidity_grab_low'] = True # Masih di dekatnya, potensi penarikan
            signal_strength['reason'].append(f"SMC: Price near Equal Low ({last_eq_low_level:.2f}) (potential liquidity).")

    # --- Evaluasi Data Market Tambahan untuk Sinyal BELI ---
    # Orderbook (Binance Spot) - Deteksi Dinding Beli (Strong Bid Wall)
    binance_orderbook = binance_spot_data.get("orderbook")
    if binance_orderbook and binance_orderbook.get('bids'):
        # Cari bid besar di dekat harga saat ini (misal dalam 0.5% dari harga)
        top_bids = sorted([float(b[0]) for b in binance_orderbook['bids']], reverse=True)
        top_bid_price = top_bids[0] if top_bids else 0
        
        # Contoh: Cek apakah ada bid yang sangat besar di dekat harga saat ini
        # Ini perlu tuning lebih lanjut, bisa berdasarkan persentase total volume atau ukuran spesifik
        if current_price and top_bid_price and (current_price - top_bid_price) / current_price < 0.005: # within 0.5%
            # Contoh sederhana: Jika total volume 5 bid teratas > ambang batas
            top_bid_volume = sum([float(b[1]) for b in binance_orderbook['bids'][:5]]) # Sum volume 5 bid teratas
            if top_bid_volume > 50 * current_price: # Contoh: total volume lebih dari 50 BTC/ETH
                confluences['ob_support_strong'] = True
                signal_strength['reason'].append("Orderbook: Strong Bid Wall / Support detected near current price.")
                logger.debug(f"Strong Bid Wall Detected: {top_bid_volume:.2f} at {top_bid_price:.2f}")

    # Funding Rate (Binance Futures & Bybit) - Sentimen Bullish
    binance_fr = float(binance_futures_data.get("funding_rate", [{}])[0].get('fundingRate', 0)) if binance_futures_data.get("funding_rate") else 0
    bybit_fr_result = bybit_data.get("funding_rate")
    bybit_fr = float(bybit_fr_result.get('result', {}).get('list', [{}])[0].get('fundingRate', 0)) if bybit_fr_result and bybit_fr_result.get('result') and bybit_fr_result['result'].get('list') else 0

    if binance_fr > 0.0001 or bybit_fr > 0.0001: # Funding rate positif signifikan
        confluences['funding_rate_bullish'] = True
        signal_strength['reason'].append("Funding Rate: Positive (Bullish Sentiment).")
        logger.debug(f"Funding Rates: Binance {binance_fr:.5f}, Bybit {bybit_fr:.5f}")

    # Open Interest (Binance Futures & Bybit) - OI Meningkat dengan Harga Naik
    # Ini memerlukan data historis OI untuk melihat tren, ini hanya contoh nilai terakhir
    binance_oi = float(binance_futures_data.get("open_interest", {}).get('openInterest', 0)) if binance_futures_data.get("open_interest") else 0
    bybit_oi_result = bybit_data.get("open_interest")
    bybit_oi = float(bybit_oi_result.get('result', {}).get('list', [{}])[0].get('openInterest', 0)) if bybit_oi_result and bybit_oi_result.get('result') and bybit_oi_result['result'].get('list') else 0

    # Logika sederhana: Jika harga naik (current > open) DAN OI di kedua bursa besar (indikasi uang baru masuk)
    if current_price is not None and current_open_price is not None and current_price > current_open_price and binance_oi > 100000000 and bybit_oi > 100000000: # Contoh ambang batas OI
        confluences['oi_increasing_with_price'] = True
        signal_strength['reason'].append("Open Interest: Increasing with rising price (Bullish confirmation).")
        logger.debug(f"Open Interests: Binance {binance_oi}, Bybit {bybit_oi}")

    # Long/Short Ratio (Binance Futures & Bybit) - Kontrarian Bullish
    # Biasanya jika rasio long terlalu tinggi, itu bisa menjadi sinyal reversal (sell).
    # Untuk buy, kita mencari rasio long yang rendah atau berbalik naik dari titik rendah.
    binance_ls_account_ratio = float(binance_futures_data.get("long_short_account_ratio", [{}])[0].get('longShortRatio', 1.0)) if binance_futures_data.get("long_short_account_ratio") else 1.0
    bybit_ls_result = bybit_data.get("long_short_ratio")
    bybit_ls_ratio = float(bybit_ls_result.get('result', {}).get('list', [{}])[0].get('longShortRatio', 1.0)) if bybit_ls_result and bybit_ls_result.get('result') and bybit_ls_result['result'].get('list') else 1.0

    # Contoh: Jika rasio long/short mendekati 1.0 (seimbang) atau sedikit di bawah 1.0 dan mulai naik
    # Atau jika sudah sangat rendah (bearish ekstrem) dan berbalik naik
    if (binance_ls_account_ratio < 1.05 and bybit_ls_ratio < 1.05) and (binance_ls_account_ratio > 0.95 or bybit_ls_ratio > 0.95): # Misal, rasio cenderung seimbang
        confluences['long_short_ratio_bullish_divergence'] = True
        signal_strength['reason'].append("Long/Short Ratio: Relatively balanced or slightly bullish bias.")
        logger.debug(f"Long/Short Ratios: Binance {binance_ls_account_ratio:.2f}, Bybit {bybit_ls_ratio:.2f}")

    # Taker Buy/Sell Volume (Binance Futures) - Dominasi Taker Buy
    taker_buy_sell_ratio = float(binance_futures_data.get("taker_buy_sell_volume", [{}])[0].get('buySellRatio', 0.5)) if binance_futures_data.get("taker_buy_sell_volume") else 0.5
    if taker_buy_sell_ratio > 0.55: # Lebih banyak taker buy
        confluences['taker_buy_volume_dominant'] = True
        signal_strength['reason'].append(f"Taker Volume: Buy Volume Dominant ({taker_buy_sell_ratio:.2f} ratio).")
        logger.debug(f"Taker Buy/Sell Ratio: {taker_buy_sell_ratio:.2f}")

    # --- Kombinasi Logika Konfluensi untuk Sinyal BELI ---
    # Sinyal Sangat Kuat (Strong Buy)
    # Membutuhkan tren bullish, momentum, struktur break, DAN reaksi di POI (OB/FVG),
    # Serta konfirmasi dari likuiditas atau BB, DAN minimal 2 dari sinyal tambahan.
    if (confluences['ema_bullish_trend'] and
        confluences['macd_bullish_momentum'] and
        confluences['rsi_not_overbought'] and # RSI tidak overbought (bisa normal/oversold)
        confluences['stoch_bullish_momentum'] and
        confluences['smc_structure_break'] and
        (confluences['price_reacting_to_ob'] or confluences['price_reacting_to_fvg']) and
        (confluences['liquidity_grab_low'] or confluences['bb_bullish_signal'])):
        
        additional_bullish_signals = sum([
            confluences['ob_support_strong'],
            confluences['funding_rate_bullish'],
            confluences['oi_increasing_with_price'],
            confluences['long_short_ratio_bullish_divergence'],
            confluences['taker_buy_volume_dominant']
        ])
        
        if additional_bullish_signals >= 2: # Setidaknya 2 sinyal tambahan
            signal_strength['type'] = 'strong_buy'
            signal_strength['reason'].append(f"Strong Confluence: All major conditions met (Trend, Momentum, Structure Break, POI reaction, Liquidity/BB) + {additional_bullish_signals} additional bullish signals.")
            logger.debug("Strong Buy Signal Detected!")
            return signal_strength

    # Sinyal Kuat (Moderate Buy)
    # Membutuhkan tren bullish, struktur break, dan setidaknya satu momentum/BB positif,
    # PLUS reaksi di POI, ATAU likuiditas terambil, DAN minimal 1 dari sinyal tambahan.
    if (confluences['ema_bullish_trend'] and
        confluences['smc_structure_break'] and
        (confluences['macd_bullish_momentum'] or confluences['stoch_bullish_momentum'] or confluences['bb_bullish_signal']) and
        (confluences['price_reacting_to_ob'] or confluences['price_reacting_to_fvg'] or confluences['liquidity_grab_low'])):
        
        additional_bullish_signals = sum([
            confluences['ob_support_strong'],
            confluences['funding_rate_bullish'],
            confluences['oi_increasing_with_price'],
            confluences['long_short_ratio_bullish_divergence'],
            confluences['taker_buy_volume_dominant']
        ])

        if additional_bullish_signals >= 1: # Setidaknya 1 sinyal tambahan
            signal_strength['type'] = 'moderate_buy'
            signal_strength['reason'].append(f"Moderate Confluence: Trend, Structure, Momentum/BB alignment, with POI/Liquidity interaction + {additional_bullish_signals} additional bullish signals.")
            logger.debug("Moderate Buy Signal Detected.")
            return signal_strength

    # Sinyal Potensial (Weak Buy / Entry Confirmation)
    # Membutuhkan reaksi di POI DENGAN momentum positif ATAU likuiditas terambil
    # ATAU jika ada 3+ sinyal tambahan yang kuat tanpa POI/SMC
    if (confluences['price_reacting_to_ob'] or confluences['price_reacting_to_fvg'] or confluences['liquidity_grab_low']) and \
       (confluences['rsi_not_overbought'] or confluences['stoch_bullish_momentum'] or confluences['bb_bullish_signal']):
        signal_strength['type'] = 'potential_buy'
        signal_strength['reason'].append("Potential Confluence: Price reacting at POI/Liquidity with momentum/BB confirmation.")
        logger.debug("Potential Buy Signal Detected.")
        return signal_strength

    logger.debug("No Buy Signal based on current confluence.")
    return signal_strength


def check_sell_confluence(classic_indicators: dict, smc_signals: dict, current_price: float, current_open_price: float, market_data_additional: dict) -> dict:
    """
    Menentukan sinyal JUAL berdasarkan konfluensi antara indikator klasik, sinyal SMC,
    dan data pasar tambahan (orderbook, funding, OI, dll.).
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

    # --- Ambil Data Market Tambahan ---
    binance_spot_data = market_data_additional.get("binance_spot", {})
    binance_futures_data = market_data_additional.get("binance_futures", {})
    bybit_data = market_data_additional.get("bybit", {})

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
        'bb_bearish_signal': False,
        # Sinyal dari data market tambahan
        'ob_resistance_strong': False, # Orderbook resistance kuat (dinding jual)
        'funding_rate_bearish': False,
        'oi_increasing_with_price_drop': False,
        'long_short_ratio_bearish_divergence': False, # Misal, rasio long terlalu tinggi/berbalik turun
        'taker_sell_volume_dominant': False
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
    if rsi_value is not None and rsi_value > 30: # Not oversold (bisa normal atau overbought)
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
        last_eq_high_level = min(eq_zone_data['eq_high']) # Ambil equal high yang paling rendah/terbaru
        # Jika lilin menembus equal high dan kemudian close di bawahnya (reversal)
        if current_open_price > last_eq_high_level and current_price < last_eq_high_level and current_price > (last_eq_high_level * 0.995): # Close sedikit di bawah
            confluences['liquidity_grab_high'] = True
            signal_strength['reason'].append(f"SMC: Equal High ({last_eq_high_level:.2f}) swept and reversed (liquidity grab).")
        elif _is_price_near_zone(current_price, [last_eq_high_level, last_eq_high_level], tolerance_percent=0.001):
            confluences['liquidity_grab_high'] = True # Masih di dekatnya, potensi penarikan
            signal_strength['reason'].append(f"SMC: Price near Equal High ({last_eq_high_level:.2f}) (potential liquidity).")

    # --- Evaluasi Data Market Tambahan untuk Sinyal JUAL ---
    # Orderbook (Binance Spot) - Deteksi Dinding Jual (Strong Ask Wall)
    binance_orderbook = binance_spot_data.get("orderbook")
    if binance_orderbook and binance_orderbook.get('asks'):
        top_asks = sorted([float(a[0]) for a in binance_orderbook['asks']])
        top_ask_price = top_asks[0] if top_asks else float('inf')

        # Contoh: Cek apakah ada ask yang sangat besar di dekat harga saat ini
        if current_price and top_ask_price and (top_ask_price - current_price) / current_price < 0.005: # within 0.5%
            top_ask_volume = sum([float(a[1]) for a in binance_orderbook['asks'][:5]]) # Sum volume 5 ask teratas
            if top_ask_volume > 50 * current_price: # Contoh ambang batas volume
                confluences['ob_resistance_strong'] = True
                signal_strength['reason'].append("Orderbook: Strong Ask Wall / Resistance detected near current price.")
                logger.debug(f"Strong Ask Wall Detected: {top_ask_volume:.2f} at {top_ask_price:.2f}")

    # Funding Rate (Binance Futures & Bybit) - Sentimen Bearish
    binance_fr = float(binance_futures_data.get("funding_rate", [{}])[0].get('fundingRate', 0)) if binance_futures_data.get("funding_rate") else 0
    bybit_fr_result = bybit_data.get("funding_rate")
    bybit_fr = float(bybit_fr_result.get('result', {}).get('list', [{}])[0].get('fundingRate', 0)) if bybit_fr_result and bybit_fr_result.get('result') and bybit_fr_result['result'].get('list') else 0

    if binance_fr < -0.0001 or bybit_fr < -0.0001: # Funding rate negatif signifikan
        confluences['funding_rate_bearish'] = True
        signal_strength['reason'].append("Funding Rate: Negative (Bearish Sentiment).")
        logger.debug(f"Funding Rates: Binance {binance_fr:.5f}, Bybit {bybit_fr:.5f}")

    # Open Interest (Binance Futures & Bybit) - OI Meningkat dengan Harga Turun
    binance_oi = float(binance_futures_data.get("open_interest", {}).get('openInterest', 0)) if binance_futures_data.get("open_interest") else 0
    bybit_oi_result = bybit_data.get("open_interest")
    bybit_oi = float(bybit_oi_result.get('result', {}).get('list', [{}])[0].get('openInterest', 0)) if bybit_oi_result and bybit_oi_result.get('result') and bybit_oi_result['result'].get('list') else 0

    if current_price is not None and current_open_price is not None and current_price < current_open_price and binance_oi > 100000000 and bybit_oi > 100000000: # Contoh ambang batas OI
        confluences['oi_increasing_with_price_drop'] = True
        signal_strength['reason'].append("Open Interest: Increasing with falling price (Bearish confirmation).")
        logger.debug(f"Open Interests: Binance {binance_oi}, Bybit {bybit_oi}")

    # Long/Short Ratio (Binance Futures & Bybit) - Kontrarian Bearish
    binance_ls_account_ratio = float(binance_futures_data.get("long_short_account_ratio", [{}])[0].get('longShortRatio', 1.0)) if binance_futures_data.get("long_short_account_ratio") else 1.0
    bybit_ls_result = bybit_data.get("long_short_ratio")
    bybit_ls_ratio = float(bybit_ls_result.get('result', {}).get('list', [{}])[0].get('longShortRatio', 1.0)) if bybit_ls_result and bybit_ls_result.get('result') and bybit_ls_result['result'].get('list') else 1.0

    # Contoh: Jika rasio long/short sangat tinggi (misal > 1.1) atau berbalik turun dari titik tinggi
    if (binance_ls_account_ratio > 1.1 or bybit_ls_ratio > 1.1) and (binance_ls_account_ratio < 1.25 or bybit_ls_ratio < 1.25): # Rasio long cukup tinggi
        confluences['long_short_ratio_bearish_divergence'] = True
        signal_strength['reason'].append("Long/Short Ratio: Relatively high long bias or starting to decrease (Bearish sentiment).")
        logger.debug(f"Long/Short Ratios: Binance {binance_ls_account_ratio:.2f}, Bybit {bybit_ls_ratio:.2f}")

    # Taker Buy/Sell Volume (Binance Futures) - Dominasi Taker Sell
    taker_buy_sell_ratio = float(binance_futures_data.get("taker_buy_sell_volume", [{}])[0].get('buySellRatio', 0.5)) if binance_futures_data.get("taker_buy_sell_volume") else 0.5
    if taker_buy_sell_ratio < 0.45: # Lebih banyak taker sell
        confluences['taker_sell_volume_dominant'] = True
        signal_strength['reason'].append(f"Taker Volume: Sell Volume Dominant ({taker_buy_sell_ratio:.2f} ratio).")
        logger.debug(f"Taker Buy/Sell Ratio: {taker_buy_sell_ratio:.2f}")

    # --- Kombinasi Logika Konfluensi untuk Sinyal JUAL ---
    # Sinyal Sangat Kuat (Strong Sell)
    if (confluences['ema_bearish_trend'] and
        confluences['macd_bearish_momentum'] and
        confluences['rsi_not_oversold'] and # RSI tidak oversold (bisa normal/overbought)
        confluences['stoch_bearish_momentum'] and
        confluences['smc_structure_break'] and
        (confluences['price_reacting_to_ob'] or confluences['price_reacting_to_fvg']) and
        (confluences['liquidity_grab_high'] or confluences['bb_bearish_signal'])):
        
        additional_bearish_signals = sum([
            confluences['ob_resistance_strong'],
            confluences['funding_rate_bearish'],
            confluences['oi_increasing_with_price_drop'],
            confluences['long_short_ratio_bearish_divergence'],
            confluences['taker_sell_volume_dominant']
        ])
        
        if additional_bearish_signals >= 2: # Setidaknya 2 sinyal tambahan
            signal_strength['type'] = 'strong_sell'
            signal_strength['reason'].append(f"Strong Confluence: All major conditions met (Trend, Momentum, Structure Break, POI reaction, Liquidity/BB) + {additional_bearish_signals} additional bearish signals.")
            logger.debug("Strong Sell Signal Detected!")
            return signal_strength

    # Sinyal Kuat (Moderate Sell)
    if (confluences['ema_bearish_trend'] and
        confluences['smc_structure_break'] and
        (confluences['macd_bearish_momentum'] or confluences['stoch_bearish_momentum'] or confluences['bb_bearish_signal']) and
        (confluences['price_reacting_to_ob'] or confluences['price_reacting_to_fvg'] or confluences['liquidity_grab_high'])):
        
        additional_bearish_signals = sum([
            confluences['ob_resistance_strong'],
            confluences['funding_rate_bearish'],
            confluences['oi_increasing_with_price_drop'],
            confluences['long_short_ratio_bearish_divergence'],
            confluences['taker_sell_volume_dominant']
        ])

        if additional_bearish_signals >= 1: # Setidaknya 1 sinyal tambahan
            signal_strength['type'] = 'moderate_sell'
            signal_strength['reason'].append(f"Moderate Confluence: Trend, Structure, Momentum/BB alignment, with POI/Liquidity interaction + {additional_bearish_signals} additional bearish signals.")
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

def evaluate_market_confluence(market_data: dict) -> dict:
    """
    Mengevaluasi konfluensi keseluruhan berdasarkan indikator klasik, sinyal SMC,
    dan data pasar tambahan yang dikumpulkan.
    Ini adalah fungsi yang akan dipanggil dari modul lain (misalnya, analyzer_entry.py).

    Args:
        market_data (dict): Kamus berisi semua data pasar yang telah dikumpulkan
                            (classic_indicators, smc_signals, current_price, current_open_price,
                            market_data_additional, dll.).

    Returns:
        dict: Hasil analisis konfluensi, berisi 'overall_sentiment' dan 'signals' (daftar alasan).
    """
    logger.info("🔍 Mengevaluasi konfluensi sinyal dari semua data yang tersedia...")

    # Ekstraksi data dari dictionary market_data
    classic_indicators = market_data.get("classic_indicators", {})
    smc_signals = market_data.get("smc_signals", {})
    current_price = market_data.get("current_price")
    current_open_price = market_data.get("current_open_price")
    market_data_additional = market_data.get("market_data_additional", {})

    # Pastikan data esensial tersedia
    if current_price is None or current_open_price is None:
        logger.error("Harga saat ini atau harga pembukaan tidak tersedia. Tidak dapat mengevaluasi konfluensi.")
        return {
            "overall_sentiment": "NO_DATA",
            "signals": {"error": "Missing current price data"}
        }

    # Panggil fungsi cek beli dan jual, meneruskan data tambahan
    buy_strength_result = check_buy_confluence(classic_indicators, smc_signals, current_price, current_open_price, market_data_additional)
    sell_strength_result = check_sell_confluence(classic_indicators, smc_signals, current_price, current_open_price, market_data_additional)

    final_signal_type = 'NEUTRAL'
    final_reason_list = [] # Menggunakan list untuk alasan yang lebih terstruktur

    # Logika untuk memilih sinyal terbaik
    buy_type ength_result.get('type', 'no_signal')
    sell_type = sell_strength_result.get('type', 'no_signal')

    # Prioritas: Strong > Moderate > Potential. Hindari konflik strong.
    if buy_type == 'strong_buy' and sell_type != 'strong_sell':
        final_signal_type = 'BULLISH'
        final_reason_list = buy_strength_result['reason']
    elif sell_type == 'strong_sell' and buy_type != 'strong_buy':
        final_signal_type = 'BEARISH'
        final_reason_list = sell_strength_result['reason']
    elif buy_type == 'moderate_buy' and sell_type not in ['strong_sell', 'moderate_sell']:
        final_signal_type = 'BULLISH'
        final_reason_list = buy_strength_result['reason']
    elif sell_type == 'moderate_sell' and buy_type not in ['strong_buy', 'moderate_buy']:
        final_signal_type = 'BEARISH'
        final_reason_list = sell_strength_result['reason']
    elif buy_type == 'potential_buy' and sell_type == 'no_signal':
        final_signal_type = 'NEUTRAL' # Sinyal potential biasanya tidak cukup kuat untuk overall
        final_reason_list = buy_strength_result['reason']
    elif sell_type == 'potential_sell' and buy_type == 'no_signal':
        final_signal_type = 'NEUTRAL'
        final_reason_list = sell_strength_result['reason']
    elif buy_type != 'no_signal' and sell_type != 'no_signal':
        # Kasus konflik
        logger.warning(f"Sinyal beli ({buy_type}) dan jual ({sell_type}) terdeteksi. Memilih yang dominan atau NETRAL.")
        if buy_type == 'strong_buy' and sell_type == 'strong_sell':
            final_signal_type = 'CONFLICTING' # Konflik kuat, lebih baik tidak trading
            final_reason_list.append("Conflicting strong buy and strong sell signals. Market uncertainty.")
        elif buy_type == 'strong_buy': # Jika buy strong, override sell non-strong
            final_signal_type = 'BULLISH'
            final_reason_list = buy_strength_result['reason']
        elif sell_type == 'strong_sell': # Jika sell strong, override buy non-strong
            final_signal_type = 'BEARISH'
            final_reason_list = sell_strength_result['reason']
        elif buy_type == 'moderate_buy' and sell_type == 'moderate_sell':
            final_signal_type = 'NEUTRAL' # Konflik moderate, lebih baik netral
            final_reason_list.append("Conflicting moderate buy and moderate sell signals.")
        elif buy_type == 'moderate_buy':
            final_signal_type = 'BULLISH'
            final_reason_list = buy_strength_result['reason']
        elif sell_type == 'moderate_sell':
            final_signal_type = 'BEARISH'
            final_reason_list = sell_strength_result['reason']
        else: # Kasus lainnya, misal keduanya 'potential'
            final_signal_type = 'NEUTRAL'
            final_reason_list.append("No clear dominant signal amidst conflicting potential/moderate signals.")
    else:
        # Jika tidak ada sinyal sama sekali
        final_signal_type = 'NEUTRAL'
        final_reason_list.append("No specific confluence signals detected.")
        logger.debug("No confluence signals detected, setting overall sentiment to NEUTRAL.")
    
    logger.info(f"Hasil Konfluensi Akhir: Sentimen: {final_signal_type}, Alasan: {final_reason_list}")
    
    # Mengembalikan dictionary sesuai dengan ekspektasi analyzer_entry.py
    return {
        "overall_sentiment": final_signal_type,
        "signals": final_reason_list # Menggunakan list sebagai alasan
    }

# Jika ingin menguji checker secara terpisah, Anda bisa tambahkan blok if __name__ == "__main__": di sini.
if __name__ == "__main__":
    # Contoh penggunaan dummy untuk pengujian
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
    
    print("\n--- Menguji Confluence Checker ---")

    # --- Skenario BELI Kuat ---
    print("\n--- Skenario BELI Kuat ---")
    mock_data_buy_strong = {
        "classic_indicators": {
            "ema_signal": "strong_bullish", "macd_trend": "bullish", "rsi": 55.0,
            "stoch_signal": "bullish", "bb_signal": "cross_above_middle"
        },
        "smc_signals": {
            "bos_choch": {"type": "bullish_choch"},
            "fvg": {"type": "bullish_fvg", "zone": [190.0, 195.0]},
            "order_block": {"bullish_ob": {"low": 188.0, "high": 192.0}, "bearish_ob": None},
            "eq_zone": {"eq_low": [180.0, 180.5], "eq_high": []}
        },
        "current_price": 193.0,
        "current_open_price": 191.0,
        "market_data_additional": {
            "binance_spot": {"orderbook": {"bids": [["192.9", "1000"], ["192.8", "500"]]}},
            "binance_futures": {
                "funding_rate": [{"fundingRate": "0.0003"}],
                "open_interest": {"openInterest": "1500000000"},
                "taker_buy_sell_volume": [{"buySellRatio": "0.65"}]
            },
            "bybit": {
                "funding_rate": {"result": {"list": [{"fundingRate": "0.0002"}]}},
                "open_interest": {"result": {"list": [{"openInterest": "1300000000"}]}},
                "long_short_ratio": {"result": {"list": [{"longShortRatio": "0.98"}]}}
            }
        }
    }
    result_buy_strong = evaluate_market_confluence(mock_data_buy_strong)
    print(f"Sinyal BELI Kuat: {result_buy_strong}")

    # --- Skenario JUAL Kuat ---
    print("\n--- Skenario JUAL Kuat ---")
    mock_data_sell_strong = {
        "classic_indicators": {
            "ema_signal": "strong_bearish", "macd_trend": "bearish", "rsi": 45.0,
            "stoch_signal": "bearish", "bb_signal": "cross_below_middle"
        },
        "smc_signals": {
            "bos_choch": {"type": "bearish_choch"},
            "fvg": {"type": "bearish_fvg", "zone": [205.0, 210.0]},
            "order_block": {"bullish_ob": None, "bearish_ob": {"low": 208.0, "high": 212.0}},
            "eq_zone": {"eq_low": [], "eq_high": [220.0, 220.5]}
        },
        "current_price": 207.0,
        "current_open_price": 209.0,
        "market_data_additional": {
            "binance_spot": {"orderbook": {"asks": [["207.1", "1200"], ["207.2", "600"]]}},
            "binance_futures": {
                "funding_rate": [{"fundingRate": "-0.0002"}],
                "open_interest": {"openInterest": "1600000000"},
                "taker_buy_sell_volume": [{"buySellRatio": "0.35"}]
            },
            "bybit": {
                "funding_rate": {"result": {"list": [{"fundingRate": "-0.0003"}]}},
                "open_interest": {"result": {"list": [{"openInterest": "1400000000"}]}},
                "long_short_ratio": {"result": {"list": [{"longShortRatio": "1.15"}]}}
            }
        }
    }
    result_sell_strong = evaluate_market_confluence(mock_data_sell_strong)
    print(f"Sinyal JUAL Kuat: {result_sell_strong}")

    # --- Skenario NETRAL (No Signal) ---
    print("\n--- Skenario NETRAL (No Signal) ---")
    mock_data_neutral = {
        "classic_indicators": {
            "ema_signal": "neutral", "macd_trend": "neutral", "rsi": 50.0,
            "stoch_signal": "neutral", "bb_signal": "normal"
        },
        "smc_signals": {
            "bos_choch": {"type": "no_break"}, "fvg": {}, "order_block": {}, "eq_zone": {}
        },
        "current_price": 100.0,
        "current_open_price": 100.0,
        "market_data_additional": {
            "binance_spot": {"orderbook": {"bids": [], "asks": []}},
            "binance_futures": {"funding_rate": [], "open_interest": {}, "taker_buy_sell_volume": []},
            "bybit": {"funding_rate": {"result": {"list": []}}, "open_interest": {"result": {"list": []}}, "long_short_ratio": {"result": {"list": []}}}
        }
    }
    result_neutral = evaluate_market_confluence(mock_data_neutral)
    print(f"Sinyal NETRAL: {result_neutral}")

    # --- Skenario Konflik (Strong Buy dan Strong Sell) ---
    print("\n--- Skenario Konflik (Strong Buy dan Strong Sell) ---")
    # Menggabungkan kondisi dari skenario beli kuat dan jual kuat (ini sangat tidak mungkin di pasar nyata pada waktu yang sama)
    # Ini untuk menguji logika penanganan konflik
    mock_data_conflicting = {
        "classic_indicators": {
            "ema_signal": "strong_bullish", "macd_trend": "bullish", "rsi": 55.0,
            "stoch_signal": "bullish", "bb_signal": "cross_above_middle"
        }, # Kombinasi kondisi, bisa juga dibuat netral
        "smc_signals": {
            "bos_choch": {"type": "bullish_choch"}, # Atau bisa buat bullish dan bearish FVG/OB muncul bersamaan
            "fvg": {"type": "bullish_fvg", "zone": [190.0, 195.0]},
            "order_block": {"bullish_ob": {"low": 188.0, "high": 192.0}, "bearish_ob": {"low": 196.0, "high": 199.0}}, # Contoh konflik OB
            "eq_zone": {"eq_low": [180.0], "eq_high": [200.0]}
        },
        "current_price": 193.0,
        "current_open_price": 191.0,
        "market_data_additional": {
            "binance_spot": {"orderbook": {"bids": [["192.9", "1000"]], "asks": [["193.1", "1200"]]}}, # Konflik Orderbook
            "binance_futures": {
                "funding_rate": [{"fundingRate": "0.0003"}], # Bullish
                "open_interest": {"openInterest": "1500000000"},
                "taker_buy_sell_volume": [{"buySellRatio": "0.65"}] # Bullish
            },
            "bybit": {
                "funding_rate": {"result": {"list": [{"fundingRate": "-0.0003"}]}}, # Bearish
                "open_interest": {"result": {"list": [{"openInterest": "1400000000"}]}},
                "long_short_ratio": {"result": {"list": [{"longShortRatio": "1.15"}]}} # Bearish
            }
        }
    }
    result_conflicting = evaluate_market_confluence(mock_data_conflicting)
    print(f"Sinyal KONFLIK: {result_conflicting}")
