# -*- coding: utf-8 -*-
"""
AMBIL DATA KECEPATAN ANGIN TERKINI DARI AWS CENTER BMKG
=============================================================
Mengambil snapshot kondisi terkini dari AWS Ketapang dan
Gilimanuk, mengambil kecepatan angin MAKSIMUM (field "ws_max" --
sudah merepresentasikan kecepatan maks. pada periode observasi
AWS, berpasangan dengan "ws_avg"), lalu mencari nilai MAKSIMUM
di antara kedua stasiun dan menyimpannya ke file JSON supaya
bisa dibaca dashboard.

Contoh struktur JSON asli per stasiun (dict tunggal, bukan list):
    {
      "nama_stasiun": "AWS Maritim Ketapang",
      "tanggal": "31 Agustus 2026 01:26:00+00",  <- UTC, bulan Bahasa Indonesia
      "ws_avg": "4.1",
      "ws_max": "5.1",
      "wd_avg": "146",
      ...
    }

Memakai cookie session yang disimpan oleh
login_aws_dan_simpan_cookie.py (login manual sekali, dipakai
berulang sampai sesi kadaluarsa).

CATATAN ASUMSI: "ws_max" diasumsikan sudah berupa kecepatan
maksimum pada periode observasi AWS terkini (umumnya 10 menit,
sesuai standar WMO AWS yang melaporkan avg & max berpasangan).
Kalau ternyata di lapangan "ws_max" berarti hal lain (misal
maksimum sejak tengah malam), beri tahu saya supaya logikanya
disesuaikan.
"""

import os
import json
from datetime import datetime, timezone

import requests

# =============================================================
# KONFIGURASI
# =============================================================

# HARUS SAMA dengan LOCAL_DIR di script lain
LOCAL_DIR = "./Satelit"

COOKIE_FILE = os.path.join(LOCAL_DIR, "aws_center_cookies.json")
OUTPUT_JSON = os.path.join(LOCAL_DIR, "angin_aws_terkini.json")

# URL Stasiun disembunyikan menggunakan variabel lingkungan
STASIUN = {
    "Gilimanuk": os.environ.get("AWS_GILIMANUK_URL", ""),
    "Ketapang": os.environ.get("AWS_KETAPANG_URL", ""),
}

TIMEOUT_DETIK = 20

# Satuan asli data "ws_max" dari AWS Center: "ms" (meter/detik,
# standar BMKG) atau "kt" (kalau ternyata sudah dalam knot).
SATUAN_ASLI = "ms"

# Kalau data "tanggal" dari AWS lebih basi dari ini (menit),
# dianggap tidak valid dipakai (stasiun mungkin sedang offline).
BATAS_BASI_DATA_MENIT = 30

# Set True untuk mencetak isi JSON mentah ke terminal (debug).
MODE_DEBUG = False

BULAN_INDONESIA = {
    "januari": 1, "februari": 2, "maret": 3, "april": 4,
    "mei": 5, "juni": 6, "juli": 7, "agustus": 8,
    "september": 9, "oktober": 10, "november": 11, "desember": 12,
}


# =============================================================
# FUNGSI BANTUAN
# =============================================================

def muat_cookies():
    if not os.path.exists(COOKIE_FILE):
        raise FileNotFoundError(
            f"File cookie tidak ditemukan: {COOKIE_FILE}. "
            "Jalankan login_aws_dan_simpan_cookie.py dulu."
        )
    with open(COOKIE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def buat_session_dengan_cookie():
    cookies = muat_cookies()
    session = requests.Session()
    for c in cookies:
        session.cookies.set(
            c.get("name"), c.get("value"),
            domain=c.get("domain"), path=c.get("path", "/"),
        )
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    })
    return session


def ambil_json_stasiun(session, url):
    if not url:
        raise ValueError("URL stasiun kosong atau tidak ditemukan di environment variables.")
    
    resp = session.get(url, timeout=TIMEOUT_DETIK)
    resp.raise_for_status()

    try:
        return resp.json()
    except ValueError:
        raise RuntimeError(
            "Respons bukan JSON -- sesi login kemungkinan sudah "
            "kadaluarsa. Jalankan ulang login_aws_dan_simpan_cookie.py."
        )


def ms_ke_knot(nilai_ms):
    return nilai_ms * 1.94384


def parse_tanggal_aws(teks_tanggal):
    """
    Parse format '31 Agustus 2026 01:26:00+00' (bulan Bahasa
    Indonesia, offset UTC di akhir) -> datetime naive dalam UTC.
    Mengembalikan None kalau gagal parse.
    """
    try:
        bagian = teks_tanggal.strip().split()
        hari = int(bagian[0])
        bulan = BULAN_INDONESIA[bagian[1].lower()]
        tahun = int(bagian[2])
        waktu_bersih = bagian[3][:8]  # ambil "HH:MM:SS", buang offset +00
        jam, menit, detik = (int(x) for x in waktu_bersih.split(":"))
        return datetime(tahun, bulan, hari, jam, menit, detik)
    except Exception:
        return None


def ekstrak_kecepatan_maks(data_json, nama_stasiun):
    """
    data_json adalah SATU dict (snapshot kondisi terkini stasiun).
    Mengambil field "ws_max" + validasi kesegaran data via "tanggal".
    Mengembalikan (nilai_ws_max_asli, waktu_data_utc) atau (None, None).
    """
    if not isinstance(data_json, dict):
        print(f"[{nama_stasiun}] Struktur JSON tidak sesuai ekspektasi (bukan dict).")
        return None, None

    ws_max = data_json.get("ws_max")
    tanggal_str = data_json.get("tanggal")

    if ws_max is None:
        print(f"[{nama_stasiun}] Field 'ws_max' tidak ditemukan di respons.")
        return None, None

    if tanggal_str is None:
        print(f"[{nama_stasiun}] Field 'tanggal' tidak ditemukan, tidak bisa cek kesegaran data.")
        return None, None

    waktu_data_utc = parse_tanggal_aws(tanggal_str)
    if waktu_data_utc is None:
        print(f"[{nama_stasiun}] Gagal parse tanggal: '{tanggal_str}'")
        return None, None

    sekarang_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    selisih_menit = (sekarang_utc - waktu_data_utc).total_seconds() / 60
    if selisih_menit > BATAS_BASI_DATA_MENIT:
        print(f"[{nama_stasiun}] Data basi ({selisih_menit:.0f} menit yang lalu, tanggal: {tanggal_str}).")
        return None, None

    try:
        nilai = float(ws_max)
    except (TypeError, ValueError):
        print(f"[{nama_stasiun}] Nilai 'ws_max' tidak valid: {ws_max!r}")
        return None, None

    return nilai, waktu_data_utc


# =============================================================
# PROSES UTAMA
# =============================================================

def ambil_data_angin_terkini():
    os.makedirs(LOCAL_DIR, exist_ok=True)

    try:
        session = buat_session_dengan_cookie()
    except FileNotFoundError as e:
        print(f"[GAGAL] {e}")
        hasil = {
            "waktu_ambil": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "kecepatan_maks_knot": None,
            "stasiun_maks": None,
            "detail_per_stasiun": {},
            "error": [str(e)],
        }
        with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
            json.dump(hasil, f, indent=2, ensure_ascii=False)
        return hasil

    hasil_per_stasiun = {}
    error_list = []

    for nama_stasiun, url in STASIUN.items():
        try:
            data_json = ambil_json_stasiun(session, url)

            if MODE_DEBUG:
                debug_path = os.path.join(LOCAL_DIR, f"debug_aws_{nama_stasiun}.json")
                with open(debug_path, "w", encoding="utf-8") as f:
                    json.dump(data_json, f, indent=2, default=str, ensure_ascii=False)
                print(f"[DEBUG] Struktur JSON {nama_stasiun} disimpan ke: {debug_path}")

            nilai_maks, waktu_data = ekstrak_kecepatan_maks(data_json, nama_stasiun)

            hasil_per_stasiun[nama_stasiun] = {
                "kecepatan_maks_asli": nilai_maks,
                "satuan_asli": SATUAN_ASLI,
                "waktu_data_utc": waktu_data.strftime("%Y-%m-%d %H:%M:%S") if waktu_data else None,
                "nama_lengkap": data_json.get("nama_stasiun") if isinstance(data_json, dict) else None,
            }

        except Exception as e:
            print(f"[GAGAL] Ambil data {nama_stasiun}: {e}")
            error_list.append(f"{nama_stasiun}: {e}")
            hasil_per_stasiun[nama_stasiun] = {
                "kecepatan_maks_asli": None, "satuan_asli": SATUAN_ASLI,
                "waktu_data_utc": None, "nama_lengkap": None,
            }

    # Cari nilai MAKSIMUM di antara kedua stasiun
    kandidat_valid = [
        (nama, info["kecepatan_maks_asli"])
        for nama, info in hasil_per_stasiun.items()
        if info["kecepatan_maks_asli"] is not None
    ]

    if kandidat_valid:
        stasiun_maks, nilai_maks_asli = max(kandidat_valid, key=lambda x: x[1])
        if SATUAN_ASLI == "ms":
            nilai_maks_knot = round(ms_ke_knot(nilai_maks_asli), 1)
        else:
            nilai_maks_knot = round(nilai_maks_asli, 1)
    else:
        stasiun_maks = None
        nilai_maks_knot = None

    hasil = {
        "waktu_ambil": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "kecepatan_maks_knot": nilai_maks_knot,
        "stasiun_maks": stasiun_maks,
        "detail_per_stasiun": hasil_per_stasiun,
        "error": error_list,
    }

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(hasil, f, indent=2, ensure_ascii=False)

    print("\n=== HASIL ===")
    print(json.dumps(hasil, indent=2, ensure_ascii=False))

    return hasil


if __name__ == "__main__":
    ambil_data_angin_terkini()
