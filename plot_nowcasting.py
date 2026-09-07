# -*- coding: utf-8 -*-
"""
Created on Mon Sep  7 21:28:54 2026

@author: Asus
"""

# -*- coding: utf-8 -*-
import os
import glob
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import cartopy.io.img_tiles as cimgt

INFO_RADAR = {
    "SURABAYA": {"lat": -7.460, "lon": 112.730},
    "DENPASAR": {"lat": -8.748, "lon": 115.177},
}
RADIUS_RADAR_KM = 250.0
DIR_SATELIT = "./Satelit"

def plot_prediksi(radar_nama):
    print(f"Memplot Nowcasting untuk {radar_nama}...")
    info = INFO_RADAR[radar_nama.upper()]
    
    # Cari file prediksi yang baru saja dibuat oleh opencv
    pola = os.path.join(DIR_SATELIT, f"RADAR_{radar_nama.upper()}_*_PREDIKSI_*.png")
    file_prediksi = glob.glob(pola)
    
    for file_input in file_prediksi:
        # Ekstrak informasi waktu dari nama file (misal: 10M, 20M)
        menit_prediksi = file_input.split("_")[-1].replace(".png", "")
        
        tiler = cimgt.QuadtreeTiles()
        fig = plt.figure(figsize=(8, 8), dpi=150, facecolor="#0e1117")
        ax = plt.axes(projection=tiler.crs)
        ax.set_facecolor("black")
        
        batas_extent = [info["lon"] - 2.5, info["lon"] + 2.5, info["lat"] - 2.5, info["lat"] + 2.5]
        ax.set_extent(batas_extent, crs=ccrs.PlateCarree())
        ax.add_image(tiler, 8, alpha=0.4) # Basemap satelit redup

        # Garis Pantai & Grid
        ax.add_feature(cfeature.COASTLINE.with_scale("10m"), edgecolor="#ffffff", alpha=0.6, linewidth=1.2, zorder=5)
        ax.add_feature(cfeature.BORDERS.with_scale("10m"), edgecolor="#ffffff", alpha=0.4, linewidth=0.8, zorder=5)
        gl = ax.gridlines(crs=ccrs.PlateCarree(), draw_labels=True, linewidth=0.5, color="gray", alpha=0.5, linestyle="--", zorder=6)
        gl.top_labels = gl.right_labels = False
        gl.xlabel_style = gl.ylabel_style = {'color': 'red', 'weight': 'bold', 'size': 9}

        # Plot overlay prediksi hujan
        img_radar = plt.imread(file_input)
        dlat = RADIUS_RADAR_KM / 111.0
        dlon = RADIUS_RADAR_KM / (111.0 * np.cos(np.radians(info["lat"])))
        extent_radar = [info["lon"] - dlon, info["lon"] + dlon, info["lat"] - dlat, info["lat"] + dlat]
        
        ax.imshow(img_radar, extent=extent_radar, transform=ccrs.PlateCarree(), origin='upper', zorder=10)
        ax.plot(info["lon"], info["lat"], marker="^", color="red", markersize=8, transform=ccrs.PlateCarree(), zorder=15)
        
        # Judul Peta
        ax.set_title(f"Prediksi Hujan {radar_nama.capitalize()} (+{menit_prediksi})", color="#ffcc00", fontweight="bold", pad=10)

        # Colorbar dBZ
        dbz_levels = [5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70]
        dbz_colors = ["#00ecec", "#01a0f6", "#0000f6", "#00ff00", "#00c800", "#009000", "#ffff00", "#e7c000", "#ff9000", "#ff0000", "#d60000", "#c00000", "#f800fd"]
        cmap_dbz = mcolors.ListedColormap(dbz_colors)
        norm_dbz = mcolors.BoundaryNorm(dbz_levels, cmap_dbz.N)
        sm_dbz = plt.cm.ScalarMappable(cmap=cmap_dbz, norm=norm_dbz)
        sm_dbz.set_array([])
        cbar_dbz = plt.colorbar(sm_dbz, ax=ax, orientation="vertical", shrink=0.75, pad=0.04)
        cbar_dbz.set_label("Intensitas (dBZ)", color="white", fontsize=10)
        cbar_dbz.ax.tick_params(colors="white", labelsize=8)

        # Simpan dengan nama standar agar mudah dipanggil Streamlit
        file_output = os.path.join(DIR_SATELIT, f"NOWCAST_FINAL_{radar_nama.upper()}_{menit_prediksi}.png")
        plt.savefig(file_output, dpi=150, facecolor="#0e1117", bbox_inches="tight")
        plt.close(fig)
        print(f"Tersimpan: {file_output}")

if __name__ == "__main__":
    plot_prediksi("SURABAYA")
    plot_prediksi("DENPASAR")