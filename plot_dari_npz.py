# -*- coding: utf-8 -*-
"""
GAMBAR PETA DARI FILE .npz + OVERLAY RADAR CUACA
=============================================================
Menggambar citra Himawari (dari .npz) dan menumpuk gambar 
radar cuaca (CMAX) Denpasar dan Surabaya di atasnya.
"""

import sys
import os
import shutil
import re
import glob
from datetime import datetime, timedelta

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import cartopy.crs as ccrs
import cartopy.feature as cfeature

# =============================================================
# KONFIGURASI
# =============================================================
LOCAL_DIR = "./Satelit"

TARGET_LON = 114.43
TARGET_LAT = -8.15

# Radius lingkaran di peta
RADIUS_SIAGA_KM = 15
RADIUS_WASPADA_KM = 30

FIGSIZE = (12, 12)
DPI = 800

TEMP_LEVELS = [-100, -80, -75, -69, -62, -56, -48, -41, -34, -28, -21, -13, -7, 0, 8, 14, 21, 60]
TEMP_COLORS = [
    "#ff0000", "#ff4444", "#ff7777", "#ffb07c", "#ff9900", "#ff6600",
    "#d99b00", "#b8b000", "#9ed000", "#68d900", "#00e070", "#00bfbf",
    "#27a7e8", "#458df5", "#416fca", "#14588e", "#08355f"
]

POLA_TIMESTAMP = re.compile(r"(\d{12})\.nc$", re.IGNORECASE)

INFO_RADAR = {
    "SURABAYA": {"lat": -7.230, "lon": 113.030},
    "DENPASAR": {"lat": -8.748, "lon": 115.167},
}
RADIUS_RADAR_KM = 250.0

# =============================================================
# FUNGSI BANTUAN
# =============================================================
def ambil_timestamp(nama_file):
    match = POLA_TIMESTAMP.search(nama_file)
    if not match: return datetime.min
    try: return datetime.strptime(match.group(1), "%Y%m%d%H%M")
    except ValueError: return datetime.min

def format_waktu_satellite(nama_file):
    waktu = ambil_timestamp(nama_file)
    if waktu == datetime.min: return "Waktu tidak diketahui"
    return waktu.strftime("%d/%m/%Y %H:%M UTC")

def buat_lingkaran_km(lon_center, lat_center, radius_km, jumlah_titik=360):
    sudut = np.linspace(0, 2 * np.pi, jumlah_titik)
    radius_lat = radius_km / 111.0
    radius_lon = radius_km / (111.0 * np.cos(np.radians(lat_center)))
    return (lon_center + radius_lon * np.cos(sudut), lat_center + radius_lat * np.sin(sudut))

def cari_file_radar_terdekat(waktu_target, radar_nama):
    """Mencari file PNG radar terdekat dengan batas toleransi 15 menit."""
    pola_pencarian = os.path.join(LOCAL_DIR, f"RADAR_{radar_nama}_*.png")
    daftar_file = glob.glob(pola_pencarian)
    file_terpilih = None
    selisih_terkecil = timedelta(minutes=30)
    
    for f in daftar_file:
        nama_file = os.path.basename(f)
        try:
            waktu_str = nama_file.split('_')[-2] + '_' + nama_file.split('_')[-1][:4]
            waktu_file = datetime.strptime(waktu_str, "%Y%m%d_%H%M")
            selisih = abs(waktu_target - waktu_file)
            if selisih <= selisih_terkecil:
                selisih_terkecil, file_terpilih = selisih, f
        except Exception: pass
    return file_terpilih

# =============================================================
# PROSES UTAMA PENGGAMBARAN
# =============================================================
def gambar_dari_npz(npz_path):
    print("\n=== GAMBAR PETA:", os.path.basename(npz_path), "===")
    npz = np.load(npz_path, allow_pickle=True)

    lat = npz["lat"]
    lon = npz["lon"]
    data_values = npz["data_values"]
    status = str(npz["status"])
    nama_file = str(npz["nama_file"])
    waktu_dt = ambil_timestamp(nama_file)

    warna_lingkaran = {"AMAN": "#33cc66", "WASPADA": "#ffcc00", "SIAGA": "#ff3333"}.get(status, "white")
    cmap = mcolors.ListedColormap(TEMP_COLORS)
    norm = mcolors.BoundaryNorm(TEMP_LEVELS, cmap.N)

    fig = plt.figure(figsize=FIGSIZE, dpi=DPI, facecolor="black")
    ax = plt.axes(projection=ccrs.PlateCarree())
    ax.set_facecolor("black")
    ax.set_extent([113.70, 115.90, -9.20, -7.00], crs=ccrs.PlateCarree())

    # 1. PLOT AWAN SATELIT (Z-Order: 1)
    mesh = ax.pcolormesh(lon, lat, data_values, cmap=cmap, norm=norm, shading="auto", transform=ccrs.PlateCarree(), zorder=1)

    # 2. PLOT OVERLAY RADAR CUACA (Z-Order: 15)
    for radar_nama, info in INFO_RADAR.items():
        file_radar = cari_file_radar_terdekat(waktu_dt, radar_nama)
        if file_radar:
            try:
                img_radar = plt.imread(file_radar)
                dlat = RADIUS_RADAR_KM / 111.0
                dlon = RADIUS_RADAR_KM / (111.0 * np.cos(np.radians(info["lat"])))
                
                # Extent = [kiri, kanan, bawah, atas]
                extent_radar = [
                    info["lon"] - dlon, info["lon"] + dlon,
                    info["lat"] - dlat, info["lat"] + dlat
                ]
                
                # Plot radar dengan sedikit transparansi (alpha=0.85) agar awan satelit di bawahnya tetap terlihat teksturnya
                ax.imshow(img_radar, extent=extent_radar, transform=ccrs.PlateCarree(), origin='upper', zorder=15, alpha=0.85)
                print(f"[{radar_nama}] Overlay radar dipasang: {os.path.basename(file_radar)}")
            except Exception as e:
                print(f"[{radar_nama}] Gagal memasang overlay radar: {e}")

    # 3. PLOT GARIS PANTAI & GRID (Z-Order: 30, agar selalu ada di atas awan & radar)
    ax.add_feature(cfeature.COASTLINE.with_scale("10m"), edgecolor="white", linewidth=1.0, zorder=30)
    ax.add_feature(cfeature.BORDERS.with_scale("10m"), edgecolor="white", linewidth=0.8, zorder=30)
    ax.gridlines(crs=ccrs.PlateCarree(), draw_labels=False, linewidth=1.0, color="white", alpha=0.65, linestyle=":", zorder=30)

    for lon_tick in [114.0, 114.3, 114.6, 114.9, 115.2, 115.5, 115.8]:
        ax.text(lon_tick, -9.20 + 0.02, f"{lon_tick:.1f}\u00b0E", transform=ccrs.PlateCarree(), color="#ff5555", fontsize=10, ha="center", va="bottom", zorder=35)
    for lat_tick in [-7.2, -7.5, -7.8, -8.1, -8.4, -8.7, -9.0]:
        ax.text(113.70 + 0.02, lat_tick, f"{abs(lat_tick):.1f}\u00b0S", transform=ccrs.PlateCarree(), color="#ff5555", fontsize=10, ha="left", va="center", rotation=90, zorder=35)

    # 4. PLOT LINGKARAN RADIUS & TARGET KETAPANG (Z-Order: 20-25)
    lon30, lat30 = buat_lingkaran_km(TARGET_LON, TARGET_LAT, RADIUS_WASPADA_KM)
    ax.plot(lon30, lat30, color=warna_lingkaran, linewidth=2, linestyle="--", transform=ccrs.PlateCarree(), zorder=20)
    lon15, lat15 = buat_lingkaran_km(TARGET_LON, TARGET_LAT, RADIUS_SIAGA_KM)
    ax.plot(lon15, lat15, color="magenta", linewidth=2, linestyle="--", transform=ccrs.PlateCarree(), zorder=21)
    ax.plot(TARGET_LON, TARGET_LAT, marker="s", markersize=4, markerfacecolor="magenta", markeredgecolor="white", transform=ccrs.PlateCarree(), zorder=22)

    # Kosmetik Peta (Colorbar & Judul)
    cbar = plt.colorbar(mesh, ax=ax, orientation="vertical", shrink=0.55, pad=0.035, ticks=TEMP_LEVELS)
    cbar.set_label("Suhu Satelit (°C)", color="white", fontsize=13)
    cbar.ax.tick_params(colors="white", labelsize=10)

    waktu_judul = format_waktu_satellite(nama_file)
    ax.set_title(f"EWS Multi-Sensor (H09 + Radar): {waktu_judul}  |  Status: {status}", loc="left", fontsize=16, fontweight="bold", color="#fff8cf", pad=12)
    ax.text(0.99, 0.985, "© BMKG - Stasiun Meteorologi Banyuwangi", transform=ax.transAxes, ha="right", va="top", fontsize=10, color="lightgray")

    nama_png = os.path.splitext(nama_file)[0] + ".png"
    output_png = os.path.join(LOCAL_DIR, nama_png)
    plt.savefig(output_png, dpi=DPI, facecolor="black", bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)

    shutil.copy2(output_png, os.path.join(LOCAL_DIR, "HIMAWARI_B13_TERBARU.png"))
    print("Selesai menggambar:", output_png)
    return output_png

if __name__ == "__main__":
    if len(sys.argv) < 2: sys.exit(1)
    gambar_dari_npz(sys.argv[1])