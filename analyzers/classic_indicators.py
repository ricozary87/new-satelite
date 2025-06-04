import pandas as pd
import ta

def calculate_indicators(df):
    """
    Menghitung indikator klasik yang ditingkatkan untuk sinyal yang lebih tajam dan berbobot:
    EMA (9, 21, 50, 100, 200), RSI, MACD, Bollinger Bands, Stochastic RSI.
    Setiap indikator akan memiliki sinyal yang lebih granular untuk konfluensi yang lebih baik.

    Args:
        df (pd.DataFrame): DataFrame OHLCV dengan kolom ['open', 'high', 'low', 'close', 'volume'].
                          Membutuhkan minimal 200 candle untuk perhitungan indikator jangka panjang.

    Returns:
        dict: Sebuah dictionary berisi semua indikator yang dihitung dan sinyal terbaru.
              Mengembalikan None jika DataFrame kosong, tidak memiliki kolom 'close', atau data tidak cukup.
    """
    results = {}

    # Validasi data: Pastikan DataFrame memiliki kolom 'close' dan cukup data
    # EMA 200 membutuhkan setidaknya 200 candle.
    if df.empty or 'close' not in df.columns or len(df) < 200:
        print("Error: DataFrame kosong, tidak memiliki kolom 'close', atau data tidak cukup untuk perhitungan indikator.")
        return None

    close = df['close']
    high = df['high']
    low = df['low']

    # --- EMA (Exponential Moving Average) ---
    # Menghitung beberapa periode EMA untuk mengidentifikasi tren jangka pendek hingga panjang
    results['ema_9'] = ta.trend.ema_indicator(close, window=9).iloc[-1]
    results['ema_21'] = ta.trend.ema_indicator(close, window=21).iloc[-1]
    results['ema_50'] = ta.trend.ema_indicator(close, window=50).iloc[-1]
    results['ema_100'] = ta.trend.ema_indicator(close, window=100).iloc[-1]
    results['ema_200'] = ta.trend.ema_indicator(close, window=200).iloc[-1]

    # Sinyal EMA: Lebih banyak kondisi untuk mengidentifikasi kekuatan dan arah tren
    if (results['ema_9'] > results['ema_21'] and
        results['ema_21'] > results['ema_50'] and
        results['ema_50'] > results['ema_100'] and
        results['ema_100'] > results['ema_200'] and
        close.iloc[-1] > results['ema_9']):
        results['ema_signal'] = 'strong_bullish_aligned' # Semua EMA terurut naik & harga di atas EMA terpendek
    elif (results['ema_9'] < results['ema_21'] and
          results['ema_21'] < results['ema_50'] and
          results['ema_50'] < results['ema_100'] and
          results['ema_100'] < results['ema_200'] and
          close.iloc[-1] < results['ema_9']):
        results['ema_signal'] = 'strong_bearish_aligned' # Semua EMA terurut turun & harga di bawah EMA terpendek
    elif results['ema_9'] > results['ema_21'] and close.iloc[-1] > results['ema_21']:
        results['ema_signal'] = 'bullish_short_term' # EMA pendek bullish & harga konfirm
    elif results['ema_9'] < results['ema_21'] and close.iloc[-1] < results['ema_21']:
        results['ema_signal'] = 'bearish_short_term' # EMA pendek bearish & harga konfirm
    elif (results['ema_50'] > results['ema_200'] and
          results['ema_9'] > results['ema_50']):
        results['ema_signal'] = 'golden_cross_potential' # EMA 50 di atas 200, mengindikasikan tren naik jangka panjang
    elif (results['ema_50'] < results['ema_200'] and
          results['ema_9'] < results['ema_50']):
        results['ema_signal'] = 'death_cross_potential' # EMA 50 di bawah 200, mengindikasikan tren turun jangka panjang
    else:
        results['ema_signal'] = 'neutral_or_ranging_ema' # Tidak ada pola tren yang jelas


    # --- RSI (Relative Strength Index) ---
    rsi = ta.momentum.RSIIndicator(close, window=14).rsi()
    results['rsi'] = rsi.iloc[-1]
    # Sinyal RSI: Overbought/Oversold dan konfirmasi momentum
    if results['rsi'] < 30:
        results['rsi_signal'] = 'oversold'
    elif results['rsi'] > 70:
        results['rsi_signal'] = 'overbought'
    elif results['rsi'] >= 50:
        results['rsi_signal'] = 'bullish_momentum' # RSI di atas 50 mendukung momentum naik
    else:
        results['rsi_signal'] = 'bearish_momentum' # RSI di bawah 50 mendukung momentum turun

    # Sinyal Divergensi RSI: Deteksi dasar potensi pembalikan
    # Membutuhkan cukup data untuk melihat pola dalam beberapa candle terakhir
    results['rsi_divergence'] = 'no_divergence'
    if len(df) >= 10: # Memastikan ada cukup data untuk melihat pola
        # Untuk deteksi divergensi yang lebih robust, biasanya diperlukan fungsi swing point yang lebih canggih.
        # Implementasi ini adalah pendekatan heuristik dasar.
        
        # Bullish Divergence: Harga Lower Low, RSI Higher Low
        # Cek 3 candle terakhir
        if (close.iloc[-1] < close.iloc[-2] and close.iloc[-2] < close.iloc[-3] and # Harga membuat LL
            rsi.iloc[-1] > rsi.iloc[-2] and rsi.iloc[-2] > rsi.iloc[-3]): # RSI membuat HL
            results['rsi_divergence'] = 'potential_bullish_divergence'
        
        # Bearish Divergence: Harga Higher High, RSI Lower High
        if (close.iloc[-1] > close.iloc[-2] and close.iloc[-2] > close.iloc[-3] and # Harga membuat HH
            rsi.iloc[-1] < rsi.iloc[-2] and rsi.iloc[-2] < rsi.iloc[-3]): # RSI membuat LH
            results['rsi_divergence'] = 'potential_bearish_divergence'


    # --- MACD (Moving Average Convergence Divergence) ---
    macd_instance = ta.trend.MACD(close)
    results['macd'] = macd_instance.macd().iloc[-1]
    results['macd_signal_line'] = macd_instance.macd_signal().iloc[-1]
    results['macd_hist'] = macd_instance.macd_diff().iloc[-1]
    
    # Sinyal Trend MACD: Berdasarkan posisi MACD dan histogram
    if results['macd'] > 0 and results['macd_hist'] > 0:
        results['macd_trend'] = 'strong_bullish_momentum' # MACD di atas nol & histogram positif
    elif results['macd'] < 0 and results['macd_hist'] < 0:
        results['macd_trend'] = 'strong_bearish_momentum' # MACD di bawah nol & histogram negatif
    elif results['macd'] > results['macd_signal_line']:
        results['macd_trend'] = 'bullish_momentum' # MACD di atas garis sinyal
    else:
        results['macd_trend'] = 'bearish_momentum' # MACD di bawah garis sinyal
            
    # Sinyal Crossover MACD: Konfirmasi perubahan momentum
    results['macd_crossover_signal'] = 'no_crossover'
    if len(macd_instance.macd()) >= 2: # Pastikan ada data sebelumnya untuk deteksi crossover
        prev_macd = macd_instance.macd().iloc[-2]
        prev_signal = macd_instance.macd_signal().iloc[-2]
        
        if (results['macd'] > results['macd_signal_line'] and prev_macd <= prev_signal):
            results['macd_crossover_signal'] = 'bullish_crossover'
        elif (results['macd'] < results['macd_signal_line'] and prev_macd >= prev_signal):
            results['macd_crossover_signal'] = 'bearish_crossover'
    
    # Catatan: Deteksi divergensi MACD bisa ditambahkan di sini, mirip dengan RSI,
    # namun memerlukan logika yang lebih kompleks untuk mengidentifikasi puncak/lembah.


    # --- Bollinger Bands ---
    bb_instance = ta.volatility.BollingerBands(close)
    results['bb_upper'] = bb_instance.bollinger_hband().iloc[-1]
    results['bb_lower'] = bb_instance.bollinger_lband().iloc[-1]
    results['bb_middle'] = bb_instance.bollinger_mavg().iloc[-1]
    # Menghitung lebar band sebagai persentase dari garis tengah untuk mengukur volatilitas
    results['bb_width'] = (results['bb_upper'] - results['bb_lower']) / results['bb_middle'] * 100 
        
    # Sinyal Bollinger Bands: Posisi harga relatif terhadap pita dan garis tengah
    if close.iloc[-1] >= results['bb_upper']:
        results['bb_signal'] = 'overbought_band_extreme' # Harga di atau di atas pita atas
    elif close.iloc[-1] <= results['bb_lower']:
        results['bb_signal'] = 'oversold_band_extreme' # Harga di atau di bawah pita bawah
    elif close.iloc[-1] > results['bb_middle'] and close.iloc[-2] <= results['bb_middle']:
        results['bb_signal'] = 'cross_above_middle' # Harga memotong garis tengah ke atas
    elif close.iloc[-1] < results['bb_middle'] and close.iloc[-2] >= results['bb_middle']:
        results['bb_signal'] = 'cross_below_middle' # Harga memotong garis tengah ke bawah
    elif close.iloc[-1] > results['bb_middle']:
        results['bb_signal'] = 'above_middle_band' # Harga di atas garis tengah (dukungan)
    elif close.iloc[-1] < results['bb_middle']:
        results['bb_signal'] = 'below_middle_band' # Harga di bawah garis tengah (resistensi)
    else:
        results['bb_signal'] = 'neutral_band_range' # Harga berada di antara pita, tanpa sinyal kuat

    # Sinyal Bollinger Squeeze/Expansion: Deteksi perubahan volatilitas
    results['bb_volatility_signal'] = 'not_enough_data'
    if len(bb_instance.bollinger_wband()) >= 20: # Window default BB adalah 20, jadi butuh setidaknya 20 bar
        # Gunakan rata-rata lebar band historis untuk membandingkan
        bb_widths_history = ta.volatility.bollinger_wband(close, window=20).iloc[-20:-1]
        if not bb_widths_history.empty:
            avg_prev_bb_width = bb_widths_history.mean()
            
            # Deteksi squeeze (penyempitan band)
            if results['bb_width'] < (avg_prev_bb_width * 0.75): # Jika lebar saat ini 25% lebih kecil dari rata-rata
                results['bb_volatility_signal'] = 'squeeze_potential' # Potensi breakout setelah konsolidasi
            # Deteksi expansion (pelebaran band)
            elif results['bb_width'] > (avg_prev_bb_width * 1.25): # Jika lebar saat ini 25% lebih besar dari rata-rata
                results['bb_volatility_signal'] = 'expansion_ongoing' # Volatilitas tinggi, tren sedang berkembang
            else:
                results['bb_volatility_signal'] = 'normal_volatility'


    # --- Stochastic RSI ---
    stochrsi_instance = ta.momentum.StochRSIIndicator(close)
    results['stoch_k'] = stochrsi_instance.stochrsi_k().iloc[-1]
    results['stoch_d'] = stochrsi_instance.stochrsi_d().iloc[-1]
    
    # Sinyal Stochastic RSI: Crossover dan posisi di area overbought/oversold
    if results['stoch_k'] > results['stoch_d']:
        if results['stoch_k'] < 20:
            results['stoch_signal'] = 'oversold_bullish_cross' # Crossover bullish di area oversold (sinyal beli kuat)
        elif results['stoch_k'] > 80:
            results['stoch_signal'] = 'overbought_bullish_momentum' # Momentum bullish di area overbought
        else:
            results['stoch_signal'] = 'bullish_momentum_stoch' # Momentum bullish umum
    elif results['stoch_k'] < results['stoch_d']:
        if results['stoch_k'] > 80:
            results['stoch_signal'] = 'overbought_bearish_cross' # Crossover bearish di area overbought (sinyal jual kuat)
        elif results['stoch_k'] < 20:
            results['stoch_signal'] = 'oversold_bearish_momentum' # Momentum bearish di area oversold
        else:
            results['stoch_signal'] = 'bearish_momentum_stoch' # Momentum bearish umum
    else:
        results['stoch_signal'] = 'neutral_stoch' # Tidak ada arah yang jelas
        
    # Catatan: Deteksi divergensi Stochastic RSI juga bisa ditambahkan di sini.
    
    return results
