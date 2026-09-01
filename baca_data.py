# -*- coding: utf-8 -*-
"""
BACA DATA SATELIT & RADAR -> HITUNG STATUS -> LOG CSV & NPZ
=============================================================
Memadukan deteksi Himawari-9 B13 (Suhu <= -34C) dan 
Radar SIDARMA CMAX (Reflektivitas >= 5 dBZ) dengan logika OR.
"""

import sys
import os
import re
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import xarray as xr
from scipy import ndimage

# Import modul radar yang baru kita buat
try:
    import baca_radar
except ImportError:
    baca_radar = None
    print("[WARNING] Modul baca_radar.py tidak ditemukan. Hanya menggunakan satelit.")

# =============================================================
# KONFIGURASI
# =============================================================
LOCAL_DIR = "./Satelit"
CACHE_DIR = os.path.join(LOCAL_DIR, "_cache")

TARGET_LON = 114.43
TARGET_LAT = -8.15

RADIUS_SIAGA_KM = 10
RADIUS_WASPADA_KM = 20

AMBANG_SEL_SIGNIFIKAN_C = -34.0
LUAS_MIN_SEL_KM2 = 10.0
TOLERANSI_LACAK_JAM = 0.5
KECEPATAN_MAKS_KMH = 100.0

LOG_CSV = os.path.join(LOCAL_DIR, "log_status_cb.csv")
MAKS_BARIS_LOG = 288
# Tambahan kolom 'dbz_maks_radar'
KOLOM_LOG = [
    "waktu_utc", "waktu_wib", "file_sumber",
    "suhu_min_10km", "suhu_min_20km",
    "status", "arah_relatif",
    "jumlah_sel_signifikan", "luas_sel_terbesar_km2", "jarak_terdekat_km",
    "initial_heading_deg", "initial_speed_kmh",
    "cell_lat", "cell_lon", "dbz_maks_radar" 
]

POLA_TIMESTAMP = re.compile(r"(\d{12})\.nc$", re.IGNORECASE)
os.makedirs(CACHE_DIR, exist_ok=True)

# =============================================================
# FUNGSI SATELIT (Diringkas, sama seperti sebelumnya)
# =============================================================
def ambil_timestamp(nama_file):
    match = POLA_TIMESTAMP.search(nama_file)
    if not match: return datetime.min
    try: return datetime.strptime(match.group(1), "%Y%m%d%H%M")
    except ValueError: return datetime.min

def cari_koordinat(ds):
    lat_name = next((n for n in ["lat", "latitude", "y"] if n in ds.coords or n in ds.variables), None)
    lon_name = next((n for n in ["lon", "longitude", "x"] if n in ds.coords or n in ds.variables), None)
    return lat_name, lon_name

def cari_variabel_suhu(ds):
    for nama in ["brightness_temperature", "tbb", "data", "temp"]:
        if nama in ds.data_vars: return nama
    return list(ds.data_vars)[0]

def konversi_ke_celsius(data, variable):
    units = str(variable.attrs.get("units", "")).lower().strip()
    if units in ["k", "kelvin"]: return data - 273.15
    return data

def hitung_suhu_min_radius(lat, lon, data_values, lon_center, lat_center, radius_km):
    lon2d, lat2d = np.meshgrid(lon, lat) if lat.ndim == 1 else (lon, lat)
    dlat_km = (lat2d - lat_center) * 111.0
    dlon_km = (lon2d - lon_center) * 111.0 * np.cos(np.radians(lat_center))
    jarak_km = np.sqrt(dlat_km ** 2 + dlon_km ** 2)
    nilai = data_values[jarak_km <= radius_km]
    nilai = nilai[~np.isnan(nilai)]
    return float(np.nanmin(nilai)) if nilai.size > 0 else None

def hitung_luas_piksel_km2(lat, lon):
    dlat = abs(lat[1] - lat[0]) if lat.ndim == 1 else abs(lat[1, 0] - lat[0, 0])
    dlon = abs(lon[1] - lon[0]) if lon.ndim == 1 else abs(lon[0, 1] - lon[0, 0])
    return max((dlat * 111.0) * (dlon * 111.0 * np.cos(np.radians(float(np.nanmean(lat))))), 1e-6)

def hitung_jarak_grid_km(lat, lon, lon_center, lat_center):
    lon2d, lat2d = np.meshgrid(lon, lat) if lat.ndim == 1 else (lon, lat)
    dlat_km = (lat2d - lat_center) * 111.0
    dlon_km = (lon2d - lon_center) * 111.0 * np.cos(np.radians(lat_center))
    return np.sqrt(dlat_km ** 2 + dlon_km ** 2), lat2d, lon2d

def deteksi_sel_signifikan_satelit(lat, lon, data_values, target_lon, target_lat, radius_maks_km=None):
    mask = np.where(np.isnan(data_values), False, data_values <= AMBANG_SEL_SIGNIFIKAN_C)
    if not mask.any(): return []
    
    berlabel, jumlah_label = ndimage.label(mask)
    luas_px_km2 = hitung_luas_piksel_km2(lat, lon)
    jarak_grid_km, lat2d, lon2d = hitung_jarak_grid_km(lat, lon, target_lon, target_lat)
    
    daftar_sel = []
    for i in range(1, jumlah_label + 1):
        region_mask = berlabel == i
        luas_km2 = int(region_mask.sum()) * luas_px_km2
        if luas_km2 < LUAS_MIN_SEL_KM2: continue
        
        jarak_min_km = float(jarak_grid_km[region_mask].min())
        if radius_maks_km and jarak_min_km > radius_maks_km: continue
        
        rows, cols = np.where(region_mask)
        daftar_sel.append({
            "luas_km2": luas_km2, "jarak_km": jarak_min_km,
            "centroid_lat": float(lat2d[int(np.mean(rows)), int(np.mean(cols))]),
            "centroid_lon": float(lon2d[int(np.mean(rows)), int(np.mean(cols))]),
            "sumber": "SATELIT"
        })
    return daftar_sel

def tentukan_status_dari_sel(daftar_sel_dalam_radius):
    if not daftar_sel_dalam_radius: return "AMAN"
    jarak_terdekat = min(sel["jarak_km"] for sel in daftar_sel_dalam_radius)
    return "SIAGA" if jarak_terdekat <= RADIUS_SIAGA_KM else "WASPADA"

def hitung_bearing_derajat(lat1, lon1, lat2, lon2):
    lat1r, lat2r, dlon = np.radians(lat1), np.radians(lat2), np.radians(lon2 - lon1)
    x = np.sin(dlon) * np.cos(lat2r)
    y = np.cos(lat1r) * np.sin(lat2r) - np.sin(lat1r) * np.cos(lat2r) * np.cos(dlon)
    return float((np.degrees(np.arctan2(x, y)) + 360) % 360)

def hitung_jarak_antar_titik_km(lat1, lon1, lat2, lon2):
    dlat_km = (lat2 - lat1) * 111.0
    dlon_km = (lon2 - lon1) * 111.0 * np.cos(np.radians((lat1 + lat2) / 2.0))
    return float(np.sqrt(dlat_km ** 2 + dlon_km ** 2))

def _baca_posisi_terlacak_sebelumnya():
    if not os.path.exists(LOG_CSV): return None, None, None
    try: df_lama = pd.read_csv(LOG_CSV)
    except: return None, None, None
    if df_lama.empty or "cell_lat" not in df_lama.columns: return None, None, None
    baris_sebelumnya = df_lama.iloc[-1]
    prev_lat, prev_lon, prev_waktu = baris_sebelumnya.get("cell_lat"), baris_sebelumnya.get("cell_lon"), baris_sebelumnya.get("waktu_utc")
    if pd.isna(prev_lat) or pd.isna(prev_lon) or not prev_waktu: return None, None, None
    return prev_lat, prev_lon, prev_waktu

def lacak_pergerakan_sel(waktu_dt, daftar_sel):
    if not daftar_sel: return None, None, None, None
    sel_default = min(daftar_sel, key=lambda s: s["jarak_km"])
    prev_lat, prev_lon, prev_waktu = _baca_posisi_terlacak_sebelumnya()
    if prev_lat is None: return None, None, sel_default["centroid_lat"], sel_default["centroid_lon"]
    try: prev_dt = datetime.strptime(str(prev_waktu), "%Y-%m-%d %H:%M")
    except ValueError: return None, None, sel_default["centroid_lat"], sel_default["centroid_lon"]
    
    delta_jam = (waktu_dt - prev_dt).total_seconds() / 3600.0
    if not (0 < delta_jam <= TOLERANSI_LACAK_JAM): return None, None, sel_default["centroid_lat"], sel_default["centroid_lon"]
    
    sel_cocok = min(daftar_sel, key=lambda s: hitung_jarak_antar_titik_km(prev_lat, prev_lon, s["centroid_lat"], s["centroid_lon"]))
    kecepatan_kmh = hitung_jarak_antar_titik_km(prev_lat, prev_lon, sel_cocok["centroid_lat"], sel_cocok["centroid_lon"]) / delta_jam
    
    if kecepatan_kmh > KECEPATAN_MAKS_KMH: return None, None, sel_default["centroid_lat"], sel_default["centroid_lon"]
    return round(hitung_bearing_derajat(prev_lat, prev_lon, sel_cocok["centroid_lat"], sel_cocok["centroid_lon"]), 0), round(kecepatan_kmh, 1), sel_cocok["centroid_lat"], sel_cocok["centroid_lon"]

def simpan_log_status(baris_baru: dict):
    df_baru = pd.DataFrame([baris_baru])
    df_lama = pd.read_csv(LOG_CSV) if os.path.exists(LOG_CSV) else pd.DataFrame(columns=KOLOM_LOG)
    df_gabung = pd.concat([df_lama, df_baru], ignore_index=True).drop_duplicates(subset=["waktu_utc"], keep="last").sort_values("waktu_utc").tail(MAKS_BARIS_LOG)
    df_gabung.to_csv(LOG_CSV, index=False)
    print(f"Log status disimpan: {LOG_CSV} ({len(df_gabung)} baris)")

# =============================================================
# PROSES UTAMA
# =============================================================
def baca_dan_simpan(nc_file):
    print("=== BACA DATA:", os.path.basename(nc_file), "===")
    ds = xr.open_dataset(nc_file)
    lat_name, lon_name = cari_koordinat(ds)
    var = ds[cari_variabel_suhu(ds)]
    data_values = konversi_ke_celsius(var, var).values
    lat, lon = ds[lat_name].values, ds[lon_name].values
    
    while data_values.ndim > 2: data_values = data_values[0]
    if lat.ndim == 1 and lat[0] > lat[-1]: lat, data_values = lat[::-1], np.flip(data_values, axis=0)
    if lon.ndim == 1 and lon[0] > lon[-1]: lon, data_values = lon[::-1], np.flip(data_values, axis=1)
    
    data_values = np.asarray(data_values, dtype=float)
    data_values[(data_values < -120) | (data_values > 80)] = np.nan
    
    suhu_min_10km = hitung_suhu_min_radius(lat, lon, data_values, TARGET_LON, TARGET_LAT, RADIUS_SIAGA_KM)
    suhu_min_20km = hitung_suhu_min_radius(lat, lon, data_values, TARGET_LON, TARGET_LAT, RADIUS_WASPADA_KM)
    
    waktu_dt = ambil_timestamp(os.path.basename(nc_file))
    waktu_wib_dt = waktu_dt + timedelta(hours=7)

    # 1. DETEKSI SEL SATELIT
    sel_satelit = deteksi_sel_signifikan_satelit(lat, lon, data_values, TARGET_LON, TARGET_LAT, radius_maks_km=RADIUS_WASPADA_KM)

    # 2. DETEKSI SEL RADAR (LOGIKA OR)
    sel_radar = []
    if baca_radar is not None:
        try:
            sel_radar = baca_radar.proses_radar_sinkron(waktu_dt)
            # Hanya ambil sel radar yang sudah masuk radius waspada
            sel_radar = [s for s in sel_radar if s["jarak_km"] <= RADIUS_WASPADA_KM]
        except Exception as e:
            print(f"[GAGAL] Error membaca radar: {e}")

    # GABUNGKAN KEDUA DAFTAR SEL
    daftar_sel_gabungan = sel_satelit + sel_radar
    status = tentukan_status_dari_sel(daftar_sel_gabungan)
    
    # Ambil nilai max dBZ dari radar untuk di log
    dbz_maks_radar = max([s["dbz_maks"] for s in sel_radar]) if sel_radar else None

    jumlah_sel_signifikan = len(daftar_sel_gabungan)
    luas_terbesar_km2, jarak_terdekat_km = None, None
    if daftar_sel_gabungan:
        luas_terbesar_km2 = max(daftar_sel_gabungan, key=lambda s: s["luas_km2"])["luas_km2"]
        jarak_terdekat_km = min(daftar_sel_gabungan, key=lambda s: s["jarak_km"])["jarak_km"]

    heading, speed, c_lat, c_lon = lacak_pergerakan_sel(waktu_dt, daftar_sel_gabungan)

    print(f"Status: {status} | Sel Gabungan: {jumlah_sel_signifikan} | dBZ Maks: {dbz_maks_radar}")

    simpan_log_status({
        "waktu_utc": waktu_dt.strftime("%Y-%m-%d %H:%M") if waktu_dt != datetime.min else "",
        "waktu_wib": waktu_wib_dt.strftime("%Y-%m-%d %H:%M") if waktu_dt != datetime.min else "",
        "file_sumber": os.path.basename(nc_file),
        "suhu_min_10km": round(suhu_min_10km, 2) if suhu_min_10km is not None else "",
        "suhu_min_20km": round(suhu_min_20km, 2) if suhu_min_20km is not None else "",
        "status": status,
        "arah_relatif": "-",
        "jumlah_sel_signifikan": jumlah_sel_signifikan,
        "luas_sel_terbesar_km2": round(luas_terbesar_km2, 1) if luas_terbesar_km2 is not None else "",
        "jarak_terdekat_km": round(jarak_terdekat_km, 1) if jarak_terdekat_km is not None else "",
        "initial_heading_deg": heading if heading is not None else "",
        "initial_speed_kmh": speed if speed is not None else "",
        "cell_lat": c_lat if c_lat is not None else "",
        "cell_lon": c_lon if c_lon is not None else "",
        "dbz_maks_radar": round(dbz_maks_radar, 1) if dbz_maks_radar is not None else ""
    })

    ds.close()

    npz_path = os.path.join(CACHE_DIR, os.path.splitext(os.path.basename(nc_file))[0] + ".npz")
    np.savez(npz_path, lat=lat, lon=lon, data_values=data_values, status=np.array(status), nama_file=np.array(os.path.basename(nc_file)))
    
    print(f"NPZ_PATH:{npz_path}")
    return npz_path

if __name__ == "__main__":
    if len(sys.argv) < 2: sys.exit(1)
    baca_dan_simpan(sys.argv[1])