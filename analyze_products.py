"""
AgroLLM - Tarım Ürünü Analizi (Excel Verisinden)
Bu kod, 2024 VERILERI.xlsx dosyasındaki tarım ürünlerini okur ve temel özet çıkarır.
"""

import pandas as pd

# Excel dosyasını oku
file_path = "2024 VERILERI.xlsx"
try:
    df = pd.read_excel(file_path)
except Exception as e:
    raise FileNotFoundError(f"❌ Dosya okunamadı: {e}")

# Veri hakkında bilgi
print("✅ Veri başarıyla yüklendi.")
print(f"Toplam satır: {len(df)}, Sütunlar: {list(df.columns)}\n")

# İlk birkaç satırı göster
print(df.head())

# Eğer sütun adlarında sorun varsa kullanıcıya bildir
if all("Unnamed" in str(c) for c in df.columns):
    print("⚠️ Görünüşe göre Excel'de sütun başlıkları eksik. İlk satır başlık olabilir.")
    print("Excel'i açıp ilk satırda hangi sütunlar olduğunu kontrol et.")
