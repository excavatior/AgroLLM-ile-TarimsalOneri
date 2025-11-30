"""
AgroLLM - Ürün Listesi Yükleyici (Düzeltilmiş)
Excel'deki ürün, ekim ve hasat bilgilerini otomatik algılar.
"""

import pandas as pd

def load_products(file_path="2024 VERILERI.xlsx"):
    # İlk satırı başlık olarak al (1 yerine 2 deneyebiliriz)
    df = pd.read_excel(file_path, header=None)

    # Boş satır/sütunları temizle
    df = df.dropna(how="all", axis=0)
    df = df.dropna(how="all", axis=1)

    # Başlık satırını ve veri kısmını tespit et
    df.columns = [f"col_{i}" for i in range(len(df.columns))]

    # Sadece içinde "ekim" veya "hasat" geçen sütunları bul
    ekim_cols = [c for c in df.columns if df[c].astype(str).str.contains("ekim", case=False, na=False).any()]
    hasat_cols = [c for c in df.columns if df[c].astype(str).str.contains("hasat", case=False, na=False).any()]

    # Asıl ürünlerin bulunduğu satırları filtrele
    data = df.tail(5).reset_index(drop=True)

    # 3 ana sütunu çıkar
    if len(data.columns) >= 3:
        subset = data.iloc[:, -3:]  # son 3 sütun
        subset.columns = ["urun", "ekim_tarihi", "hasat_tarihi"]
    else:
        subset = data
        subset.columns = ["urun", "ekim_tarihi", "hasat_tarihi"][:len(data.columns)]

    print("✅ Ürün verileri başarıyla okundu.\n")
    print(subset)
    return subset

if __name__ == "__main__":
    load_products()
