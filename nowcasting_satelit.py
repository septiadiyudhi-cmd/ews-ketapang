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
    
    # 1. Cari file .npz terbaru
    pola_pencarian = os.path.join(DIR_CACHE, "H09_B13_*.npz")
    daftar_file = sorted(glob.glob(pola_pencarian))
    
    if len(daftar_file) < 2:
        print("File data mentah .npz kurang dari 2. Nowcasting dibatalkan.")
        return
        
    file_sebelumnya = daftar_file[-2]
    file_terbaru = daftar_file[-1]
    
    print(f"Data T-1: {os.path.basename(file_sebelumnya)}")
    print(f"Data T-0: {os.path.basename(file_terbaru)}")

    # 2. Muat data mentah
    try:
        npz_prev = np.load(file_sebelumnya)
        npz_curr = np.load(file_terbaru)
        data_prev = npz_prev['data']
        data_curr = npz_curr['data']
        lons = npz_curr['lons']
        lats = npz_curr['lats']
    except Exception as e:
        print(f"Gagal memuat data .npz: {e}")
        return

    # 3. Normalisasi data suhu (-80 sampai 40 C) ke format 8-bit (0-255) untuk mesin OpenCV
    def skala_ke_8bit(data_suhu):
        data_clip = np.clip(data_suhu, -80, 40)
        # Balik: awan dingin (-80) jadi terang (255), daratan hangat (40) jadi gelap (0)
        data_8bit = ((40 - data_clip) / 120 * 255).astype(np.uint8)
        return data_8bit

    gray_prev = skala_ke_8bit(data_prev)
    gray_curr = skala_ke_8bit(data_curr)

    # 4. Hitung Optical Flow (Pelacakan Pergerakan Awan)
    flow = cv2.calcOpticalFlowFarneback(gray_prev, gray_curr, None, 
                                        pyr_scale=0.5, levels=3, winsize=15, 
                                        iterations=3, poly_n=5, poly_sigma=1.2, flags=0)

    # Ambil waktu valid dari nama file T-0 (Format H09_B13_Indonesia_YYYYMMDDHHMM.npz)
    nama_file = os.path.basename(file_terbaru)
    waktu_str = nama_file.split("_")[-1].replace(".npz", "")
    try:
        waktu_awal = datetime.strptime(waktu_str, "%Y%m%d%H%M")
    except Exception:
        waktu_awal = datetime.utcnow()

    frame_prediksi = []
    
    # 5. Ekstrapolasi dan Plotting dengan Cartopy
    for step in range(1, 7):
        menit = step * 10
        waktu_berlaku = waktu_awal + timedelta(minutes=menit)
        teks_waktu = waktu_berlaku.strftime("%Y-%m-%d %H:%M UTC")
        
        # Geser MATRIKS SUHU MENTAH (Bukan gambarnya)
        h, w = data_curr.shape
        map_x, map_y = np.meshgrid(np.arange(w), np.arange(h))
        map_x = map_x - (flow[..., 0] * step)
        map_y = map_y - (flow[..., 1] * step)
        
        # Warp data mentah (presisi suhu desimal tetap terjaga)
        data_pred = cv2.remap(data_curr.astype(np.float32), map_x.astype(np.float32), map_y.astype(np.float32), 
                              interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        
        # --- MULAI MENGGAMBAR PETA (CARTOPY) ---
        fig = plt.figure(figsize=(10, 6), dpi=150, facecolor="#0e1117")
        ax = plt.axes(projection=ccrs.PlateCarree())
        ax.set_facecolor("#0e1117")
        
        # Batas peta (Fokus Jawa Timur & Bali - Ketapang Gilimanuk)
        ax.set_extent([112.0, 116.0, -9.5, -6.5], crs=ccrs.PlateCarree())
        
        # Fitur peta statis (Garis pantai tidak akan melar/bergerak)
        ax.add_feature(cfeature.COASTLINE.with_scale('10m'), edgecolor="#ffffff", linewidth=1.0, zorder=5)
        ax.add_feature(cfeature.BORDERS.with_scale('10m'), edgecolor="#aaaaaa", linewidth=0.8, linestyle='--', zorder=5)
        
        # Sembunyikan suhu daratan/laut yang hangat (misal > 5 derajat celcius) agar transparan
        data_mask = np.ma.masked_greater(data_pred, 5.0)
        
        # Plotting gumpalan awan
        mesh = ax.pcolormesh(lons, lats, data_mask, transform=ccrs.PlateCarree(),
                             cmap='nipy_spectral_r', vmin=-80, vmax=20, zorder=2, shading='auto')
        
        # Titik Lokasi EWS Penyeberangan
        ax.plot(114.39, -8.14, marker='*', color='yellow', markersize=12, transform=ccrs.PlateCarree(), zorder=10)
        ax.text(114.45, -8.14, "Ketapang", color="white", transform=ccrs.PlateCarree(), zorder=10, fontsize=10, fontweight='bold')
        
        # Judul dinamis dengan waktu valid
        ax.set_title(f"Prediksi Satelit Himawari-9 (Suhu Puncak Awan)\nBerlaku: {teks_waktu}", color="#33cc66", fontweight="bold", pad=15)
        
        # Legenda Colorbar
        cbar = plt.colorbar(mesh, ax=ax, orientation='vertical', pad=0.02, shrink=0.8)
        cbar.set_label("Suhu (°C)", color="white")
        cbar.ax.tick_params(colors="white")
        
        # Simpan Frame
        file_output = os.path.join(DIR_SATELIT, f"NOWCAST_FINAL_SATELIT_{menit}M.png")
        try:
            plt.savefig(file_output, dpi=150, facecolor="#0e1117", bbox_inches="tight")
            frame_prediksi.append(file_output)
            print(f"Tersimpan: {file_output}")
        except Exception as e:
            print(f"Peringatan: Gagal menyimpan gambar prediksi ({e})")
        finally:
            plt.close(fig)

    # 6. Rajut GIF
    print("Merajut GIF Nowcasting Satelit...")
    # Cari gambar T-0 (HIMAWARI_B13_TERBARU.png) untuk titik awal
    gambar_t0 = os.path.join(DIR_SATELIT, "HIMAWARI_B13_TERBARU.png")
    
    frames_valid = []
    if os.path.exists(gambar_t0):
        frames_valid.append(gambar_t0)
    
    frames_valid.extend([f for f in frame_prediksi if os.path.exists(f)])
    
    if len(frames_valid) > 1:
        try:
            images = [Image.open(f).convert("RGB") for f in frames_valid]
            output_gif = os.path.join(DIR_SATELIT, "NOWCAST_SATELIT_ANIMASI.gif")
            durations = [700] * (len(images) - 1) + [2000]
            images[0].save(output_gif, save_all=True, append_images=images[1:], duration=durations, loop=0, optimize=True)
            print(f"[OK] Animasi Satelit Selesai: {output_gif}")
        except Exception as e:
            print(f"[GAGAL] Gagal merajut GIF: {e}")

if __name__ == "__main__":
    proses_nowcasting_satelit_npz()
