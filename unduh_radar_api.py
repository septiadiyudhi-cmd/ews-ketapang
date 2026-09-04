# -*- coding: utf-8 -*-
import os
import json
import time
import requests
from datetime import datetime

LOCAL_DIR = "./Satelit"
COOKIE_FILE = os.path.join(LOCAL_DIR, "sidarma_cookies.json")
RADAR_LIST = ["Denpasar", "Surabaya"]

# Alamat API dan Referer disembunyikan menggunakan variabel lingkungan
API_URL = os.environ.get("RADAR_API_URL")
REFERER_URL = os.environ.get("RADAR_REFERER")

def muat_cookies():
    with open(COOKIE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def buat_session():
    session = requests.Session()
    for c in muat_cookies():
        session.cookies.set(
            c.get("name"), c.get("value"),
            domain=c.get("domain", ""), path=c.get("path", "/")
        )
    
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        # Menggunakan variabel rahasia, atau string kosong jika tidak ada
        "Referer": REFERER_URL or "",
    })
    return session

def unduh_radar():
    print("=== UNDUH GAMBAR RADAR SIDARMA ===")
    session = buat_session()
    waktu_str = datetime.utcnow().strftime("%Y%m%d_%H%M")
    
    for radar in RADAR_LIST:
        print(f"\n[{radar}] Memeriksa API untuk gambar terbaru...")
        params = {"radar": radar, "product": "CMAX", "_": int(time.time() * 1000)}
        
        try:
            # 1. Panggil API untuk mendapatkan JSON
            resp = session.get(API_URL, params=params, timeout=15)
            resp.raise_for_status()
            data_json = resp.json()
            
            # 2. Ekstrak URL gambar dari dalam JSON
            img_url = data_json.get("Latest", {}).get("file")
            if not img_url:
                print(f"[X] Gagal. URL gambar tidak ditemukan di dalam respon JSON.")
                continue
                
            print(f"[{radar}] Link ditemukan: {img_url}")
            print(f"[{radar}] Mengunduh gambar...")
            
            # 3. Unduh gambar asli dari URL yang didapat
            img_resp = session.get(img_url, timeout=30)
            img_resp.raise_for_status()
            
            nama_file = f"RADAR_{radar.upper()}_{waktu_str}.png"
            path_file = os.path.join(LOCAL_DIR, nama_file)
            
            # 4. Simpan ke lokal
            with open(path_file, 'wb') as f:
                f.write(img_resp.content)
                
            print(f"[OK] Berhasil disimpan: {nama_file}")
            
        except Exception as e:
            print(f"[X] Terjadi kesalahan pada {radar}: {e}")

if __name__ == "__main__":
    unduh_radar()
