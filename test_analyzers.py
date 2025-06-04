import pandas as pd
from datetime import datetime, timedelta
import numpy as np # Import numpy untuk simulasi data yang lebih baik

# Import fungsi-fungsi dari modul analyzer Anda
from analyzers.classic_indicators import calculate_indicators
from analyzers.smc_structure import analyze_smc_structure, find_swing_points

# --- Contoh Data OHLCV yang Lebih Panjang dan Terstruktur ---
# Kita perlu data yang cukup panjang agar indikator dan SMC bisa dihitung dengan benar.
# Mari kita buat data dummy yang sedikit lebih terstruktur untuk membantu deteksi swing points
num_candles = 300 # Jumlah candle yang cukup untuk EMA 200 dan SMC lookback
start_time = datetime.now() - timedelta(minutes=num_candles * 5) # Misal, timeframe 5 menit

# Membuat data harga dengan sedikit tren dan fluktuasi
prices = np.linspace(100, 200, num_candles) + np.random.normal(0, 5, num_candles)
# Memastikan high, low, close konsisten
highs = prices + np.random.uniform(0, 2, num_candles)
lows = prices - np.random.uniform(0, 2, num_candles)
opens = prices - np.random.uniform(-1, 1, num_candles)
closes = prices + np.random.uniform(-1, 1, num_candles)

data = {
    'open': opens,
    'high': highs,
    'low': lows,
    'close': closes,
    'volume': [1000 + i * 10 + np.random.randint(-200, 200) for i in range(num_candles)]
}
df = pd.DataFrame(data, index=pd.to_datetime([start_time + timedelta(minutes=i * 5) for i in range(num_candles)]))


print("---")
print("📊 [TEST] Classic Indicators:")
print("---")
indicators = calculate_indicators(df)
if indicators:
    for key, value in indicators.items():
        if isinstance(value, (float, int)):
            print(f"  {key}: {value:.4f}")
        else:
            print(f"  {key}: {value}")
else:
    print("  Gagal menghitung indikator klasik.")

print("\n---")
print("📈 [TEST] SMC Structure:")
print("---")
# Panggil fungsi utama analyze_smc_structure
# Anda bisa coba ubah window=5 di analyze_smc_structure jika masih tidak terdeteksi
smc_analysis = analyze_smc_structure(df) 

if smc_analysis:
    for key, value in smc_analysis.items():
        print(f"  {key}: {value}")
else:
    print("  Gagal menganalisis struktur SMC. Pastikan data cukup dan benar.")
