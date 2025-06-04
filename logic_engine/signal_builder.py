# === FILE: logic_engine/signal_builder.py ===
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__) # Mendapatkan logger untuk modul ini

# Import fungsi yang sudah disempurnakan dari confluence_checker
from logic_engine.confluence_checker import check_buy_confluence, check_sell_confluence 

# Penting: Impor fungsi helper yang dibutuhkan dari confluence_checker
from logic_engine.confluence_checker import _is_price_in_zone, _is_price_near_zone, _is_price_entering_zone 

def generate_trading_signal(
    symbol: str,
    timeframe: str,
    classic_indicators: dict,
    smc_signals: dict,
    df: pd.DataFrame, # Menambahkan DataFrame sebagai argumen
    current_price: float,
    current_open_price: float # Menambahkan open price
) -> dict:
    """
    Membuat ringkasan sinyal trading yang komprehensif berdasarkan hasil analisis.
    
    Args:
        symbol (str): Simbol aset (misal, "BTC/USDT").
        timeframe (str): Timeframe analisis (misal, "1h").
        classic_indicators (dict): Hasil dari calculate_indicators.
        smc_signals (dict): Hasil dari analyze_smc_structure.
        df (pd.DataFrame): DataFrame harga lengkap (untuk mengambil swing points).
        current_price (float): Harga penutupan candle terakhir.
        current_open_price (float): Harga pembukaan candle terakhir.

    Returns:
        dict: Detail sinyal trading (signal type, strength, entry, SL, TPs, reason).
    """
    logger.info("⚙️ Membangun sinyal trading...")

    # Mendapatkan hasil konfluensi dari checker
    buy_confluence = check_buy_confluence(classic_indicators, smc_signals, current_price, current_open_price)
    sell_confluence = check_sell_confluence(classic_indicators, smc_signals, current_price, current_open_price)

    signal_type = "NO_SIGNAL"
    signal_strength = "none"
    reason = "Konfluensi belum cukup untuk sinyal valid."
    entry_price = current_price # Default entry adalah harga saat ini
    stop_loss = None
    take_profit_1 = None
    take_profit_2 = None
    take_profit_3 = None # Tambahan TP3 untuk profit yang lebih tinggi
    risk_reward_ratio = None
    
    # Ambil swing low/high terakhir untuk SL yang lebih dinamis
    last_swing_low_price = None
    last_swing_high_price = None

    # Mengambil swing points dari DataFrame jika tersedia
    if smc_signals.get('swing_points') and 'swing_lows' in smc_signals['swing_points']:
        # Filter swing lows yang terjadi sebelum atau pada waktu candle terakhir
        # Pastikan list swing_lows berisi timestamp yang valid
        relevant_swing_lows_timestamps = [
            ts for ts in smc_signals['swing_points']['swing_lows'] 
            if isinstance(ts, pd.Timestamp) and ts <= df.index[-1]
        ]
        if relevant_swing_lows_timestamps:
            last_swing_low_idx = relevant_swing_lows_timestamps[-1]
            if last_swing_low_idx in df.index: # Pastikan timestamp ada di index DataFrame
                last_swing_low_price = df.loc[last_swing_low_idx]['low']
            else:
                logger.debug(f"Timestamp swing low {last_swing_low_idx} tidak ada di DataFrame.")
                
    if smc_signals.get('swing_points') and 'swing_highs' in smc_signals['swing_points']:
        # Filter swing highs yang terjadi sebelum atau pada waktu candle terakhir
        # Pastikan list swing_highs berisi timestamp yang valid
        relevant_swing_highs_timestamps = [
            ts for ts in smc_signals['swing_points']['swing_highs'] 
            if isinstance(ts, pd.Timestamp) and ts <= df.index[-1]
        ]
        if relevant_swing_highs_timestamps:
            last_swing_high_idx = relevant_swing_highs_timestamps[-1]
            if last_swing_high_idx in df.index: # Pastikan timestamp ada di index DataFrame
                last_swing_high_price = df.loc[last_swing_high_idx]['high']
            else:
                logger.debug(f"Timestamp swing high {last_swing_high_idx} tidak ada di DataFrame.")
    
    # Ambil nilai ATR terbaru
    atr_value = classic_indicators.get('ATR')
    # Faktor ATR untuk SL/TP. Umumnya 1.5 - 2.5 kali ATR.
    atr_sl_factor = 1.5 
    atr_tp_factor_1 = 1.5 # Contoh RRR 1:1 jika pakai ATR
    atr_tp_factor_2 = 3.0 # Contoh RRR 1:2
    atr_tp_factor_3 = 4.5 # Contoh RRR 1:3

    # --- Logika Sinyal BELI ---
    if buy_confluence['type'] != 'no_signal':
        signal_type = "BUY"
        signal_strength = buy_confluence['type']
        reason = "Konfluensi Bullish: " + ", ".join(buy_confluence['reason'])

        # Menentukan Entry Price yang Ideal
        bullish_ob = smc_signals.get("order_block", {}).get("bullish_ob")
        fvg_data = smc_signals.get("fvg", {})
        
        # Prioritaskan entry di POI jika harga saat ini berada di dalamnya atau baru masuk
        if bullish_ob and bullish_ob.get('low') is not None and bullish_ob.get('high') is not None:
            if _is_price_in_zone(current_price, [bullish_ob['low'], bullish_ob['high']]):
                entry_price = (bullish_ob['low'] + bullish_ob['high']) / 2 # Mid-point OB
                reason += " | Entry ideal di Bullish OB."
        
        # Jika belum ada entry dari OB, coba FVG
        if entry_price == current_price: # Cek jika entry_price masih default
            if fvg_data and fvg_data.get('type') == 'bullish_fvg' and fvg_data.get('zone'): 
                 if _is_price_in_zone(current_price, fvg_data['zone']):
                    entry_price = (fvg_data['zone'][0] + fvg_data['zone'][1]) / 2 # Mid-point FVG
                    reason += " | Entry ideal di Bullish FVG."
        # Jika tidak ada interaksi dengan POI, entry_price tetap current_price (harga penutupan)

        # Menentukan Stop Loss untuk sinyal BELI
        # Prioritas: OB low -> Swing Low -> ATR -> Fallback
        if bullish_ob and bullish_ob.get('low') is not None: 
            stop_loss = bullish_ob['low'] * 0.995 # Sedikit di bawah low OB untuk keamanan
            reason += " | SL based on Bullish OB."
        elif last_swing_low_price is not None:
            stop_loss = last_swing_low_price * 0.995 # Sedikit di bawah swing low terakhir
            reason += " | SL based on Last Swing Low."
        elif atr_value is not None and atr_value > 0:
            stop_loss = entry_price - (atr_value * atr_sl_factor)
            reason += " | SL based on ATR."
        else:
            stop_loss = current_price * 0.98 # Fallback: 2% di bawah harga saat ini
            reason += " | SL based on Percentage Fallback."


    # --- Logika Sinyal JUAL ---
    elif sell_confluence['type'] != 'no_signal':
        signal_type = "SELL"
        signal_strength = sell_confluence['type']
        reason = "Konfluensi Bearish: " + ", ".join(sell_confluence['reason'])

        # Menentukan Entry Price yang Ideal
        bearish_ob = smc_signals.get("order_block", {}).get("bearish_ob")
        fvg_data = smc_signals.get("fvg", {})

        if bearish_ob and bearish_ob.get('low') is not None and bearish_ob.get('high') is not None:
            if _is_price_in_zone(current_price, [bearish_ob['low'], bearish_ob['high']]):
                entry_price = (bearish_ob['low'] + bearish_ob['high']) / 2 # Mid-point OB
                reason += " | Entry ideal di Bearish OB."
        
        # Jika belum ada entry dari OB, coba FVG
        if entry_price == current_price: # Cek jika entry_price masih default
            if fvg_data and fvg_data.get('type') == 'bearish_fvg' and fvg_data.get('zone'): 
                 if _is_price_in_zone(current_price, fvg_data['zone']):
                    entry_price = (fvg_data['zone'][0] + fvg_data['zone'][1]) / 2 # Mid-point FVG
                    reason += " | Entry ideal di Bearish FVG."
        # Jika tidak ada interaksi dengan POI, entry_price tetap current_price

        # Menentukan Stop Loss untuk sinyal JUAL
        # Prioritas: OB high -> Swing High -> ATR -> Fallback
        if bearish_ob and bearish_ob.get('high') is not None: # Pastikan 'high' ada
            stop_loss = bearish_ob['high'] * 1.005 # Sedikit di atas high OB untuk keamanan
            reason += " | SL based on Bearish OB."
        elif last_swing_high_price is not None:
            stop_loss = last_swing_high_price * 1.005 # Sedikit di atas swing high terakhir
            reason += " | SL based on Last Swing High."
        elif atr_value is not None and atr_value > 0:
            stop_loss = entry_price + (atr_value * atr_sl_factor)
            reason += " | SL based on ATR."
        else:
            stop_loss = current_price * 1.02 # Fallback: 2% di atas harga saat ini
            reason += " | SL based on Percentage Fallback."

    # --- Hitung Take Profit berdasarkan Risk-Reward Ratio (RRR) atau ATR ---
    if stop_loss is not None and entry_price is not None and signal_type != "NO_SIGNAL":
        risk_per_unit = abs(entry_price - stop_loss)
        
        if risk_per_unit > 0: # Pastikan ada risiko yang terukur
            # TP berdasarkan RRR
            if signal_type == "BUY":
                take_profit_1 = entry_price + (risk_per_unit * 1.0)
                take_profit_2 = entry_price + (risk_per_unit * 2.0)
                take_profit_3 = entry_price + (risk_per_unit * 3.0)
            else: # SELL
                take_profit_1 = entry_price - (risk_per_unit * 1.0)
                take_profit_2 = entry_price - (risk_per_unit * 2.0)
                take_profit_3 = entry_price - (risk_per_unit * 3.0)
            
            # Jika ada ATR, bisa juga menggunakan ATR untuk TP sebagai alternatif atau konfirmasi
            # Contoh: jika TP RRR lebih konservatif dari TP ATR, gunakan yang RRR
            # Atau gunakan rata-rata, dsb. Untuk saat ini, kita tetap pakai RRR utama
            # Anda bisa menambahkan logika di sini jika ingin TP mempertimbangkan ATR juga.
            # if atr_value is not None and atr_value > 0:
            #      if signal_type == "BUY":
            #          tp_atr_1 = entry_price + (atr_value * atr_tp_factor_1)
            #          take_profit_1 = min(take_profit_1, tp_atr_1) # Pilih yang lebih rendah untuk keamanan BUY
            #      else: # SELL
            #          tp_atr_1 = entry_price - (atr_value * atr_tp_factor_1)
            #          take_profit_1 = max(take_profit_1, tp_atr_1) # Pilih yang lebih tinggi untuk keamanan SELL
                 
            risk_reward_ratio = f"1:{round(abs(entry_price - take_profit_1) / risk_per_unit, 2)}" # Hitung RRR untuk TP1
        else:
            reason += " | Risk per unit is zero, cannot calculate proper TP/SL."

    # Format output (pastikan pembulatan hanya jika nilai tidak None)
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "signal": signal_type,
        "strength": signal_strength,
        "entry_price": round(entry_price, 4) if entry_price is not None else None,
        "stop_loss": round(stop_loss, 4) if stop_loss is not None else None,
        "take_profit_1": round(take_profit_1, 4) if take_profit_1 is not None else None,
        "take_profit_2": round(take_profit_2, 4) if take_profit_2 is not None else None,
        "take_profit_3": round(take_profit_3, 4) if take_profit_3 is not None else None,
        "risk_reward_ratio_base": risk_reward_ratio, # RRR berdasarkan TP1
        "reason": reason
    }
