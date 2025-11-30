"""
AgroLLM-Urfa Light - 1. Gün
Veri Toplama (OpenWeather + NDVI)
"""

import requests
import pandas as pd
from datetime import datetime

# =========================
# 1️⃣ OpenWeather API
# =========================
API_KEY = "877bc7ea47f1d8c752fec1694b108062"
CITY = "Sanliurfa,TR"

# API endpoint
url = f"http://api.openweathermap.org/data/2.5/weather?q={CITY}&appid={API_KEY}&units=metric&lang=tr"

response = requests.get(url)

if response.status_code == 200:
    data = response.json()
    weather = {
        "şehir": data["name"],
        "tarih": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "sıcaklık_(°C)": data["main"].get("temp", None),
        "nem_(%)": data["main"]["humidity"],
        "rüzgar_hızı_(m/s)": data["wind"]["speed"],
        "hava_durumu": data["weather"][0]["description"],
    }

    df = pd.DataFrame([weather])
    df.to_csv("weather_data.csv", index=False, encoding="utf-8-sig")

    print("✅ Hava verisi başarıyla alındı ve kaydedildi:")
    print(df)
else:
    print("❌ OpenWeather API hatası:", response.status_code)


# =========================
# 2️⃣ Sentinel NDVI (örnek veri)
# =========================
ndvi_data = {
    "bölge": "Şanlıurfa",
    "ortalama_ndvi": 0.52,  # placeholder değer
    "kaynak": "Sentinel-2 (örnek)",
    "tarih": datetime.now().strftime("%Y-%m-%d"),
}

pd.DataFrame([ndvi_data]).to_csv("ndvi_data.csv", index=False, encoding="utf-8-sig")

print("\n✅ NDVI verisi (örnek) kaydedildi: ndvi_data.csv")
