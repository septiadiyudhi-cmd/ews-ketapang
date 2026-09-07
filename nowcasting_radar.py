# -*- coding: utf-8 -*-
"""
Created on Mon Sep  7 20:28:43 2026

@author: Asus
"""

# -*- coding: utf-8 -*-
"""
NOWCASTING RADAR DENGAN OPTICAL FLOW (OPENCV)
Memprediksi pergerakan gema radar 10, 20, dan 30 menit ke depan
"""

import cv2
import numpy as np
import glob
import os
import sys

DIR_SATELIT = "./Satelit"

def prediksi_pergerakan_radar(radar_nama):
    print(f"\n=== Memulai Nowcasting Radar {radar_nama} ===")
    
    # 1. Cari semua file PNG radar, urutkan dari yang terlama ke terbaru
    pola_pencarian = os.path.join(DIR_SATELIT, f"RADAR_{radar_nama.upper()}_*.png")
    daftar_file = sorted(glob.glob(pola_pencarian))
    
    # Butuh minimal 2 gambar untuk melihat arah pergerakan
    if len(daftar_file) < 2:
        print(f"File radar {radar_nama} kurang dari 2. Nowcasting dibatalkan.")
        return
        
    file_sebelumnya = daftar_file[-2]
    file_terbaru = daftar_file[-1]
    
    print(f"Gambar 1 (T-1): {os.path.basename(file_sebelumnya)}")
    print(f"Gambar 2 (T-0): {os.path.basename(file_terbaru)}")

    # 2. Baca gambar (Gunakan IMREAD_UNCHANGED agar background transparan/Alpha Channel tidak hilang)
    img_prev = cv2.imread(file_sebelumnya, cv2.IMREAD_UNCHANGED)
    img_curr = cv2.imread(file_terbaru, cv2.IMREAD_UNCHANGED)

    # 3. Ubah gambar ke mode Grayscale (Hitam Putih) khusus untuk mesin Optical Flow
    gray_prev = cv2.cvtColor(img_prev, cv2.COLOR_BGRA2GRAY)
    gray_curr = cv2.cvtColor(img_curr, cv2.COLOR_BGRA2GRAY)

    # 4. Hitung Optical Flow (Farneback Algorithm)
    # Mesin akan mencari tahu piksel di gray_prev bergeser ke mana di gray_curr
    flow = cv2.calcOpticalFlowFarneback(gray_prev, gray_curr, None, 
                                        pyr_scale=0.5, levels=3, winsize=15, 
                                        iterations=3, poly_n=5, poly_sigma=1.2, flags=0)

    # 5. Fungsi untuk mendorong gambar ke masa depan (Warping)
    def geser_gambar(gambar, vektor_flow, skala_waktu):
        h, w = gambar.shape[:2]
        
        # Buat peta koordinat (Grid) baru
        map_x, map_y = np.meshgrid(np.arange(w), np.arange(h))
        
        # Tambahkan vektor pergerakan ke grid (dikalikan skala waktu)
        # Jika step=1 (10 menit), jika step=2 (20 menit)
        map_x = map_x - (vektor_flow[..., 0] * skala_waktu)
        map_y = map_y - (vektor_flow[..., 1] * skala_waktu)
        
        # Petakan ulang (geser) piksel asli ke koordinat baru
        gambar_masa_depan = cv2.remap(gambar, map_x.astype(np.float32), map_y.astype(np.float32), 
                                      interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_TRANSPARENT)
        return gambar_masa_depan

    # 6. Buat Prediksi (Asumsi jarak file 1 dan 2 adalah 10 menit)
    nama_dasar = os.path.basename(file_terbaru).replace(".png", "")
    
    # Prediksi +10 Menit (Step = 1)
    img_pred_10 = geser_gambar(img_curr, flow, skala_waktu=1)
    file_10m = os.path.join(DIR_SATELIT, f"{nama_dasar}_PREDIKSI_10M.png")
    cv2.imwrite(file_10m, img_pred_10)
    
    # Prediksi +20 Menit (Step = 2)
    img_pred_20 = geser_gambar(img_curr, flow, skala_waktu=2)
    file_20m = os.path.join(DIR_SATELIT, f"{nama_dasar}_PREDIKSI_20M.png")
    cv2.imwrite(file_20m, img_pred_20)
    
    # Prediksi +30 Menit (Step = 3)
    img_pred_30 = geser_gambar(img_curr, flow, skala_waktu=3)
    file_30m = os.path.join(DIR_SATELIT, f"{nama_dasar}_PREDIKSI_30M.png")
    cv2.imwrite(file_30m, img_pred_30)
    
    print(f"Berhasil membuat prediksi nowcasting 10, 20, 30 menit ke depan untuk {radar_nama}!")

if __name__ == "__main__":
    prediksi_pergerakan_radar("DENPASAR")
    prediksi_pergerakan_radar("SURABAYA")