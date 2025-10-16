"""
AgroLLM – Masaüstü (LLM öneri + Uydu Görüntüsü)
Uydu: Sentinel Hub → Esri World_Imagery → NASA GIBS → Placeholder
LLM alanı büyük, PanedWindow ile sürükleyip oranı değiştirebilirsin.
"""

import os
from io import BytesIO
from math import cos, radians
from datetime import date, timedelta

import tkinter as tk
from tkinter import ttk, messagebox

import numpy as np
from PIL import Image, ImageTk, ImageDraw
from geopy.geocoders import Nominatim
from openai import OpenAI
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Sentinel Hub
from sentinelhub import (
    SHConfig,
    SentinelHubRequest,
    DataCollection,
    BBox,
    MimeType,
    bbox_to_dimensions,
    CRS,
    MosaickingOrder,
)

# ==========================
# 1) API Anahtarları
# ==========================
OPENAI_KEY = os.getenv("OPENAI_API_KEY", "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")
OPENWEATHER_KEY = os.getenv("OPENWEATHER_KEY", "877bc7ea47f1d8c752fec1694b108062")

# Sentinel Hub kimlik bilgilerin (seninkiler)
SH_CLIENT_ID = os.getenv("SH_CLIENT_ID", "sh-5da78411-ec92-493e-a3fb-feadc061102")
SH_CLIENT_SECRET = os.getenv("SH_CLIENT_SECRET", "po5cA6jNsIUnryOhvKs8JjfNBdpU9ePt")

client = OpenAI(api_key=OPENAI_KEY)

# Sentinel Hub config
sh_cfg = SHConfig()
sh_cfg.sh_client_id = SH_CLIENT_ID
sh_cfg.sh_client_secret = SH_CLIENT_SECRET

# ==========================
# 2) Ürünler
# ==========================
PRODUCTS = [
    "Arpa", "Buğday", "Mercimek", "Mısır", "Pamuk",
    "Biber", "Domates", "Patlıcan", "Antep Fıstığı",
    "Zeytin", "Badem"
]

# ==========================
# HTTP Session (retry)
# ==========================
def _requests_session():
    s = requests.Session()
    retries = Retry(total=3, backoff_factor=1.5,
                    status_forcelist=[429, 500, 502, 503, 504],
                    allowed_methods=["GET"])
    s.mount("https://", HTTPAdapter(max_retries=retries))
    return s

# ==========================
# Hava + NDVI (simülasyon)
# ==========================
def get_weather_and_ndvi(city: str):
    geolocator = Nominatim(user_agent="agrollm_v3")
    location = geolocator.geocode(city)
    if not location:
        messagebox.showwarning("Bilgi", f"{city} bulunamadı, Şanlıurfa alınacak.")
        location = geolocator.geocode("Şanlıurfa,TR")
    lat, lon = location.latitude, location.longitude

    url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={OPENWEATHER_KEY}&units=metric&lang=tr"
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    d = r.json()
    weather = {
        "şehir": city,
        "hava_durumu": d["weather"][0]["description"],
        "sıcaklık": d["main"]["temp"],
        "nem": d["main"]["humidity"],
    }

    ndvi = np.random.rand(100, 100)
    ndvi_avg = round(float(ndvi.mean()), 2)
    return lat, lon, weather, ndvi_avg

# ==========================
# Esri World_Imagery (anahtarsız) – Statik görüntü
# ==========================
def fetch_esri_world_imagery(lat: float, lon: float, width=1000, height=520) -> Image.Image:
    s = _requests_session()
    span = 0.30  # derece cinsinden yaklaşık 30–35 km pencere
    south, west, north, east = lat - span/2, lon - span/2, lat + span/2, lon + span/2
    url = "https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/export"
    params = {
        "bbox": f"{west},{south},{east},{north}",
        "bboxSR": 4326,
        "imageSR": 4326,
        "size": f"{width},{height}",
        "format": "png",
        "f": "image",
        "dpi": 96
    }
    r = s.get(url, params=params, timeout=45)
    r.raise_for_status()
    return Image.open(BytesIO(r.content))

# ==========================
# NASA GIBS fallback (anahtarsız)
# ==========================
def fetch_gibs_snapshot(lat: float, lon: float, width=1000, height=520) -> Image.Image:
    s = _requests_session()
    delta = 0.25  # ~25-30 km pencere
    south, west, north, east = lat - delta, lon - delta, lat + delta, lon + delta
    date_str = date.today().isoformat()
    url = (
        "https://wvs.earthdata.nasa.gov/api/v1/snapshot"
        f"?REQUEST=GetSnapshot&TIME={date_str}&BBOX={south},{west},{north},{east}"
        "&CRS=EPSG:4326"
        "&LAYERS=MODIS_Terra_CorrectedReflectance_TrueColor"
        f"&WRAP=0&FORMAT=image/jpeg&WIDTH={width}&HEIGHT={height}"
    )
    resp = s.get(url, timeout=60)
    resp.raise_for_status()
    return Image.open(BytesIO(resp.content))

# ==========================
# Sentinel Hub – True Color (sürüm uyumlu)
# ==========================
def fetch_sentinel_image(lat: float, lon: float) -> Image.Image:
    """
    Son 30 günde en az bulutlu Sentinel-2 L2A True Color (10 m).
    Sürüm uyuşmazlıklarına karşı iki farklı 'input_data' imzası denenir.
    Başarısız olursa Esri → GIBS → placeholder sırası uygulanır.
    """
    try:
        dist_km = 1.5
        deg_lat = dist_km / 111.32
        deg_lon = dist_km / (111.32 * cos(radians(lat)))
        bbox = BBox([lon - deg_lon, lat - deg_lat, lon + deg_lon, lat + deg_lat], crs=CRS.WGS84)
        size = bbox_to_dimensions(bbox, resolution=10)
        end = date.today()
        start = end - timedelta(days=30)

        evalscript_tc = """
        //VERSION=3
        function setup() {
          return {
            input: [{ bands: ["B04", "B03", "B02"], units: "DN" }],
            output: { bands: 3, sampleType: "UINT8" }
          };
        }
        function evaluatePixel(s) {
          return [
            Math.min(255, 2.5 * s.B04),
            Math.min(255, 2.5 * s.B03),
            Math.min(255, 2.5 * s.B02)
          ];
        }
        """

        # a) Yeni API imzası
        try:
            req = SentinelHubRequest(
                evalscript=evalscript_tc,
                input_data=[
                    SentinelHubRequest.input_data(
                        data_collection=DataCollection.SENTINEL2_L2A,
                        time_interval=(start, end),
                        mosaicking_order=MosaickingOrder.LEAST_CC,
                        data_filter={"maxCloudCoverage": 30},
                    )
                ],
                responses=[SentinelHubRequest.output_response("default", MimeType.PNG)],
                bbox=bbox, size=size, config=sh_cfg,
            )
        except TypeError:
            # b) Eski API imzası
            req = SentinelHubRequest(
                evalscript=evalscript_tc,
                input_data=[
                    SentinelHubRequest.input_data(
                        data_collection=DataCollection.SENTINEL2_L2A,
                        time_interval=(start, end),
                        mosaicking_order="leastCC",
                    )
                ],
                responses=[SentinelHubRequest.output_response("default", MimeType.PNG)],
                bbox=bbox, size=size, config=sh_cfg,
            )

        out = req.get_data()[0]  # numpy array veya bytes
        if isinstance(out, bytes):
            img = Image.open(BytesIO(out))
        else:
            img = Image.fromarray(out)
        return img

    except Exception as e_sentinel:
        # 2) Esri World_Imagery
        try:
            return fetch_esri_world_imagery(lat, lon)
        except Exception as e_esri:
            # 3) GIBS
            try:
                return fetch_gibs_snapshot(lat, lon)
            except Exception as e_gibs:
                # 4) Placeholder
                img = Image.new("RGB", (1000, 520), (233, 239, 230))
                draw = ImageDraw.Draw(img)
                draw.text(
                    (30, 240),
                    f"Uydu görüntüsü alınamadı.\n"
                    f"Sentinel hata: {str(e_sentinel)[:70]}\n"
                    f"Esri hata: {str(e_esri)[:70]}\n"
                    f"GIBS hata: {str(e_gibs)[:70]}",
                    fill=(0, 0, 0),
                )
                return img

def show_satellite_in_label(img: Image.Image):
    img = img.copy()
    img.thumbnail((1100, 520))
    photo = ImageTk.PhotoImage(img)
    sat_label.config(image=photo, text="")
    sat_label.image = photo

# ==========================
# 4) Ürün analizi
# ==========================
def analiz_et():
    city = city_entry.get().strip()
    product = product_combo.get().strip()
    if not city or not product:
        messagebox.showwarning("Uyarı", "Lütfen şehir ve ürün seçin!")
        return
    try:
        sat_label.config(image=None, text="Uydu görüntüsü yükleniyor…")
        root.update_idletasks()

        lat, lon, weather, ndvi_avg = get_weather_and_ndvi(city)

        # ↓↓↓ PROMPTA DOKUNMADIM ↓↓↓
        prompt = f"""
        Ürün: {product}
        Şehir/İlçe: {city}
        Hava durumu: {weather['hava_durumu']}
        Sıcaklık: {weather['sıcaklık']} °C
        Nem: %{weather['nem']}
        NDVI ortalama: {ndvi_avg}

        Bu verilere göre, {product} için öncelikle bu bölgede yetişmiyorsa olumsuz cevap ver. Eğer bu bölgede yetiştiriliyorsa, çiftçi diliyle yazılmış teknik, detaylı bir tarımsal öneri üret.
        """
        # ↑↑↑ PROMPTA DOKUNMADIM ↑↑↑

        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Sen deneyimli bir tarım danışmanısın."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.6
        )
        recommendation = resp.choices[0].message.content.strip()

        sat_img = fetch_sentinel_image(lat, lon)
        show_satellite_in_label(sat_img)

        result_box.config(state="normal")
        result_box.delete("1.0", tk.END)
        result_box.insert(tk.END, recommendation)
        result_box.config(state="disabled")

    except Exception as e:
        messagebox.showerror("Hata", str(e))
        sat_label.config(text="Bir hata oluştu. Uydu görüntüsü yüklenemedi.")

# ==========================
# 5) Genel analiz
# ==========================
def genel_analiz():
    city = city_entry.get().strip()
    if not city:
        messagebox.showwarning("Uyarı", "Lütfen şehir girin!")
        return
    try:
        sat_label.config(image=None, text="Uydu görüntüsü yükleniyor…")
        root.update_idletasks()

        lat, lon, weather, ndvi_avg = get_weather_and_ndvi(city)

        # ↓↓↓ PROMPTA DOKUNMADIM ↓↓↓
        prompt = f"""
        Şehir/İlçe: {city}
        Hava durumu: {weather['hava_durumu']}
        Sıcaklık: {weather['sıcaklık']} °C
        Nem: %{weather['nem']}
        NDVI ortalama: {ndvi_avg}

        Sen Türkiye'deki iklim bölgelerini bilen deneyimli bir tarım danışmanısın.
        Aşağıdaki bilgileri değerlendirerek, sadece o bölgeye uygun yetiştiricilik durumuna göre öneri yap:
        - {city}, {weather['hava_durumu']}, %{weather['nem']}, {ndvi_avg}, {weather['sıcaklık']} °C
        """
        # ↑↑↑ PROMPTA DOKUNMADIM ↑↑↑

        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Sen deneyimli bir tarım danışmanısın."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.6
        )
        recommendation = resp.choices[0].message.content.strip()

        sat_img = fetch_sentinel_image(lat, lon)
        show_satellite_in_label(sat_img)

        result_box.config(state="normal")
        result_box.delete("1.0", tk.END)
        result_box.insert(tk.END, recommendation)
        result_box.config(state="disabled")

    except Exception as e:
        messagebox.showerror("Hata", str(e))
        sat_label.config(text="Bir hata oluştu. Uydu görüntüsü yüklenemedi.")

# ==========================
# 6) Arayüz
# ==========================
root = tk.Tk()
root.title("AgroLLM – Tarımsal Karar Destek Sistemi")
root.geometry("1200x900")
root.config(bg="#f2f8f1")

title_label = tk.Label(root, text="AgroLLM", font=("Segoe UI", 22, "bold"),
                       bg="#f2f8f1", fg="#2e7d32")
title_label.pack(pady=(10, 5))
subtitle_label = tk.Label(root, text="Tarımsal Karar Destek Sistemi",
                          font=("Segoe UI", 12), bg="#f2f8f1", fg="#388e3c")
subtitle_label.pack(pady=(0, 10))

# Üst çubuk
frame_top = tk.Frame(root, bg="#f2f8f1")
frame_top.pack(pady=5, padx=20, fill="x")

tk.Label(frame_top, text="📍 Şehir / İlçe:", bg="#f2f8f1",
         font=("Segoe UI", 12)).pack(side="left", padx=(0, 5))
city_entry = tk.Entry(frame_top, width=32, font=("Segoe UI", 11))
city_entry.pack(side="left", padx=5)
city_entry.insert(0, "Şanlıurfa,TR")

tk.Label(frame_top, text="🌱 Ürün:", bg="#f2f8f1",
         font=("Segoe UI", 12)).pack(side="left", padx=(20, 5))
product_combo = ttk.Combobox(frame_top, values=PRODUCTS, width=22,
                             font=("Segoe UI", 11), state="readonly")
product_combo.pack(side="left", padx=5)
product_combo.set(PRODUCTS[0])

button_frame = tk.Frame(frame_top, bg="#f2f8f1")
button_frame.pack(side="left", padx=20)
tk.Button(button_frame, text="Ürün Analizi", command=analiz_et, bg="#388e3c",
          fg="white", font=("Segoe UI", 11, "bold"),
          relief="flat", activebackground="#2e7d32").pack(side="left", padx=6)
tk.Button(button_frame, text="Genel Tarımsal Öneri", command=genel_analiz,
          bg="#1976d2", fg="white", font=("Segoe UI", 11, "bold"),
          relief="flat", activebackground="#1565c0").pack(side="left", padx=6)

# --- PanedWindow ile esnek yerleşim (HARİTA + SONUÇ) ---
pw = ttk.Panedwindow(root, orient="vertical")
pw.pack(padx=12, pady=8, fill="both", expand=True)

# Üst panel: Harita (uydu görüntüsü)
map_frame = tk.Frame(pw, bg="#e9efe6", height=420)
map_frame.pack_propagate(False)
sat_label = tk.Label(
    map_frame,
    text="Uydu görüntüsü burada görünecek",
    bg="#e9efe6",
    relief="groove",
    font=("Segoe UI", 10)
)
sat_label.pack(fill="both", expand=True)

# Alt panel: LLM sonuç alanı (büyük + scrollbar)
result_frame = tk.Frame(pw, bg="#f2f8f1", height=420)
result_frame.pack_propagate(False)
scrollbar = tk.Scrollbar(result_frame)
scrollbar.pack(side="right", fill="y")

result_box = tk.Text(
    result_frame,
    font=("Segoe UI", 12),   # büyütmek istersen 13-14 yap
    wrap="word",
    state="disabled",
    relief="solid",
    borderwidth=1,
    padx=12,
    pady=12,
    yscrollcommand=scrollbar.set
)
result_box.pack(side="left", fill="both", expand=True)
scrollbar.config(command=result_box.yview)

# Panellere ekle ve başlangıç ağırlıkları (harita:1, sonuç:2)
pw.add(map_frame, weight=1)
pw.add(result_frame, weight=2)

root.mainloop()
