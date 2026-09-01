# -*- coding: utf-8 -*-
"""
BACA RADAR CUACA (CMAX) -> KONVERSI WARNA KE dBZ -> DETEKSI SEL
=============================================================
Skrip ini dipanggil oleh baca_data.py untuk melengkapi deteksi
awan konvektif (Satelit OR Radar).
"""

import os
import glob
from datetime import datetime, timedelta
import numpy as np
from PIL import Image
from scipy import ndimage

# =============================================================
# KONFIGURASI LOKASI & RADAR
# =============================================================
LOCAL_DIR = "./Satelit"

# Titik target EWS (Ketapang)
TARGET_LON = 114.43
TARGET_LAT = -8.15

# Radius maksimal dari tepi gambar ke pusat radar (Standar CMAX BMKG)
RADIUS_RADAR_KM = 250.0 

INFO_RADAR = {
    "SURABAYA": {"lat": -7.230, "lon": 113.030},
    "DENPASAR": {"lat": -8.748, "lon": 115.167},
}

TOLERANSI_WAKTU_MENIT = 30
AMBANG_DBZ_SIGNIFIKAN = 5.0  # Hujan ringan ke atas
LUAS_MIN_SEL_KM2 = 4.0       # Minimal luas piksel agar tidak noise

# =============================================================
# KAMUS WARNA KE dBZ (Color-to-dBZ Mapping)
# =============================================================
# Diambil dari colorbar standar SIDARMA BMKG
TABEL_WARNA = np.array([
    [0, 255, 255],   # 5 dBZ (Cyan)
    [0, 200, 255],   # 10 dBZ
    [0, 0, 255],     # 15 dBZ (Biru)
    [0, 255, 0],     # 20 dBZ (Hijau)
    [0, 200, 0],     # 25 dBZ
    [0, 150, 0],     # 30 dBZ
    [255, 255, 0],   # 35 dBZ (Kuning)
    [255, 200, 0],   # 40 dBZ (Oranye)
    [255, 100, 0],   # 45 dBZ
    [255, 0, 0],     # 50 dBZ (Merah)
    [200, 0, 0],     # 55 dBZ
    [150, 0, 0],     # 60 dBZ
    [255, 0, 255],   # 65 dBZ (Magenta)
    [200, 0, 200],   # 70 dBZ
])
NILAI_DBZ = np.array([5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70])

# =============================================================
# FUNGSI UTAMA
# =============================================================

def konversi_rgb_ke_dbz(image_array):
    """Mencocokkan warna piksel RGB ke nilai dBZ terdekat."""
    # Hanya proses piksel yang tidak transparan (Alpha > 0)
    alpha = image_array[..., 3] if image_array.shape[2] == 4 else np.ones(image_array.shape[:2])
    mask_valid = alpha > 0
    
    dbz_array = np.full(image_array.shape[:2], np.nan)
    
    if not np.any(mask_valid):
        return dbz_array
        
    rgb_valid = image_array[mask_valid, :3]
    
    # Hitung jarak Euclidean dari setiap piksel ke setiap warna di tabel
    # (Metode vektorisasi numpy agar cepat)
    jarak = np.linalg.norm(rgb_valid[:, np.newaxis, :] - TABEL_WARNA, axis=2)
    idx_warna_terdekat = np.argmin(jarak, axis=1)
    
    dbz_array[mask_valid] = NILAI_DBZ[idx_warna_terdekat]
    return dbz_array

def buat_grid_koordinat(lebar, tinggi, lat_pusat, lon_pusat):
    """Membuat array Latitude dan Longitude untuk setiap piksel gambar."""
    # km per piksel
    res_km = (RADIUS_RADAR_KM * 2) / lebar
    
    x = np.arange(lebar)
    y = np.arange(tinggi)
    xx, yy = np.meshgrid(x, y)
    
    cx, cy = lebar / 2.0, tinggi / 2.0
    
    dx_km = (xx - cx) * res_km
    dy_km = (cy - yy) * res_km  # Y terbalik (0 di atas)
    
    lat_grid = lat_pusat + (dy_km / 111.0)
    lon_grid = lon_pusat + (dx_km / (111.0 * np.cos(np.radians(lat_pusat))))
    
    # Luas 1 piksel
    luas_piksel_km2 = res_km * res_km
    return lat_grid, lon_grid, luas_piksel_km2

def cari_file_terdekat(waktu_target, radar_nama):
    """Mencari gambar radar yang waktunya paling dekat dengan waktu satelit."""
    pola_pencarian = os.path.join(LOCAL_DIR, f"RADAR_{radar_nama}_*.png")
    daftar_file = glob.glob(pola_pencarian)
    
    file_terpilih = None
    selisih_terkecil = timedelta(minutes=TOLERANSI_WAKTU_MENIT)
    
    for f in daftar_file:
        nama_file = os.path.basename(f)
        try:
            # Parse 'RADAR_SURABAYA_20260831_1118.png'
            waktu_str = nama_file.split('_')[-2] + '_' + nama_file.split('_')[-1][:4]
            waktu_file = datetime.strptime(waktu_str, "%Y%m%d_%H%M")
            
            selisih = abs(waktu_target - waktu_file)
            if selisih <= selisih_terkecil:
                selisih_terkecil = selisih
                file_terpilih = f
        except Exception:
            continue
            
    return file_terpilih

def ekstrak_sel_radar(path_file, radar_nama):
    """Membaca gambar, mendeteksi sel >= 5 dBZ, menghitung jarak ke Ketapang."""
    img = Image.open(path_file).convert("RGBA")
    arr = np.array(img)
    
    dbz_array = konversi_rgb_ke_dbz(arr)
    
    lat_pusat = INFO_RADAR[radar_nama]["lat"]
    lon_pusat = INFO_RADAR[radar_nama]["lon"]
    
    lat_grid, lon_grid, luas_px = buat_grid_koordinat(arr.shape[1], arr.shape[0], lat_pusat, lon_pusat)
    
    mask_signifikan = (dbz_array >= AMBANG_DBZ_SIGNIFIKAN) & (~np.isnan(dbz_array))
    
    if not np.any(mask_signifikan):
        return []
        
    berlabel, jumlah_label = ndimage.label(mask_signifikan)
    
    # Hitung jarak tiap piksel ke Ketapang
    dlat = (lat_grid - TARGET_LAT) * 111.0
    dlon = (lon_grid - TARGET_LON) * 111.0 * np.cos(np.radians(TARGET_LAT))
    jarak_ke_target_km = np.sqrt(dlat**2 + dlon**2)
    
    daftar_sel = []
    
    for i in range(1, jumlah_label + 1):
        region_mask = (berlabel == i)
        luas_km2 = np.sum(region_mask) * luas_px
        
        if luas_km2 < LUAS_MIN_SEL_KM2:
            continue
            
        jarak_min = np.min(jarak_ke_target_km[region_mask])
        dbz_maks = np.max(dbz_array[region_mask])
        
        # Cari centroid
        rows, cols = np.where(region_mask)
        lat_tengah = lat_grid[int(np.mean(rows)), int(np.mean(cols))]
        lon_tengah = lon_grid[int(np.mean(rows)), int(np.mean(cols))]
        
        daftar_sel.append({
            "sumber": f"RADAR_{radar_nama}",
            "dbz_maks": float(dbz_maks),
            "luas_km2": float(luas_km2),
            "jarak_km": float(jarak_min),
            "centroid_lat": float(lat_tengah),
            "centroid_lon": float(lon_tengah),
        })
        
    return daftar_sel

def proses_radar_sinkron(waktu_satelit_dt):
    """
    Fungsi utama yang dipanggil oleh skrip satelit.
    Mengembalikan daftar gabungan sel radar SBY dan DEN.
    """
    sel_gabungan = []
    
    for radar in ["SURABAYA", "DENPASAR"]:
        file_radar = cari_file_terdekat(waktu_satelit_dt, radar)
        if file_radar:
            sel_radar = ekstrak_sel_radar(file_radar, radar)
            sel_gabungan.extend(sel_radar)
            
    return sel_gabungan

# Untuk test jalan terpisah
if __name__ == "__main__":
    sekarang = datetime.now()
    print(f"Menguji pencarian radar terdekat untuk waktu: {sekarang}")
    hasil = proses_radar_sinkron(sekarang)
    for sel in hasil:
        print(f"Terdeteksi: {sel['sumber']} | dBZ Maks: {sel['dbz_maks']} | Jarak: {sel['jarak_km']:.1f} km")