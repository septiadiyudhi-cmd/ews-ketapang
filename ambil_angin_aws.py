# -*- coding: utf-8 -*-
"""
AMBIL DATA KECEPATAN ANGIN TERKINI DARI AWS CENTER BMKG
=============================================================
Mengambil 10 data (10 menit) terakhir dari AWS Ketapang dan
Gilimanuk langsung melalui form POST API Raw Data AWS Center.
"""

import os
import json
from datetime import datetime, timedelta, timezone
import requests
from bs4 import BeautifulSoup

# =============================================================
# KONFIGURASI
# =============================================================
LOCAL_DIR = "./Satelit"
COOKIE_FILE = os.path.join(LOCAL_DIR, "aws_center_cookies.json")
OUTPUT_JSON = os.path.join(LOCAL_DIR, "angin_aws_terkini.json")

# URL disembunyikan dan ditarik dari Secret GitHub
URL_RAW_DATA = os.environ.get("AWS_RAW_DATA_URL", "") 

# ID Stasiun ditampilkan langsung (Hardcoded)
ID_STASIUN = {
    "Ketapang": "STA2092",
    "Gilimanuk": "STA2296"
}

TIMEOUT_DETIK = 20
BATAS_BASI_DATA_MENIT = 30

# =============================================================
# FUNGSI BANTUAN
# =============================================================
def muat_cookies():
    if not os.path.exists(COOKIE_FILE):
        raise FileNotFoundError(f"File cookie tidak ditemukan: {COOKIE_FILE}.")
    with open(COOKIE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def buat_session_dengan_cookie():
    cookies = muat_cookies()
    session = requests.Session()
    for c in cookies:
        session.cookies.set(c.get("name"), c.get("value"), domain=c.get("domain"), path=c.get("path", "/"))
    session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    return session

def ms_ke_knot(nilai_ms):
    return nilai_ms * 1.94384

def ambil_10_data_terakhir(session, nama_stasiun, id_sta):
    # Setup tanggal mulai dari kemarin hingga hari ini (agar aman saat pergantian hari/tengah malam)
    sekarang = datetime.now()
    kemarin = sekarang - timedelta(days=1)
    
    payload = {
        "tipe_alat": "T0002",
        "start": kemarin.strftime("%Y-%m-%d"),
        "end": sekarang.strftime("%Y-%m-%d"),
        "station": id_sta
    }

    resp = session.post(URL_RAW_DATA, data=payload, timeout=TIMEOUT_DETIK)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    baris_tabel = soup.find_all("tr")
    
    data_10_menit = []
    waktu_terkini = None

    # Mengabaikan thead/header, iterasi pencarian dari atas (data terbaru)
    for baris in baris_tabel:
        kolom = baris.find_all("td")
        if len(kolom) > 8:
            tanggal_str = kolom[5].text.strip()
            ws_max_str = kolom[8].text.strip()
            
            try:
                # Format waktu di tabel: 2026-09-11 14:56:00+00
                waktu_utc = datetime.strptime(tanggal_str, "%Y-%m-%d %H:%M:%S+00")
                ws_max = float(ws_max_str)
                
                # Simpan waktu dari baris pertama (paling atas) sebagai penanda kesegaran
                if waktu_terkini is None:
                    waktu_terkini = waktu_utc
                
                data_10_menit.append(ws_max)
                
                # Berhenti jika sudah mengumpulkan 10 baris yang valid (10 menit)
                if len(data_10_menit) == 10:
                    break
            except ValueError:
                continue

    # Cek apakah stasiun sedang offline (data terakhir basi)
    if waktu_terkini:
        sekarang_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        selisih_menit = (sekarang_utc - waktu_terkini).total_seconds() / 60
        if selisih_menit > BATAS_BASI_DATA_MENIT:
            print(f"[{nama_stasiun}] Data basi (Terkahir update {selisih_menit:.0f} menit lalu).")
            return None, None

    if not data_10_menit:
        return None, None
        
    return max(data_10_menit), waktu_terkini

# =============================================================
# PROSES UTAMA
# =============================================================
def ambil_data_angin_terkini():
    os.makedirs(LOCAL_DIR, exist_ok=True)
    waktu_sekarang_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try: 
        session = buat_session_dengan_cookie()
    except FileNotFoundError as e:
        print(f"[GAGAL] {e}")
        return

    hasil_per_stasiun = {}
    error_list = []

    for nama_stasiun, id_sta in ID_STASIUN.items():
        try:
            if "XXXX" in id_sta or "STA_GILIMANUK" in id_sta:
                raise ValueError("ID Stasiun belum disetting di script.")
                
            nilai_maks_10m, waktu_data = ambil_10_data_terakhir(session, nama_stasiun, id_sta)
            
            hasil_per_stasiun[nama_stasiun] = {
                "kecepatan_maks_10m_asli": nilai_maks_10m,
                "satuan_asli": "ms",
                "waktu_data_utc": waktu_data.strftime("%Y-%m-%d %H:%M:%S") if waktu_data else None
            }
        except Exception as e:
            error_list.append(f"{nama_stasiun}: {e}")
            hasil_per_stasiun[nama_stasiun] = {"kecepatan_maks_10m_asli": None}

    # Cari nilai maksimum dari kedua stasiun
    kandidat_valid = [
        (nama, info["kecepatan_maks_10m_asli"]) 
        for nama, info in hasil_per_stasiun.items() 
        if info.get("kecepatan_maks_10m_asli") is not None
    ]
    
    if kandidat_valid:
        st_snapshot, val_snapshot = max(kandidat_valid, key=lambda x: x[1])
        val_snapshot_knot = round(ms_ke_knot(val_snapshot), 1)
    else:
        st_snapshot, val_snapshot_knot = None, None

    # Simpan dengan struktur JSON yang sama persis seperti sebelumnya agar Dashboard tidak error
    snapshot_terkini = {
        "waktu_ambil": waktu_sekarang_str,
        "kecepatan_maks_10menit_knot": val_snapshot_knot,
        "stasiun_maks_10menit": st_snapshot,
        "detail_per_stasiun": hasil_per_stasiun,
        "error": error_list,
    }

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(snapshot_terkini, f, indent=2, ensure_ascii=False)

    print("\n=== HASIL 10 MENIT TERAKHIR ===")
    print(json.dumps(snapshot_terkini, indent=2, ensure_ascii=False))

    return snapshot_terkini

if __name__ == "__main__":
    ambil_data_angin_terkini()
