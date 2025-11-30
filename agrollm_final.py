"""
AgroLLM – Tarla Odaklı Uydu + NDVI + LLM Öneri
- Doğal Renk: Esri World_Imagery (en gerçekçi görüntü için)
- Yedek Doğal Renk: Sentinel-2 True Color (B04,B03,B02)
- NDVI: Sentinel-2 L2A (Sentinel Hub üzerinden)
"""

import math
import datetime
from io import BytesIO

import tkinter as tk
from tkinter import ttk, messagebox

import numpy as np
from PIL import Image, ImageTk, ImageDraw
from openai import OpenAI
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

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
# 1️⃣ API Anahtarları
# ==========================

# 👉 BURAYA kendi anahtarlarını yaz
OPENAI_KEY = "OpenAI API giriniz.."
OPENWEATHER_KEY = "OpenWeather API giriniz.."

SH_CLIENT_ID = "Sentinel Hub ID giriniz.."
SH_CLIENT_SECRET = "Sentinel Hub Secret Key giriniz.."

ESRI_WORLD_IMAGERY_EXPORT = (
    "https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/export"
)

client = OpenAI(api_key=OPENAI_KEY)

sh_config = SHConfig()
sh_config.sh_client_id = SH_CLIENT_ID
sh_config.sh_client_secret = SH_CLIENT_SECRET
try:
    sh_config.save()
except Exception:
    pass

# ==========================
# 2️⃣ Ürün listesi
# ==========================

PRODUCTS = [
    "Arpa",
    "Buğday",
    "Mercimek",
    "Mısır",
    "Pamuk",
    "Biber",
    "Domates",
    "Patlıcan",
    "Antep Fıstığı",
    "Zeytin",
    "Badem",
]

# ==========================
# 3️⃣ Tema / renkler
# ==========================

BG_MAIN = "#e5f3ec"        # ana arka plan
CARD_BG = "#ffffff"        # kart arka planı
ACCENT = "#16a34a"         # butonlar / vurgu
ACCENT_DARK = "#15803d"
TEXT_PRIMARY = "#0f172a"
TEXT_MUTED = "#6b7280"
BORDER = "#d1d5db"

# ==========================
# 4️⃣ HTTP session helper
# ==========================

def make_session() -> requests.Session:
    s = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=1.5,
        # 500'leri kendimiz handle edeceğiz
        status_forcelist=[429, 502, 503, 504],
        allowed_methods=["GET", "POST"],
    )
    s.mount("https://", HTTPAdapter(max_retries=retries))
    s.mount("http://", HTTPAdapter(max_retries=retries))
    return s


http = make_session()

# ==========================
# 5️⃣ Geometri yardımcıları
# ==========================

def bbox_from_center(lat: float, lon: float, size_m: float):
    """
    Enlem, boylam ve metre cinsinden kenar uzunluğuna göre kare bbox hesaplar.
    Dönen: (min_lon, min_lat, max_lon, max_lat)
    """
    if not size_m or size_m <= 0:
        size_m = 200.0
    half_km = (size_m / 1000.0) / 2.0

    lat_rad = math.radians(lat)
    deg_lat_dist = 111.32  # km
    deg_lon_dist = max(1e-6, 111.32 * math.cos(lat_rad))

    dlat = half_km / deg_lat_dist
    dlon = half_km / deg_lon_dist

    min_lat = lat - dlat
    max_lat = lat + dlat
    min_lon = lon - dlon
    max_lon = lon + dlon

    return (min_lon, min_lat, max_lon, max_lat)


def resolve_geometry_from_ui():
    lat_str = lat_entry.get().strip().replace(",", ".")
    lon_str = lon_entry.get().strip().replace(",", ".")
    area_str = area_entry.get().strip().replace(",", ".")

    if not lat_str or not lon_str:
        raise ValueError("Enlem ve boylam girmelisin.")

    lat = float(lat_str)
    lon = float(lon_str)
    size_m = float(area_str) if area_str else 200.0

    bbox_coords = bbox_from_center(lat, lon, size_m)
    return bbox_coords, lat, lon


def get_dates_from_ui():
    start_str = start_entry.get().strip()
    end_str = end_entry.get().strip()
    today = datetime.date.today()

    if not end_str:
        end_str = today.isoformat()
    if not start_str:
        start_str = (today - datetime.timedelta(days=30)).isoformat()

    return start_str, end_str

# ==========================
# 6️⃣ Hava durumu (OpenWeather)
# ==========================

def get_weather(city: str) -> dict:
    if not city:
        raise ValueError("Şehir/ilçe bilgisi boş.")

    url = (
        f"https://api.openweathermap.org/data/2.5/weather"
        f"?q={city}&appid={OPENWEATHER_KEY}&units=metric&lang=tr"
    )
    res = http.get(url, timeout=20)
    res.raise_for_status()
    data = res.json()

    return {
        "şehir": city,
        "hava_durumu": data["weather"][0]["description"],
        "sıcaklık": data["main"]["temp"],
        "nem": data["main"]["humidity"],
    }

# ==========================
# 7️⃣ Esri World_Imagery – Doğal Renk
# ==========================

def fetch_esri_truecolor(bbox_coords, width: int = 700, height: int = 500) -> Image.Image:
    """
    Esri World_Imagery’den doğal renk uydu görüntüsü çeker.
    bbox_coords: (min_lon, min_lat, max_lon, max_lat) WGS84
    """
    min_lon, min_lat, max_lon, max_lat = bbox_coords
    bbox_str = f"{min_lon},{min_lat},{max_lon},{max_lat}"

    params = {
        "bbox": bbox_str,
        "bboxSR": 4326,
        "imageSR": 4326,
        "size": f"{width},{height}",
        "format": "png32",
        "f": "image",
    }

    try:
        r = http.get(ESRI_WORLD_IMAGERY_EXPORT, params=params, timeout=25)
    except Exception as e:
        raise RuntimeError(f"Esri isteği gönderilemedi: {e}")

    if r.status_code >= 400:
        debug_params = params.copy()
        debug_params["f"] = "json"
        try:
            debug_resp = requests.get(
                ESRI_WORLD_IMAGERY_EXPORT,
                params=debug_params,
                timeout=25,
            )
            debug_text = debug_resp.text[:500]
        except Exception as e:
            debug_text = f"JSON hata detayı alınamadı: {e}"

        raise RuntimeError(f"Esri HTTP {r.status_code} hatası. Detay: {debug_text}")

    img = Image.open(BytesIO(r.content)).convert("RGB")
    return img

# ==========================
# 8️⃣ Sentinel-2 NDVI
# ==========================

def sentinel_ndvi_array(bbox_coords, start_date: str, end_date: str) -> np.ndarray:
    if not sh_config.sh_client_id or not sh_config.sh_client_secret:
        raise RuntimeError("Sentinel Hub kimlik bilgileri tanımlı değil.")

    bbox = BBox(bbox_coords, crs=CRS.WGS84)
    size = bbox_to_dimensions(bbox, resolution=10)

    evalscript_ndvi = """
        //VERSION=3
        function setup() {
            return {
                input: [{
                    bands: ["B08", "B04"],
                    units: "REFLECTANCE"
                }],
                output: {
                    bands: 1,
                    sampleType: "FLOAT32"
                }
            };
        }

        function evaluatePixel(sample) {
            var denom = sample.B08 + sample.B04;
            var ndvi = 0.0;
            if (denom > 0.0) {
                ndvi = (sample.B08 - sample.B04) / denom;
            }
            return [ndvi];
        }
    """

    request = SentinelHubRequest(
        evalscript=evalscript_ndvi,
        input_data=[
            SentinelHubRequest.input_data(
                data_collection=DataCollection.SENTINEL2_L2A,
                time_interval=(start_date, end_date),
                mosaicking_order=MosaickingOrder.LEAST_CC,
            )
        ],
        responses=[SentinelHubRequest.output_response("default", MimeType.TIFF)],
        bbox=bbox,
        size=size,
        config=sh_config,
    )

    data_list = request.get_data()
    if not data_list:
        raise RuntimeError("Sentinel Hub NDVI verisi döndürmedi.")
    ndvi = data_list[0].squeeze()
    return ndvi


def ndvi_to_image_and_mean(ndvi: np.ndarray) -> tuple[Image.Image, float]:
    ndvi = np.clip(ndvi, -1.0, 1.0)
    mean_val = float(np.nanmean(ndvi))

    norm = (ndvi + 1.0) / 2.0
    h, w = norm.shape
    rgb = np.zeros((h, w, 3), dtype=np.uint8)

    rgb[..., 1] = (norm * 255).astype(np.uint8)          # yeşil
    rgb[..., 0] = ((1.0 - norm) * 180).astype(np.uint8)  # kahverengi ton
    rgb[..., 2] = 0

    img = Image.fromarray(rgb, mode="RGB")
    return img, mean_val

# ==========================
# 9️⃣ Sentinel-2 True Color (Esri bozulursa yedek)
# ==========================

def sentinel_truecolor_image(bbox_coords, start_date: str, end_date: str) -> Image.Image:
    if not sh_config.sh_client_id or not sh_config.sh_client_secret:
        raise RuntimeError("Sentinel Hub kimlik bilgileri tanımlı değil.")

    bbox = BBox(bbox_coords, crs=CRS.WGS84)
    size = bbox_to_dimensions(bbox, resolution=10)

    evalscript_true = """
        //VERSION=3
        function setup() {
            return {
                input: [{
                    bands: ["B04", "B03", "B02"],
                    units: "REFLECTANCE"
                }],
                output: {
                    bands: 3,
                    sampleType: "FLOAT32"
                }
            };
        }

        function evaluatePixel(sample) {
            return [sample.B04, sample.B03, sample.B02];
        }
    """

    request = SentinelHubRequest(
        evalscript=evalscript_true,
        input_data=[
            SentinelHubRequest.input_data(
                data_collection=DataCollection.SENTINEL2_L2A,
                time_interval=(start_date, end_date),
                mosaicking_order=MosaickingOrder.LEAST_CC,
            )
        ],
        responses=[SentinelHubRequest.output_response("default", MimeType.TIFF)],
        bbox=bbox,
        size=size,
        config=sh_config,
    )

    data_list = request.get_data()
    if not data_list:
        raise RuntimeError("Sentinel Hub true color verisi döndürmedi.")

    rgb = data_list[0]             # (H, W, 3) float32 0-1
    rgb = np.clip(rgb, 0, 1)
    rgb_uint8 = (rgb * 255).astype(np.uint8)
    img = Image.fromarray(rgb_uint8, mode="RGB")
    return img

# ==========================
# 🔟 UI yardımcıları
# ==========================

def make_placeholder_image(message: str) -> Image.Image:
    img = Image.new("RGB", (700, 500), (233, 239, 230))
    draw = ImageDraw.Draw(img)
    draw.text((20, 230), message, fill=(0, 0, 0))
    return img


def show_satellite_in_label(img: Image.Image):
    img = img.copy()
    img.thumbnail((700, 500))
    photo = ImageTk.PhotoImage(img)
    sat_label.config(image=photo)
    sat_label.image = photo  # referans sakla

# ==========================
# 1️⃣1️⃣ LLM çağrısı
# ==========================

def call_llm(prompt: str) -> str:
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "Sen Türkiye'deki iklim ve tarım bölgelerini iyi bilen deneyimli bir tarım danışmanısın.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.6,
    )
    return resp.choices[0].message.content.strip()

# ==========================
# 1️⃣2️⃣ Ürün bazlı analiz
# ==========================

def analiz_et():
    city = city_entry.get().strip()
    product = product_combo.get().strip()
    if not product:
        messagebox.showwarning("Uyarı", "Lütfen bir ürün seçin!")
        return

    try:
        bbox_coords, center_lat, center_lon = resolve_geometry_from_ui()
    except Exception as e:
        messagebox.showerror("Geometri Hatası", str(e))
        return

    try:
        weather = (
            get_weather(city)
            if city
            else {"hava_durumu": "bilinmiyor", "sıcaklık": "-", "nem": "-"}
        )
    except Exception as e:
        messagebox.showwarning("Hava Durumu", f"Hava verisi alınamadı: {e}")
        weather = {"hava_durumu": "bilinmiyor", "sıcaklık": "-", "nem": "-"}

    start_str, end_str = get_dates_from_ui()
    mode = mode_var.get()

    ndvi_avg_value = None

    # Uydu görüntüsü
    try:
        if mode == "ndvi":
            ndvi_arr = sentinel_ndvi_array(bbox_coords, start_str, end_str)
            ndvi_img, ndvi_avg_value = ndvi_to_image_and_mean(ndvi_arr)
            show_satellite_in_label(ndvi_img)
        else:
            try:
                rgb_img = fetch_esri_truecolor(bbox_coords)
            except Exception as e_esri:
                messagebox.showwarning(
                    "Esri Hatası",
                    f"Esri görüntüsü alınamadı, Sentinel true-color'a geçiliyor:\n{e_esri}"
                )
                try:
                    rgb_img = sentinel_truecolor_image(bbox_coords, start_str, end_str)
                except Exception as e_s2:
                    messagebox.showwarning(
                        "Sentinel True Color",
                        f"Sentinel true-color da alınamadı, boş görüntü gösterilecek:\n{e_s2}"
                    )
                    rgb_img = make_placeholder_image("Uydu görüntüsü alınamadı.")

            show_satellite_in_label(rgb_img)

            # NDVI ortalamasını hesaplamaya çalış
            try:
                ndvi_arr = sentinel_ndvi_array(bbox_coords, start_str, end_str)
                _, ndvi_avg_value = ndvi_to_image_and_mean(ndvi_arr)
            except Exception:
                ndvi_avg_value = None

    except Exception as e:
        messagebox.showwarning("Uydu Görüntüsü", f"Uydu verisi alınamadı: {e}")
        placeholder = make_placeholder_image("Uydu görüntüsü alınamadı.")
        show_satellite_in_label(placeholder)

    ndvi_avg = f"{ndvi_avg_value:.2f}" if ndvi_avg_value is not None else "bilinmiyor"

    # 🔸 ÜRÜN ANALİZİ PROMPTU – senin sade eski hâli
    prompt = f"""
Ürün: {product}
Şehir/İlçe: {city}
Hava durumu: {weather['hava_durumu']}
Sıcaklık: {weather['sıcaklık']} °C
Nem: %{weather['nem']}
NDVI ortalama: {ndvi_avg}

Bu verilere göre, {product} için öncelikle bu bölgede yetişmiyorsa olumsuz cevap ver.
Eğer bu bölgede yetiştiriliyorsa, çiftçi diliyle yazılmış teknik, detaylı bir tarımsal öneri üret.
"""

    try:
        recommendation = call_llm(prompt)
    except Exception as e:
        messagebox.showerror("LLM Hatası", f"Öneri üretilemedi: {e}")
        return

    result_box.config(state="normal")
    result_box.delete(1.0, tk.END)
    result_box.insert(tk.END, recommendation)
    result_box.config(state="disabled")

# ==========================
# 1️⃣3️⃣ Genel tarımsal analiz
# ==========================

def genel_analiz():
    city = city_entry.get().strip()
    if not city:
        messagebox.showwarning(
            "Uyarı",
            "Genel tarımsal öneri için en azından şehir/ilçe girmen iyi olur.",
        )

    try:
        bbox_coords, center_lat, center_lon = resolve_geometry_from_ui()
    except Exception as e:
        messagebox.showerror("Geometri Hatası", str(e))
        return

    try:
        weather = (
            get_weather(city)
            if city
            else {"hava_durumu": "bilinmiyor", "sıcaklık": "-", "nem": "-"}
        )
    except Exception as e:
        messagebox.showwarning("Hava Durumu", f"Hava verisi alınamadı: {e}")
        weather = {"hava_durumu": "bilinmiyor", "sıcaklık": "-", "nem": "-"}

    start_str, end_str = get_dates_from_ui()
    mode = mode_var.get()
    ndvi_avg_value = None

    try:
        if mode == "ndvi":
            ndvi_arr = sentinel_ndvi_array(bbox_coords, start_str, end_str)
            ndvi_img, ndvi_avg_value = ndvi_to_image_and_mean(ndvi_arr)
            show_satellite_in_label(ndvi_img)
        else:
            try:
                rgb_img = fetch_esri_truecolor(bbox_coords)
            except Exception as e_esri:
                messagebox.showwarning(
                    "Esri Hatası",
                    f"Esri görüntüsü alınamadı, Sentinel true-color'a geçiliyor:\n{e_esri}"
                )
                try:
                    rgb_img = sentinel_truecolor_image(bbox_coords, start_str, end_str)
                except Exception as e_s2:
                    messagebox.showwarning(
                        "Sentinel True Color",
                        f"Sentinel true-color da alınamadı, boş görüntü gösterilecek:\n{e_s2}"
                    )
                    rgb_img = make_placeholder_image("Uydu görüntüsü alınamadı.")

            show_satellite_in_label(rgb_img)

            try:
                ndvi_arr = sentinel_ndvi_array(bbox_coords, start_str, end_str)
                _, ndvi_avg_value = ndvi_to_image_and_mean(ndvi_arr)
            except Exception:
                ndvi_avg_value = None

    except Exception as e:
        messagebox.showwarning("Uydu Görüntüsü", f"Uydu verisi alınamadı: {e}")
        placeholder = make_placeholder_image("Uydu görüntüsü alınamadı.")
        show_satellite_in_label(placeholder)

    ndvi_avg = f"{ndvi_avg_value:.2f}" if ndvi_avg_value is not None else "bilinmiyor"

    # 🔸 GENEL ANALİZ PROMPTU – eski basit hâli
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

    try:
        recommendation = call_llm(prompt)
    except Exception as e:
        messagebox.showerror("LLM Hatası", f"Öneri üretilemedi: {e}")
        return

    result_box.config(state="normal")
    result_box.delete(1.0, tk.END)
    result_box.insert(tk.END, recommendation)
    result_box.config(state="disabled")

# ==========================
# 1️⃣4️⃣ Arayüz (modern, ikiye bölünmüş)
# ==========================

root = tk.Tk()
root.title("AgroLLM – Uydu + NDVI + Tarımsal Analiz")
root.geometry("1400x820")
root.config(bg=BG_MAIN)

# Başlık
header_frame = tk.Frame(root, bg=BG_MAIN)
header_frame.pack(fill="x", padx=20, pady=(15, 5))

title_label = tk.Label(
    header_frame,
    text="🌾 AgroLLM",
    font=("Segoe UI", 24, "bold"),
    bg=BG_MAIN,
    fg=ACCENT_DARK,
)
title_label.pack(anchor="w")

subtitle_label = tk.Label(
    header_frame,
    text="Enlem/Boylam + Uydu Görüntüsü + LLM ile Tarımsal Karar Desteği",
    font=("Segoe UI", 11),
    bg=BG_MAIN,
    fg=TEXT_MUTED,
)
subtitle_label.pack(anchor="w")

# Üst kontrol kartı
control_card = tk.Frame(root, bg=CARD_BG, bd=0, highlightthickness=1, highlightbackground=BORDER)
control_card.pack(fill="x", padx=20, pady=(0, 10))

# Satır 0: şehir, enlem, boylam, alan
tk.Label(control_card, text="📍 Şehir/İlçe:", bg=CARD_BG, fg=TEXT_PRIMARY, font=("Segoe UI", 10, "bold")).grid(row=0, column=0, padx=8, pady=6, sticky="e")
city_entry = tk.Entry(control_card, width=22, font=("Segoe UI", 10), bg="#f9fafb", fg=TEXT_PRIMARY, relief="flat")
city_entry.grid(row=0, column=1, padx=4, pady=6, sticky="w")
city_entry.insert(0, "Şanlıurfa,TR")

tk.Label(control_card, text="📌 Enlem:", bg=CARD_BG, fg=TEXT_PRIMARY, font=("Segoe UI", 10, "bold")).grid(row=0, column=2, padx=8, pady=6, sticky="e")
lat_entry = tk.Entry(control_card, width=10, font=("Segoe UI", 10), bg="#f9fafb", fg=TEXT_PRIMARY, relief="flat")
lat_entry.grid(row=0, column=3, padx=4, pady=6, sticky="w")
lat_entry.insert(0, "37.2091")

tk.Label(control_card, text="Boylam:", bg=CARD_BG, fg=TEXT_PRIMARY, font=("Segoe UI", 10, "bold")).grid(row=0, column=4, padx=8, pady=6, sticky="e")
lon_entry = tk.Entry(control_card, width=10, font=("Segoe UI", 10), bg="#f9fafb", fg=TEXT_PRIMARY, relief="flat")
lon_entry.grid(row=0, column=5, padx=4, pady=6, sticky="w")
lon_entry.insert(0, "39.5629")

tk.Label(control_card, text="Alan (m):", bg=CARD_BG, fg=TEXT_PRIMARY, font=("Segoe UI", 10, "bold")).grid(row=0, column=6, padx=8, pady=6, sticky="e")
area_entry = tk.Entry(control_card, width=8, font=("Segoe UI", 10), bg="#f9fafb", fg=TEXT_PRIMARY, relief="flat")
area_entry.grid(row=0, column=7, padx=4, pady=6, sticky="w")
area_entry.insert(0, "500")

# Satır 1: tarih, mod, ürün, butonlar
today = datetime.date.today()
default_start = (today - datetime.timedelta(days=30)).isoformat()
default_end = today.isoformat()

tk.Label(control_card, text="Başlangıç:", bg=CARD_BG, fg=TEXT_PRIMARY, font=("Segoe UI", 10)).grid(row=1, column=0, padx=8, pady=6, sticky="e")
start_entry = tk.Entry(control_card, width=10, font=("Segoe UI", 10), bg="#f9fafb", fg=TEXT_PRIMARY, relief="flat")
start_entry.grid(row=1, column=1, padx=4, pady=6, sticky="w")
start_entry.insert(0, default_start)

tk.Label(control_card, text="Bitiş:", bg=CARD_BG, fg=TEXT_PRIMARY, font=("Segoe UI", 10)).grid(row=1, column=2, padx=8, pady=6, sticky="e")
end_entry = tk.Entry(control_card, width=10, font=("Segoe UI", 10), bg="#f9fafb", fg=TEXT_PRIMARY, relief="flat")
end_entry.grid(row=1, column=3, padx=4, pady=6, sticky="w")
end_entry.insert(0, default_end)

mode_var = tk.StringVar(value="rgb")
mode_frame = tk.Frame(control_card, bg=CARD_BG)
mode_frame.grid(row=1, column=4, columnspan=2, padx=8, pady=6, sticky="w")
tk.Label(mode_frame, text="Görsel:", bg=CARD_BG, fg=TEXT_PRIMARY, font=("Segoe UI", 10, "bold")).pack(side="left", padx=(0, 4))
tk.Radiobutton(mode_frame, text="Doğal Renk", variable=mode_var, value="rgb", bg=CARD_BG, fg=TEXT_PRIMARY, font=("Segoe UI", 9)).pack(side="left")
tk.Radiobutton(mode_frame, text="NDVI", variable=mode_var, value="ndvi", bg=CARD_BG, fg=TEXT_PRIMARY, font=("Segoe UI", 9)).pack(side="left")

tk.Label(control_card, text="Ürün:", bg=CARD_BG, fg=TEXT_PRIMARY, font=("Segoe UI", 10, "bold")).grid(row=1, column=6, padx=8, pady=6, sticky="e")
product_combo = ttk.Combobox(control_card, values=PRODUCTS, width=15, font=("Segoe UI", 10), state="readonly")
product_combo.grid(row=1, column=7, padx=4, pady=6, sticky="w")
product_combo.set(PRODUCTS[0])

button_frame = tk.Frame(control_card, bg=CARD_BG)
button_frame.grid(row=0, column=8, rowspan=2, padx=(20, 10), pady=6, sticky="e")

btn_urun = tk.Button(
    button_frame,
    text="Ürün Analizi",
    command=analiz_et,
    bg=ACCENT,
    fg="white",
    font=("Segoe UI", 10, "bold"),
    relief="flat",
    padx=12,
    pady=6,
    activebackground=ACCENT_DARK,
    activeforeground="white",
    borderwidth=0,
)
btn_urun.pack(side="top", pady=2, fill="x")

btn_genel = tk.Button(
    button_frame,
    text="Genel Öneri",
    command=genel_analiz,
    bg="#2563eb",
    fg="white",
    font=("Segoe UI", 10, "bold"),
    relief="flat",
    padx=12,
    pady=6,
    activebackground="#1d4ed8",
    activeforeground="white",
    borderwidth=0,
)
btn_genel.pack(side="top", pady=2, fill="x")

# Ana içerik: sol uydu, sağ LLM
content_frame = tk.Frame(root, bg=BG_MAIN)
content_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))

content_frame.rowconfigure(0, weight=1)
content_frame.columnconfigure(0, weight=1)
content_frame.columnconfigure(1, weight=1)

# Sol kart: uydu
left_card = tk.Frame(content_frame, bg=CARD_BG, bd=0, highlightthickness=1, highlightbackground=BORDER)
left_card.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

left_card.rowconfigure(1, weight=1)
left_card.columnconfigure(0, weight=1)

left_title = tk.Label(
    left_card,
    text="🛰️ Uydu Görüntüsü",
    bg=CARD_BG,
    fg=TEXT_PRIMARY,
    font=("Segoe UI", 11, "bold"),
)
left_title.grid(row=0, column=0, sticky="w", padx=10, pady=(8, 4))

sat_label = tk.Label(
    left_card,
    text="Tarla konumunu girip analiz başlatın.",
    bg="#e5e7eb",
    fg=TEXT_MUTED,
    relief="flat",
    font=("Segoe UI", 10),
)
sat_label.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")

# Sağ kart: LLM sonucu
right_card = tk.Frame(content_frame, bg=CARD_BG, bd=0, highlightthickness=1, highlightbackground=BORDER)
right_card.grid(row=0, column=1, sticky="nsew", padx=(10, 0))

right_card.rowconfigure(1, weight=1)
right_card.columnconfigure(0, weight=1)

right_title = tk.Label(
    right_card,
    text="🤖 Tarımsal Analiz ve Öneriler",
    bg=CARD_BG,
    fg=TEXT_PRIMARY,
    font=("Segoe UI", 11, "bold"),
)
right_title.grid(row=0, column=0, sticky="w", padx=10, pady=(8, 4))

result_container = tk.Frame(right_card, bg=CARD_BG)
result_container.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
result_container.rowconfigure(0, weight=1)
result_container.columnconfigure(0, weight=1)

scrollbar = tk.Scrollbar(result_container)
scrollbar.grid(row=0, column=1, sticky="ns")

result_box = tk.Text(
    result_container,
    font=("Segoe UI", 10),
    wrap="word",
    state="normal",
    relief="flat",
    bg="#f9fafb",
    fg=TEXT_PRIMARY,
    padx=8,
    pady=8,
    yscrollcommand=scrollbar.set,
)
result_box.grid(row=0, column=0, sticky="nsew")
scrollbar.config(command=result_box.yview)

result_box.insert(tk.END, "Burada LLM tabanlı tarımsal analiz ve öneriler görünecek.")
result_box.config(state="disabled")

root.mainloop()
