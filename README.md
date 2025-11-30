# 👨‍🌾 AgroLLM – Uydu Destekli Tarımsal Karar Sistemi

AgroLLM, **uydu görüntüleri + NDVI + LLM (yapay zeka)** kullanarak çiftçilere ve tarım danışmanlarına **hızlı tarımsal analiz ve öneri** sunmayı amaçlayan bir uygulamadır.

- 🛰️ **Solda**: Esri World_Imagery (ve gerekirse Sentinel-2 True Color) tabanlı uydu görüntüsü  
- 🤖 **Sağda**: OpenAI tabanlı tarımsal analiz ve tavsiyeler  
- 📍 Girdi: Şehir/ilçe, enlem–boylam, alan, tarih aralığı, ürün bilgisi  

---

## 📸 Ekran Görüntüsü

<img width="1916" height="973" alt="Uygulama içi görsel" src="https://github.com/user-attachments/assets/13a336b4-3120-4466-877a-fdfb5e29d357" />

<img width="848" height="700" alt="görsel 2" src="https://github.com/user-attachments/assets/183591f8-b16f-402e-8f2f-d0d793b82f0a" />



---

## ✨ Özellikler

- **Uydu Görüntüsü**
  - Varsayılan: **Esri World_Imagery** doğal renk (true color)
  - Esri hata verirse otomatik olarak **Sentinel-2 True Color** (B04, B03, B02) fallback
- **NDVI Görselleştirme**
  - Sentinel-2 L2A verisi üzerinden NDVI hesaplama
  - NDVI rasterini sahte renk paletiyle görselleştirme
  - NDVI ortalama değeri üzerinden yorumlama
- **Ürün Bazlı Tarımsal Analiz**
  - Seçilen ürün (Buğday, Arpa, Pamuk, Mısır, Mercimek, vb.)
  - Şehir, hava durumu, sıcaklık, nem ve NDVI bilgisine göre:
    - Uygunluk değerlendirmesi
    - Ekim–dikim, sulama, gübreleme, hastalık-zararlı, hasat önerileri
- **Genel Bölgesel Tarım Analizi**
  - Bölgenin iklim ve bitki örtüsüne göre hangi bitkilerin uygun olabileceğine dair genel öneriler
- **Modern ve Kullanışlı Arayüz**
  - Tkinter ile tasarlanmış, kart tabanlı layout
  - Sol tarafta uydu görseli, sağ tarafta LLM çıktısı
  - Basit ama işlevsel kontrol paneli (şehir, lat/lon, tarih, ürün, mod)

---

## 🧱 Teknolojiler

- **Python 3.10+**
- **Tkinter** – Masaüstü arayüz
- **Pillow (PIL)** – Görsel işleme
- **NumPy** – NDVI ve raster işlemleri
- **Sentinel Hub Python SDK** – Sentinel-2 veri erişimi
- **Esri World_Imagery** – Doğal renk uydu görüntüsü
- **OpenAI API** – Tarımsal metin analiz ve öneri
- **OpenWeatherMap API** – Hava durumu verisi
- **Requests / urllib3** – HTTP istekleri

---

## 🔑 Gerekli API Anahtarları

Uygulama çalışmadan önce aşağıdaki API bilgilerine ihtiyacın var:

1. **OpenAI API Key**  
   → https://platform.openai.com  
2. **OpenWeatherMap API Key**  
   → https://openweathermap.org/api  
3. **Sentinel Hub Client ID & Client Secret**  
   → https://www.sentinel-hub.com  

Kod içinde şu kısımda tanımlanıyor:

```python
OPENAI_KEY = "BURAYA_OPENAI_ANAHTARIN"
OPENWEATHER_KEY = "BURAYA_OPENWEATHER_ANAHTARIN"

SH_CLIENT_ID = "BURAYA_SENTINEL_CLIENT_ID"
SH_CLIENT_SECRET = "BURAYA_SENTINEL_CLIENT_SECRET"
