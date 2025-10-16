"""
AgroLLM–Urfa Light - 2. Gün
LLM (OpenAI) tabanlı tarımsal öneri üretimi
"""

import pandas as pd
from openai import OpenAI
from datetime import datetime

# ==========================
# 1️⃣ API ANAHTARINI BURAYA YAZ
# ==========================
API_KEY = "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"  # 👈 kendi OpenAI anahtarını buraya yapıştır

client = OpenAI(api_key=API_KEY)

# ==========================
# 2️⃣ Verileri Oku
# ==========================
try:
    weather_df = pd.read_csv("weather_data.csv")
    ndvi_df = pd.read_csv("ndvi_data.csv")
except FileNotFoundError:
    raise FileNotFoundError("❌ Veri dosyaları bulunamadı. Lütfen day1_data_fetch.py dosyasını çalıştırdığından emin ol.")

weather = weather_df.iloc[-1].to_dict()
ndvi = ndvi_df.iloc[-1].to_dict()

# ==========================
# 3️⃣ LLM Girdisini Hazırla
# ==========================
prompt = f"""
Sen bir tarım danışmanısın.
Aşağıdaki verilere göre Şanlıurfa için kısa, sade bir tarımsal öneri üret:

📅 Tarih: {datetime.now().strftime("%d.%m.%Y")}
🌤 Hava durumu: {weather.get('hava_durumu', 'bilinmiyor')}
🌡️ Sıcaklık: {weather.get('sıcaklık_(°C)', 'bilinmiyor')} °C
💧 Nem: {weather.get('nem_(%)', 'bilinmiyor')} %
🌬 Rüzgar: {weather.get('rüzgar_hızı_(m/s)', 'bilinmiyor')} m/s
🌱 NDVI (bitki örtüsü indeksi): {ndvi.get('ortalama_ndvi', 'bilinmiyor')}

Veriye göre:
1. Sulama önerisi yap (gerekli mi, değil mi?)
2. Bitki sağlığı hakkında kısa yorum yap.
3. Hava çok sıcaksa uyarı ver.
4. Açıklama sade, 3-4 cümleyi geçmesin.
"""

# ==========================
# 4️⃣ LLM Çıktısı Al
# ==========================
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": "Sen tarım alanında uzman bir yapay zeka danışmansın."},
        {"role": "user", "content": prompt}
    ],
    temperature=0.6,
)

recommendation = response.choices[0].message.content.strip()

print("\n🌾 **Tarımsal Öneri** 🌾\n")
print(recommendation)

# ==========================
# 5️⃣ Kaydet
# ==========================
with open("ai_recommendation.txt", "w", encoding="utf-8") as f:
    f.write(recommendation)

print("\n✅ Öneri kaydedildi: ai_recommendation.txt")
