# -*- coding: utf-8 -*-
"""
Created on Mon Aug 31 18:36:42 2026

@author: bmkg bwi
"""

# -*- coding: utf-8 -*-
import sys
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature

INFO_RADAR = {
    "SURABAYA": {"lat": -7.230, "lon": 113.030},
    "DENPASAR": {"lat": -8.748, "lon": 115.167},
}
RADIUS_RADAR_KM = 250.0
FIGSIZE = (8, 8)
DPI = 150 # Resolusi sedang agar file GIF tidak terlalu berat

def gambar_peta_radar(radar_nama, file_input, file_output):
    print(f"Menggambar peta untuk: {os.path.basename(file_input)}")
    info = INFO_RADAR[radar_nama.upper()]
    
    fig = plt.figure(figsize=FIGSIZE, dpi=DPI, facecolor="#0e1117")
    ax = plt.axes(projection=ccrs.PlateCarree())
    ax.set_facecolor("#0a192f") # Warna laut gelap
    
    # Batas peta (sekitar 2.5 derajat dari pusat radar)
    ax.set_extent([info["lon"] - 2.5, info["lon"] + 2.5, info["lat"] - 2.5, info["lat"] + 2.5], crs=ccrs.PlateCarree())

    # Garis Pantai & Grid
    ax.add_feature(cfeature.COASTLINE.with_scale("10m"), edgecolor="#555555", linewidth=1.5, zorder=5)
    ax.add_feature(cfeature.BORDERS.with_scale("10m"), edgecolor="#555555", linewidth=1.0, zorder=5)
    ax.gridlines(crs=ccrs.PlateCarree(), draw_labels=True, linewidth=0.5, color="gray", alpha=0.5, linestyle="--", zorder=6)

    # Plot Gambar Radar
    try:
        img_radar = plt.imread(file_input)
        dlat = RADIUS_RADAR_KM / 111.0
        dlon = RADIUS_RADAR_KM / (111.0 * np.cos(np.radians(info["lat"])))
        extent_radar = [info["lon"] - dlon, info["lon"] + dlon, info["lat"] - dlat, info["lat"] + dlat]
        
        # Plot radar dengan zorder tinggi agar di atas garis pantai
        ax.imshow(img_radar, extent=extent_radar, transform=ccrs.PlateCarree(), origin='upper', zorder=10)
    except Exception as e:
        print(f"Gagal memuat {file_input}: {e}")

    # Tambahkan titik lokasi radar
    ax.plot(info["lon"], info["lat"], marker="^", color="red", markersize=8, transform=ccrs.PlateCarree(), zorder=15)
    waktu_str = os.path.basename(file_input).replace(".png", "").split("_")[-2:]
    ax.set_title(f"Radar {radar_nama.capitalize()} CMAX - {' '.join(waktu_str)} UTC", color="white", pad=10)

    plt.savefig(file_output, dpi=DPI, facecolor="#0e1117", bbox_inches="tight")
    plt.close(fig)

if __name__ == "__main__":
    if len(sys.argv) < 4:
        sys.exit(1)
    gambar_peta_radar(sys.argv[1], sys.argv[2], sys.argv[3])