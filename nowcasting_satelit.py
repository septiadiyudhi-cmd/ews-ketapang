# -*- coding: utf-8 -*-
"""
NOWCASTING SATELIT HIMAWARI-9 (BERBASIS .NPZ)
Memprediksi pergerakan suhu puncak awan hingga 60 menit ke depan tanpa distorsi peta.
"""

import os
import glob
import numpy as np
import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.colors import ListedColormap, BoundaryNorm
import matplotlib.ticker as mticker
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from PIL import Image
from datetime import datetime, timedelta, timezone

DIR_CACHE = "./Satelit/_cache"
DIR_SATELIT = "./Satelit"

def proses_nowcasting_satelit_npz():
    print("\n=== Memulai Nowcasting Satelit Himawari-9 (Mode NPZ) ===")
    
    pola_pencarian = os.path.join(DIR_CACHE, "H09_B13_*.npz")
    daftar_file = sorted(glob.glob(pola_pencarian))
    
    if len(daftar_file) < 2:
        print("File data mentah .npz kurang dari 2. Nowcasting dibatalkan.")
        return
        
    file_sebelumnya = daftar_file[-2]
    file_terbaru = daftar_file[-1]
    
    try:
        npz_prev = np.load(file_sebelumnya)
        npz_curr = np.load(file_terbaru)
        
        data_prev = npz_prev['data_values']
        data_curr = npz_curr['data_values']
        lons = npz_curr['lon']
        lats = npz_curr['lat']
        
        if len(data_prev.shape) == 1:
            data_prev = data_prev.reshape((len(lats), len(lons)))
        if len(data_curr.shape) == 1:
            data_curr = data_curr.reshape((len(lats), len(lons)))
            
    except Exception as e:
        print(f"Gagal memuat data .npz: {e}")
        return

    # Normalisasi data suhu ke format 8-bit dengan Gaussian Blur untuk membuang noise (titik liar)
    def skala_ke_8bit(data_suhu):
        data_clip = np.clip(data_suhu, -80, 40)
        data_8bit = ((40 - data_clip) / 120 * 255).astype(np.uint8)
        # Efek blur agar gradien awan satelit lebih halus saat dibaca mesin
        data_blur = cv2.GaussianBlur(data_8bit, (5, 5), 0)
        return data_blur

    gray_prev = skala_ke_8bit(data_prev)
    gray_curr = skala_ke_8bit(data_curr)

    # Perhitungan Optical Flow
    flow = cv2.calcOpticalFlowFarneback(gray_prev, gray_curr, None, 
                                        pyr_scale=0.5, levels=3, winsize=31, 
                                        iterations=3, poly_n=7, poly_sigma=1.5, flags=0)
                                        
    # KUNCI PERBAIKAN: Gunakan Gaussian Blur yang kuat pada matriks vektor arah pergerakan.
    # Ini akan menyatukan pergerakan piksel liar sehingga seluruh peta bergeser mulus serentak.
    flow[..., 0] = cv2.GaussianBlur(flow[..., 0], (25, 25), 0)
    flow[..., 1] = cv2.GaussianBlur(flow[..., 1], (25, 25), 0)

    nama_file = os.path.basename(file_terbaru)
    waktu_str = nama_file.split("_")[-1].replace(".npz", "")
    try:
        waktu_awal = datetime.strptime(waktu_str, "%Y%m%d%H%M")
    except Exception:
        waktu_awal = datetime.now(timezone.utc)

    frame_prediksi = []
    
    # Rentang suhu & warna kustom identik dengan EWS Utama
    batas_suhu = [-100, -80, -75, -69, -62, -56, -48, -41, -34, -28, -21, -13, -7, 0, 8, 14, 21, 60]
    daftar_warna = [
        "#ff0000", "#ff4444", "#ff7777", "#ffb07c", "#ff9900", "#ff6600",
        "#d99b00", "#b8b000", "#9ed000", "#68d900", "#00e070", "#00bfbf",
        "#27a7e8", "#458df5", "#416fca", "#14588e", "#08355f"
    ]
    cmap_kustom = ListedColormap(daftar_warna)
    norm_kustom = BoundaryNorm(batas_suhu, cmap_kustom.N)

    for step in range(0, 7):
        menit = step * 10
        waktu_berlaku = waktu_awal + timedelta(minutes=menit)
        teks_waktu = waktu_berlaku.strftime("%Y-%m-%d %H:%M UTC")
        
        if step == 0:
            data_pred = data_curr.astype(np.float32)
        else:
            h, w = data_curr.shape
            map_x, map_y = np.meshgrid(np.arange(w), np.arange(h))
            map_x = map_x - (flow[..., 0] * step)
            map_y = map_y - (flow[..., 1] * step)
            
            # Kita remap seluruh data suhu aslinya, tanpa masking
            data_pred = cv2.remap(data_curr.astype(np.float32), map_x.astype(np.float32), map_y.astype(np.float32), 
                                  interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        
        fig = plt.figure(figsize=(10, 6), dpi=150, facecolor="#0e1117")
        ax = plt.axes(projection=ccrs.PlateCarree())
        ax.set_facecolor("#0e1117")
        ax.set_extent([112.0, 116.0, -9.5, -6.5], crs=ccrs.PlateCarree())
        
        ax.add_feature(cfeature.COASTLINE.with_scale('10m'), edgecolor="#ffffff", linewidth=1.0, zorder=5)
        ax.add_feature(cfeature.BORDERS.with_scale('10m'), edgecolor="#aaaaaa", linewidth=0.8, linestyle='--', zorder=5)

        # Definisikan titik pasti untuk garis grid dan teks
        koordinat_x = [112.0, 112.5, 113.0, 113.5, 114.0, 114.5, 115.0, 115.5, 116.0]
        koordinat_y = [-6.5, -7.0, -7.5, -8.0, -8.5, -9.0, -9.5]

        # KUNCI PERBAIKAN: Gunakan FixedLocator untuk memaksa Cartopy menggambar garis grid
        gl = ax.gridlines(
            crs=ccrs.PlateCarree(), draw_labels=False, linewidth=1.0, 
            color="white", alpha=0.65, linestyle="--", zorder=30
        )
        gl.xlocator = mticker.FixedLocator(koordinat_x)
        gl.ylocator = mticker.FixedLocator(koordinat_y)

        # Label Longitude (Berada di dasar peta: Y = -9.5)
        for lon_tick in koordinat_x[1:-1]: # Lewati ujung agar teks tidak terpotong tepi
            ax.text(lon_tick, -9.5 + 0.03, f"{lon_tick:.1f}\u00b0E", transform=ccrs.PlateCarree(), color="#ff5555", fontsize=10, ha="center", va="bottom", zorder=35)
            
        # Label Latitude (Berada di sisi kiri peta: X = 112.0)
        for lat_tick in koordinat_y[1:-1]: # Lewati ujung agar teks tidak terpotong tepi
            ax.text(112.0 + 0.03, lat_tick, f"{abs(lat_tick):.1f}\u00b0S", transform=ccrs.PlateCarree(), color="#ff5555", fontsize=10, ha="left", va="center", rotation=90, zorder=35)
        
        # Gambar prediksi dengan contourf agar batas suhunya melengkung mulus
        mesh = ax.contourf(
            lons, lats, data_pred, 
            levels=batas_suhu, 
            cmap=cmap_kustom, 
            norm=norm_kustom, 
            transform=ccrs.PlateCarree(), 
            zorder=2
        )
        
        judul_tambahan = "(Aktual)" if step == 0 else "(Prediksi)"
        ax.set_title(f"Satelit Himawari-9 (Suhu Puncak Awan) {judul_tambahan}\nBerlaku: {teks_waktu}", color="#33cc66", fontweight="bold", pad=15)
        
        # Colorbar presisi di sisi kanan luar peta
        cax_satelit = ax.inset_axes([1.02, 0.1, 0.03, 0.8])
        cbar = plt.colorbar(mesh, cax=cax_satelit, orientation='vertical', ticks=batas_suhu)
        cbar.set_label("Suhu (°C)", color="white")
        cbar.ax.tick_params(colors="white", labelsize=8)
        
        file_output = os.path.join(DIR_SATELIT, f"NOWCAST_FINAL_SATELIT_{menit}M.png")
        try:
            plt.savefig(file_output, dpi=120, facecolor="#0e1117", bbox_inches="tight")
            frame_prediksi.append(file_output)
        except Exception:
            pass
        finally:
            plt.close(fig)

    # Rajut GIF dengan Anti-Flicker (Palet Terkunci)
    frames_valid = [f for f in frame_prediksi if os.path.exists(f)]
    
    if len(frames_valid) > 1:
        try:
            images = [Image.open(f).convert("RGB") for f in frames_valid]
            
            # Kunci palet warna dari gambar pertama
            img_pertama = images[0].convert("P", palette=Image.ADAPTIVE, colors=256)
            frames_seragam = [img_pertama]
            for img in images[1:]:
                frames_seragam.append(img.quantize(palette=img_pertama))
                
            output_gif = os.path.join(DIR_SATELIT, "NOWCAST_SATELIT_ANIMASI.gif")
            durations = [700] * (len(images) - 1) + [2000]
            
            frames_seragam[0].save(
                output_gif, save_all=True, append_images=frames_seragam[1:],
                duration=durations, loop=0, optimize=False
            )
            print(f"Animasi Satelit Selesai: {output_gif}")
        except Exception as e:
            print(f"Gagal merajut GIF: {e}")

if __name__ == "__main__":
    proses_nowcasting_satelit_npz()
