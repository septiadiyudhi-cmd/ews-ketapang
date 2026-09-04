# -*- coding: utf-8 -*-
"""
Created on Mon Aug 31 18:36:42 2026

@author: bmkg bwi
"""

import sys
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import cartopy.io.img_tiles as cimgt  # <-- Modul untuk basemap citra satelit asli

INFO_RADAR = {
    "SURABAYA": {"lat": -7.460, "lon": 112.730},
    "DENPASAR": {"lat": -8.748, "lon": 115.177},
}
RADIUS_RADAR_KM = 250.0
FIGSIZE = (8, 8)
DPI = 150  # Resolusi sedang agar file GIF tidak terlalu berat

def gambar_peta_radar(radar_nama, file_input, file_output):
    print(f"Menggambar peta untuk: {os.path.basename(file_input)}")
    info = INFO_RADAR[radar_nama.upper()]
    
    # 1. PERSIAPAN BASEMAP SATELIT ASLI
    tiler = cimgt.QuadtreeTiles()
    fig = plt.figure(figsize=FIGSIZE, dpi=DPI, facecolor="#0e1117")
    
    # Proyeksi peta mengikuti tiler (Web Mercator)
    ax = plt.axes(projection=tiler.crs)
    
    # Batas peta (sekitar 2.5 derajat dari pusat radar)
    batas_extent = [info["lon"] - 2.5, info["lon"] + 2.5, info["lat"] - 2.5, info["lat"] + 2.5]
    ax.set_extent(batas_extent, crs=ccrs.PlateCarree())

    # Tambahkan gambar satelit ke latar belakang (Zoom level 8)
    ax.add_image(tiler, 8)

    # Garis Pantai & Grid (Warna diubah putih agak transparan agar kontras dengan citra satelit)
    ax.add_feature(cfeature.COASTLINE.with_scale("10m"), edgecolor="#ffffff", alpha=0.7, linewidth=1.5, zorder=5)
    ax.add_feature(cfeature.BORDERS.with_scale("10m"), edgecolor="#ffffff", alpha=0.5, linewidth=1.0, zorder=5)
    
    # 1. GRIDLINES DENGAN TEKS KOORDINAT WARNA MERAH
    gl = ax.gridlines(crs=ccrs.PlateCarree(), draw_labels=True, linewidth=0.5, color="gray", alpha=0.5, linestyle="--", zorder=6)
    gl.top_labels = False
    gl.right_labels = False
    gl.xlabel_style = {'color': 'red', 'weight': 'bold', 'size': 9}
    gl.ylabel_style = {'color': 'red', 'weight': 'bold', 'size': 9}

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

    # 2. COLORBAR SKALA INTENSITAS RADAR (dBZ)
    dbz_levels = [5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70]
    dbz_colors = [
        "#00ecec", "#01a0f6", "#0000f6", "#00ff00", "#00c800", "#009000",
        "#ffff00", "#e7c000", "#ff9000", "#ff0000", "#d60000", "#c00000", "#f800fd"
    ]
    cmap_dbz = mcolors.ListedColormap(dbz_colors)
    norm_dbz = mcolors.BoundaryNorm(dbz_levels, cmap_dbz.N)
    
    sm_dbz = plt.cm.ScalarMappable(cmap=cmap_dbz, norm=norm_dbz)
    sm_dbz.set_array([])
    
    cbar_dbz = plt.colorbar(sm_dbz, ax=ax, orientation="vertical", shrink=0.75, pad=0.04)
    cbar_dbz.set_label("Intensitas (dBZ)", color="white", fontsize=10)
    cbar_dbz.ax.tick_params(colors="white", labelsize=8)

    plt.savefig(file_output, dpi=DPI, facecolor="#0e1117", bbox_inches="tight")
    plt.close(fig)

if __name__ == "__main__":
    if len(sys.argv) < 4:
        sys.exit(1)
    gambar_peta_radar(sys.argv[1], sys.argv[2], sys.argv[3])
