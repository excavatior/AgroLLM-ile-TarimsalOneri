"""
AgroLLM – Masaüstü Uygulaması (Tkinter)
Tarımsal öneri üretimi (OpenAI + OpenWeather)
"""

import tkinter as tk
from tkinter import messagebox, scrolledtext
import requests
from openai import OpenAI
from datetime import datetime
import pandas as pd

# ==========================
# 1️⃣ API Anahtarları
# ==========================
OPENAI_KEY = "sk-proj-..."      # 👈 kendi OpenAI anahtarını yaz
OPENWEATHER_KEY = "..."         # 👈 kendi OpenWeather anahtarını yaz

client = OpenAI(api_key=OPENAI_KEY)

# ==========================
# 2️⃣ Ana Fonksiyon
# ==========================
def analiz_et():
    city = city_entry.get().strip()
    if not city:
        messagebox.showwarning("Uyarı", "Lütfen şehir girin!")
        return

    try:
        # 1. Hava durumu verisi
        url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={OPENWEATHER_KEY}&units=metric&lang=tr"
        res = requests.get(url)
        if res.status_code != 200:
            messagebox.showerror("Hata", f"API hatası: {res.status_code}")
            return

        data = res.json()
        weather = {
            "şehir": data["name"],
            "sıcaklık_(°C)": data["main"]["temp"],
            "nem_(%)": data["main"]["humidity"],
            "rüzgar_hızı_(m/s)": data["wind"]["speed"],
            "hava_durumu": data["weather"][0]["description"],
            "tarih": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        # 2. NDVI (örnek değer)
        ndvi = 0.52

        # 3. LLM analizi
        prompt = f"""
        Şu anda {weather['şehir']} için hava durumu {weather['hava_durumu']},
        sıcaklık {weather['sıcaklık_(°C)']} °C, nem {weather['nem_(%)']} %,
        NDVI {ndvi}.
        Buna göre:
        - Sulama önerisi yap
        - Bitki sağlığı hakkında kısa yorum yap
        - Sıcaklık/nem uyarısı ver
        """

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Sen bir tarım danışmanısın."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.6
        )

        recommendation = response.choices[0].message.content.strip()

        # 4. Sonucu ekrana yaz
        output_text.config(state="normal")
        output_text.delete(1.0, tk.END)
        output_text.insert(tk.END, f"🌾 TARIMSAL ÖNERİ ({weather['şehir']}) 🌾\n\n{recommendation}")
        output_text.config(state="disabled")

        # 5. Kaydet
        pd.DataFrame([weather]).to_csv("latest_weather.csv", index=False, encoding="utf-8-sig")
        with open("ai_recommendation.txt", "w", encoding="utf-8") as f:
            f.write(recommendation)

        messagebox.showinfo("Başarılı", "✅ Öneri üretildi ve kaydedildi.")

    except Exception as e:
        messagebox.showerror("Hata", str(e))


# ==========================
# 3️⃣ Arayüz (Tkinter)
# ==========================
root = tk.Tk()
root.title("AgroLLM - Tarımsal Öneri Sistemi")
root.geometry("650x450")
root.resizable(False, False)

title_label = tk.Label(root, text="AgroLLM - Tarımsal Öneri", font=("Arial", 16, "bold"), fg="#2E7D32")
title_label.pack(pady=10)

frame = tk.Frame(root)
frame.pack(pady=10)

tk.Label(frame, text="📍 Şehir / İlçe:").grid(row=0, column=0, padx=5)
city_entry = tk.Entry(frame, width=30)
city_entry.grid(row=0, column=1, padx=5)

analyze_button = tk.Button(frame, text="Analiz Et", command=analiz_et, bg="#4CAF50", fg="white", font=("Arial", 11, "bold"))
analyze_button.grid(row=0, column=2, padx=10)

output_text = scrolledtext.ScrolledText(root, width=75, height=15, wrap=tk.WORD, state="disabled", font=("Arial", 10))
output_text.pack(padx=10, pady=15)

root.mainloop()
