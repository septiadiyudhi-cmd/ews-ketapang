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
from PIL import Image

INFO_RADAR = {
    "SURABAYA": {"lat": -7.460, "lon": 112.730},
    "DENPASAR": {"lat": -8.748, "lon": 115.177},
}
RADIUS_RADAR_KM = 250.0
DIR_SATELIT = "./Satelit"

def plot_prediksi(radar_nama):
    print(f"Memplot Nowcasting untuk {radar_nama}...")
    info = INFO_RADAR[radar_nama.upper()]
    
    pola = os.path.join(DIR_SATELIT, f"RADAR_{radar_nama.upper()}_*_PREDIKSI_*.png")
    file_prediksi = glob.glob(pola)
    
    for file_input in file_prediksi:
        menit_prediksi = file_input.split("_")[-1].replace(".png", "")
        
        tiler = cimgt.QuadtreeTiles()
        fig = plt.figure(figsize=(8, 8), dpi=150, facecolor="#0e1117")
        ax = plt.axes(projection=tiler.crs)
        ax.set_facecolor("black")
        
        batas_extent = [info["lon"] - 2.5, info["lon"] + 2.5, info["lat"] - 2.5, info["lat"] + 2.5]
        ax.set_extent(batas_extent, crs=ccrs.PlateCarree())
        ax.add_image(tiler, 8, alpha=0.4)

        ax.add_feature(cfeature.COASTLINE.with_scale("10m"), edgecolor="#ffffff", alpha=0.6, linewidth=1.2, zorder=5)
        ax.add_feature(cfeature.BORDERS.with_scale("10m"), edgecolor="#ffffff", alpha=0.4, linewidth=0.8, zorder=5)
        gl = ax.gridlines(crs=ccrs.PlateCarree(), draw_labels=True, linewidth=0.5, color="gray", alpha=0.5, linestyle="--", zorder=6)
        gl.top_labels = gl.right_labels = False
        gl.xlabel_style = gl.ylabel_style = {'color': 'red', 'weight': 'bold', 'size': 9}

        img_radar = plt.imread(file_input)
        dlat = RADIUS_RADAR_KM / 111.0
        dlon = RADIUS_RADAR_KM / (111.0 * np.cos(np.radians(info["lat"])))
        extent_radar = [info["lon"] - dlon, info["lon"] + dlon, info["lat"] - dlat, info["lat"] + dlat]
        
        ax.imshow(img_radar, extent=extent_radar, transform=ccrs.PlateCarree(), origin='upper', zorder=10)
        ax.plot(info["lon"], info["lat"], marker="^", color="red", markersize=8, transform=ccrs.PlateCarree(), zorder=15)
        
        ax.set_title(f"Prediksi Hujan {radar_nama.capitalize()} (+{menit_prediksi})", color="#ffcc00", fontweight="bold", pad=10)

        dbz_levels = [5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70]
        dbz_colors = ["#00ecec", "#01a0f6", "#0000f6", "#00ff00", "#00c800", "#009000", "#ffff00", "#e7c000", "#ff9000", "#ff0000", "#d60000", "#c00000", "#f800fd"]
        cmap_dbz = mcolors.ListedColormap(dbz_colors)
        norm_dbz = mcolors.BoundaryNorm(dbz_levels, cmap_dbz.N)
        sm_dbz = plt.cm.ScalarMappable(cmap=cmap_dbz, norm=norm_dbz)
        sm_dbz.set_array([])
        cbar_dbz = plt.colorbar(sm_dbz, ax=ax, orientation="vertical", shrink=0.75, pad=0.04)
        cbar_dbz.set_label("Intensitas (dBZ)", color="white", fontsize=10)
        cbar_dbz.ax.tick_params(colors="white", labelsize=8)

        file_output = os.path.join(DIR_SATELIT, f"NOWCAST_FINAL_{radar_nama.upper()}_{menit_prediksi}.png")
        try:
            plt.savefig(file_output, dpi=150, facecolor="#0e1117", bbox_inches="tight")
            print(f"Tersimpan: {file_output}")
        except Exception as e:
            print(f"Peringatan: Gagal menyimpan {file_output} ({e})")
        finally:
            plt.close(fig)

def buat_gif_nowcast(radar_nama):
    print(f"Merajut GIF Nowcasting untuk {radar_nama}...")
    
    # Ambil frame kondisi saat ini (titik nol)
    pola_observasi = os.path.join(DIR_SATELIT, f"MAP_RADAR_{radar_nama.upper()}_*.png")
    file_observasi = sorted(glob.glob(pola_observasi))
    frame_awal = [file_observasi[-1]] if file_observasi else []

    # Susun berurutan +10, +20, +30
    frame_prediksi = [
        os.path.join(DIR_SATELIT, f"NOWCAST_FINAL_{radar_nama.upper()}_10M.png"),
        os.path.join(DIR_SATELIT, f"NOWCAST_FINAL_{radar_nama.upper()}_20M.png"),
        os.path.join(DIR_SATELIT, f"NOWCAST_FINAL_{radar_nama.upper()}_30M.png")
    ]
    
    frames_valid = frame_awal + [f for f in frame_prediksi if os.path.exists(f)]
    
    if len(frames_valid) > 1:
        try:
            images = [Image.open(f).convert("RGB") for f in frames_valid]
            output_gif = os.path.join(DIR_SATELIT, f"NOWCAST_RADAR_{radar_nama.upper()}.gif")
            
            # Frame terakhir (prediksi +30M) ditahan lebih lama
            durations = [700] * (len(images) - 1) + [2000]
            images[0].save(output_gif, save_all=True, append_images=images[1:], duration=durations, loop=0, optimize=True)
            print(f"[OK] Animasi Nowcast Selesai: {output_gif}")
        except Exception as e:
            print(f"[GAGAL] Gagal merajut GIF: {e}")

if __name__ == "__main__":
    plot_prediksi("SURABAYA")
    buat_gif_nowcast("SURABAYA")
    
    plot_prediksi("DENPASAR")
    buat_gif_nowcast("DENPASAR")
