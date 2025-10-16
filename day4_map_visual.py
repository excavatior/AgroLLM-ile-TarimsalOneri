"""
AgroLLM – 4. Gün
Uydu (harita) görüntüsü + NDVI analizi + LLM önerisi
"""

import requests
import folium
from folium.plugins import MiniMap
from geopy.geocoders import Nominatim
from openai import OpenAI
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image
from io import BytesIO
import os

# ==========================
# 1️⃣ API anahtarları
# ==========================
OPENAI_KEY = "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"  # 👈 kendi OpenAI API anahtarını buraya yaz
OW_KEY = "877bc7ea47f1d8c752fec1694b108062"              # 👈 kendi OpenWeather API anahtarını yaz

client = OpenAI(api_key=OPENAI_KEY)

# ==========================
# 2️⃣ Kullanıcıdan şehir al
# ==========================
city = input("📍 Lütfen şehir veya ilçe girin (ör: Şanlıurfa,TR): ") or "Şanlıurfa,TR"

# ==========================
# 3️⃣ Koordinat bul (geopy)
# ==========================
geolocator = Nominatim(user_agent="agrollm")
location = geolocator.geocode(city)
if not location:
    raise ValueError("❌ Konum bulunamadı. Lütfen farklı bir isim deneyin.")

latitude, longitude = location.latitude, location.longitude
print(f"📍 {city} konumu: {latitude:.4f}, {longitude:.4f}")

# ==========================
# 4️⃣ Hava durumu (OpenWeather)
# ==========================
url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={OW_KEY}&units=metric&lang=tr"
res = requests.get(url)
data = res.json()

weather = {
    "şehir": data["name"],
    "sıcaklık_(°C)": data["main"]["temp"],
    "nem_(%)": data["main"]["humidity"],
    "hava_durumu": data["weather"][0]["description"],
}
print(f"🌤 Hava: {weather['hava_durumu']}, {weather['sıcaklık_(°C)']}°C, Nem %{weather['nem_(%)']}")

# ==========================
# 5️⃣ NDVI (örnek oluşturma)
# ==========================
# Uydu NDVI simülasyonu (rastgele yeşil tonlu görsel)
ndvi_array = np.random.rand(100, 100)
plt.imshow(ndvi_array, cmap='YlGn')
plt.axis('off')
plt.savefig("ndvi_map.png", bbox_inches='tight', pad_inches=0)
plt.close()

print("🟩 NDVI haritası oluşturuldu: ndvi_map.png")

# ==========================
# 6️⃣ LLM Önerisi
# ==========================
prompt = f"""
Şehir: {weather['şehir']}
Hava durumu: {weather['hava_durumu']}
Sıcaklık: {weather['sıcaklık_(°C)']} °C
Nem: %{weather['nem_(%)']}
NDVI: ortalama {ndvi_array.mean():.2f}

Verilere göre:
- Sulama gerekliliği
- Bitki sağlığı değerlendirmesi
- Tarımsal tavsiye (kısa)
"""
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": "Sen bir tarım danışmanısın."},
        {"role": "user", "content": prompt}
    ],
    temperature=0.7
)
recommendation = response.choices[0].message.content.strip()

print("\n🌾 **Tarımsal Öneri** 🌾\n")
print(recommendation)

# ==========================
# 7️⃣ Harita oluştur
# ==========================
m = folium.Map(location=[latitude, longitude], zoom_start=10, tiles="Stamen Terrain")
MiniMap().add_to(m)

folium.Marker(
    [latitude, longitude],
    popup=f"<b>{city}</b><br>{weather['hava_durumu']}<br>{weather['sıcaklık_(°C)']}°C, %{weather['nem_(%)']} nem",
    tooltip="Tarım bölgesi"
).add_to(m)

# NDVI görselini haritaya ekle
img = Image.open("ndvi_map.png")
img.save("ndvi_overlay.png")

# Görseli base64 formatında HTML'e göm
import base64
with open("ndvi_overlay.png", "rb") as f:
    img_base64 = base64.b64encode(f.read()).decode("utf-8")

html = f"""
<div style="text-align:center;">
    <h4>🌿 NDVI (Bitki Sağlığı) Haritası</h4>
    <img src="data:image/png;base64,{img_base64}" width="250"/>
    <p><b>LLM Önerisi:</b><br>{recommendation}</p>
</div>
"""
folium.Marker(
    [latitude, longitude],
    popup=folium.Popup(html, max_width=300),
    tooltip="Uydu Görüntüsü + Öneri"
).add_to(m)

m.save("agrollm_map.html")
print("\n✅ Harita oluşturuldu: agrollm_map.html")
print("🌍 Tarayıcıda açmak için: agrollm_map.html dosyasına çift tıkla.")
