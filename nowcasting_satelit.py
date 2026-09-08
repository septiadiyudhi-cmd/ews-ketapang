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
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from PIL import Image
from datetime import datetime, timedelta

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

    # Perhitungan Optical Flow (Disetel khusus untuk awan satelit)
    flow = cv2.calcOpticalFlowFarneback(gray_prev, gray_curr, None, 
                                        pyr_scale=0.5, levels=3, winsize=31, 
                                        iterations=3, poly_n=7, poly_sigma=1.5, flags=0)
                                        
    # Median Filter untuk merapikan arah angin (mencegah efek garis melar)
    flow[..., 0] = cv2.medianBlur(flow[..., 0], 5)
    flow[..., 1] = cv2.medianBlur(flow[..., 1], 5)

    nama_file = os.path.basename(file_terbaru)
    waktu_str = nama_file.split("_")[-1].replace(".npz", "")
    try:
        waktu_awal = datetime.strptime(waktu_str, "%Y%m%d%H%M")
    except Exception:
        waktu_awal = datetime.utcnow()

    frame_prediksi = []
    
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
             
             data_pred = cv2.remap(data_curr.astype(np.float32), map_x.astype(np.float32), map_y.astype(np.float32), 
                                   interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        
        # Ukuran dan resolusi peta diperkecil (figsize 8x5, dpi 120)
        fig = plt.figure(figsize=(10, 6), dpi=150, facecolor="#0e1117")
        ax = plt.axes(projection=ccrs.PlateCarree())
        ax.set_facecolor("#0e1117")
        ax.set_extent([112.0, 116.0, -9.5, -6.5], crs=ccrs.PlateCarree())
        
        ax.add_feature(cfeature.COASTLINE.with_scale('10m'), edgecolor="#ffffff", linewidth=1.0, zorder=5)
        ax.add_feature(cfeature.BORDERS.with_scale('10m'), edgecolor="#aaaaaa", linewidth=0.8, linestyle='--', zorder=5)
        
        data_mask = np.ma.masked_greater(data_pred, 5.0)
        
        mesh = ax.pcolormesh(lons, lats, data_mask, transform=ccrs.PlateCarree(),
                             cmap='nipy_spectral_r', vmin=-80, vmax=20, zorder=2, shading='auto')
        
        judul_tambahan = "(Aktual)" if step == 0 else "(Prediksi)"
        ax.set_title(f"Satelit Himawari-9 (Suhu Puncak Awan) {judul_tambahan}\nBerlaku: {teks_waktu}", color="#33cc66", fontweight="bold", pad=15)
        
        cbar = plt.colorbar(mesh, ax=ax, orientation='vertical', pad=0.02, shrink=0.8)
        cbar.set_label("Suhu (°C)", color="white")
        cbar.ax.tick_params(colors="white")
        
        file_output = os.path.join(DIR_SATELIT, f"NOWCAST_FINAL_SATELIT_{menit}M.png")
        try:
            plt.savefig(file_output, dpi=120, facecolor="#0e1117", bbox_inches="tight")
            frame_prediksi.append(file_output)
        except Exception:
            pass
        finally:
            plt.close(fig)

    frames_valid = [f for f in frame_prediksi if os.path.exists(f)]
    
    if len(frames_valid) > 1:
        try:
            images = [Image.open(f).convert("RGB") for f in frames_valid]
            output_gif = os.path.join(DIR_SATELIT, "NOWCAST_SATELIT_ANIMASI.gif")
            durations = [700] * (len(images) - 1) + [2000]
            images[0].save(output_gif, save_all=True, append_images=images[1:], duration=durations, loop=0, optimize=True)
            print(f"Animasi Satelit Selesai: {output_gif}")
        except Exception as e:
            print(f"Gagal merajut GIF: {e}")

if __name__ == "__main__":
    proses_nowcasting_satelit_npz()
