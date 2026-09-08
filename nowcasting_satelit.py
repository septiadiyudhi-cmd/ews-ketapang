# -*- coding: utf-8 -*-
"""
Created on Tue Sep  8 23:53:04 2026

@author: bmkg bwi
"""

# -*- coding: utf-8 -*-
"""
NOWCASTING SATELIT HIMAWARI-9 (OPENCV)
Memprediksi pergerakan suhu puncak awan hingga 60 menit ke depan
"""

import cv2
import numpy as np
import glob
import os
from PIL import Image

DIR_SATELIT = "./Satelit"

def proses_nowcasting_satelit():
    print("\n=== Memulai Nowcasting Satelit Himawari-9 ===")
    
    # 1. Kumpulkan histori gambar observasi satelit
    semua_png = glob.glob(os.path.join(DIR_SATELIT, "*.png"))
    
    # Saring agar hanya mengambil gambar histori satelit asli
    daftar_file = sorted([
        p for p in semua_png 
        if not os.path.basename(p).startswith("RADAR_") 
        and not os.path.basename(p).startswith("MAP_") 
        and "PREDIKSI" not in p 
        and "NOWCAST" not in p
        and "TERBARU" not in p
    ])
    
    if len(daftar_file) < 2:
        print("File satelit kurang dari 2. Nowcasting dibatalkan.")
        return
        
    file_sebelumnya = daftar_file[-2]
    file_terbaru = daftar_file[-1]
    
    print(f"Gambar 1 (T-1): {os.path.basename(file_sebelumnya)}")
    print(f"Gambar 2 (T-0): {os.path.basename(file_terbaru)}")

    # 2. Proses Optical Flow (Farneback)
    img_prev = cv2.imread(file_sebelumnya, cv2.IMREAD_UNCHANGED)
    img_curr = cv2.imread(file_terbaru, cv2.IMREAD_UNCHANGED)

    gray_prev = cv2.cvtColor(img_prev, cv2.COLOR_BGR2GRAY)
    gray_curr = cv2.cvtColor(img_curr, cv2.COLOR_BGR2GRAY)

    flow = cv2.calcOpticalFlowFarneback(gray_prev, gray_curr, None, 
                                        pyr_scale=0.5, levels=3, winsize=15, 
                                        iterations=3, poly_n=5, poly_sigma=1.2, flags=0)

    # 3. Fungsi Ekstrapolasi Piksel
    def geser_gambar(gambar, vektor_flow, skala_waktu):
        h, w = gambar.shape[:2]
        map_x, map_y = np.meshgrid(np.arange(w), np.arange(h))
        map_x = map_x - (vektor_flow[..., 0] * skala_waktu)
        map_y = map_y - (vektor_flow[..., 1] * skala_waktu)
        gambar_masa_depan = cv2.remap(gambar, map_x.astype(np.float32), map_y.astype(np.float32), 
                                      interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        return gambar_masa_depan

    # 4. Buat Prediksi 10 hingga 60 Menit
    frame_prediksi = []
    nama_dasar = os.path.basename(file_terbaru).replace(".png", "")
    
    for step in range(1, 7):
        menit = step * 10
        img_pred = geser_gambar(img_curr, flow, skala_waktu=step)
        
        # Tambahkan teks penanda "Waktu Berlaku" di pojok gambar prediksi
        teks = f"PREDIKSI +{menit} MENIT"
        cv2.putText(img_pred, teks, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2, cv2.LINE_AA)
        
        file_pred = os.path.join(DIR_SATELIT, f"NOWCAST_SATELIT_{menit}M.png")
        cv2.imwrite(file_pred, img_pred)
        frame_prediksi.append(file_pred)
        print(f"Tersimpan: {file_pred}")

    # 5. Rajut Menjadi Animasi GIF
    print("Merajut GIF Nowcasting Satelit...")
    frames_valid = [file_terbaru] + [f for f in frame_prediksi if os.path.exists(f)]
    
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
    proses_nowcasting_satelit()