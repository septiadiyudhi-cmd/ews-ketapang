# -*- coding: utf-8 -*-
"""
AUTO DOWNLOAD + PROCESS + LOG STATUS CB (Satelit + Radar)
HIMAWARI-9 B13 & SIDARMA CMAX - EWS Penyeberangan Ketapang-Gilimanuk

Versi Multi-Sensor (Isolasi Penuh - GITHUB ACTIONS VERSION):
- Download FTP Satelit (Dengan Passive Mode)
- Download API Radar Cuaca
- Proses .nc (Satelit) & .png (Radar) di proses terpisah (baca_data.py)
- Plot gambar .npz (plot_dari_npz.py)
- Download Data Angin AWS Center (ambil_angin_aws.py)
"""

from ftplib import FTP
from datetime import datetime, timedelta
import os
import re
import sys
import subprocess

# =============================================================
# KONFIGURASI FTP SATELIT
# =============================================================
print("Mulai mencoba koneksi ke FTP BMKG...")
# Alamat IP sekarang disembunyikan menggunakan GitHub Secrets (Environment Variable)
FTP_HOST = os.environ.get("SERVER_IP")
FTP_USER = os.environ.get("FTP_USER")
FTP_PASS = os.environ.get("FTP_PASS")

REMOTE_BASE_DIR = "/himawari6/netcdf/Indonesia"

LOCAL_DIR = "./Satelit"
CACHE_DIR = os.path.join(LOCAL_DIR, "_cache")

JUMLAH_FILE = 5
EKSTENSI = ".nc"
BAND = "B13"

POLA_TIMESTAMP = re.compile(r"(\d{12})\.nc$", re.IGNORECASE)

# =============================================================
# KONFIGURASI TIMEOUT
# =============================================================
TIMEOUT_PROSES_SATU_LANGKAH = 180  # detik
TIMEOUT_AMBIL_ANGIN = 30  # detik

# =============================================================
# LOKASI SCRIPT PENDUKUNG (harus ada di folder yang sama)
# =============================================================
FOLDER_SCRIPT_INI = os.path.dirname(os.path.abspath(__file__))
SCRIPT_BACA_DATA = os.path.join(FOLDER_SCRIPT_INI, "baca_data.py")
SCRIPT_PLOT = os.path.join(FOLDER_SCRIPT_INI, "plot_dari_npz.py")
SCRIPT_AMBIL_ANGIN = os.path.join(FOLDER_SCRIPT_INI, "ambil_angin_aws.py")
SCRIPT_UNDUH_RADAR = os.path.join(FOLDER_SCRIPT_INI, "unduh_radar_api.py")
SCRIPT_PLOT_RADAR = os.path.join(FOLDER_SCRIPT_INI, "plot_radar_saja.py") 

PYTHON_EXE = sys.executable

# =============================================================
# PERSIAPAN FOLDER
# =============================================================
os.makedirs(LOCAL_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)

# =============================================================
# FUNGSI TIMESTAMP & CLEANUP
# =============================================================
def ambil_timestamp(nama_file):
    match = POLA_TIMESTAMP.search(nama_file)
    if not match:
        return datetime.min
    try:
        return datetime.strptime(match.group(1), "%Y%m%d%H%M")
    except ValueError:
        return datetime.min

def cari_remote_dir(ftp):
    waktu_utc = datetime.utcnow()
    kandidat_tanggal = [waktu_utc, waktu_utc - timedelta(days=1)]

    for tanggal in kandidat_tanggal:
        remote_dir = (
            f"{REMOTE_BASE_DIR}/{tanggal.strftime('%Y')}/"
            f"{tanggal.strftime('%m')}/{tanggal.strftime('%d')}"
        )
        try:
            ftp.cwd(remote_dir)
            print(f"[OK] Folder ditemukan: {remote_dir}")
            return remote_dir
        except Exception:
            print(f"[X] Folder tidak ditemukan: {remote_dir}")
    return None

def bersihkan_local_dir():
    # 1. Hapus NetCDF dan PNG Satelit (Abaikan Radar)
    for nama_file in os.listdir(LOCAL_DIR):
        if nama_file.lower().endswith(".nc"):
            try:
                os.remove(os.path.join(LOCAL_DIR, nama_file))
            except Exception: pass
        elif nama_file.lower().endswith(".png"):
            # Jika itu file radar, lewati (jangan dihapus)
            if not nama_file.startswith("RADAR_") and not nama_file.startswith("MAP_"):
                try:
                    os.remove(os.path.join(LOCAL_DIR, nama_file))
                except Exception: pass

    # 2. Hapus Cache Data
    if os.path.isdir(CACHE_DIR):
        for nama_file in os.listdir(CACHE_DIR):
            if nama_file.lower().endswith(".npz"):
                try:
                    os.remove(os.path.join(CACHE_DIR, nama_file))
                except Exception: pass

    # 3. MANAJEMEN ARSIP RADAR (Cegah hardisk penuh)
    # Kita hanya menyimpan 10 file radar/map terbaru untuk setiap jenis
    jenis_radar = ["RADAR_SURABAYA_", "RADAR_DENPASAR_", "MAP_RADAR_SURABAYA_", "MAP_RADAR_DENPASAR_"]
    for prefix in jenis_radar:
        daftar_file = sorted([f for f in os.listdir(LOCAL_DIR) if f.startswith(prefix) and f.lower().endswith(".png")])
        if len(daftar_file) > 5:
            for file_usang in daftar_file[:-5]: # Hapus sisanya, tinggalkan 10 terbaru
                try:
                    os.remove(os.path.join(LOCAL_DIR, file_usang))
                except Exception: pass

    print("File lama dibersihkan. Histori radar dipertahankan (maks 10 file).")

# =============================================================
# DOWNLOAD FTP (SATELIT)
# =============================================================
def auto_ftp_download():
    print("\n=== KONEKSI FTP (SATELIT) ===")
    ftp = FTP(FTP_HOST, timeout=30)
    print("Koneksi host berhasil, mencari daftar file...")
    ftp.login(FTP_USER, FTP_PASS)
    ftp.set_pasv(True)

    remote_dir = cari_remote_dir(ftp)
    if remote_dir is None:
        print("Folder FTP hari ini/kemarin tidak ditemukan.")
        try: ftp.quit()
        except: pass
        return []

    semua_file = ftp.nlst()
    file_nc = [f for f in semua_file if f.lower().endswith(EKSTENSI) and f"_{BAND}_" in f]

    if not file_nc:
        print(f"Tidak ada file {BAND} di {remote_dir}")
        try: ftp.quit()
        except: pass
        return []

    file_terbaru = sorted(file_nc, key=ambil_timestamp)[-JUMLAH_FILE:]

    print(f"Akan download {len(file_terbaru)} file:")
    for nama in file_terbaru:
        print(" -", nama)

    bersihkan_local_dir()
    
    # Tutup koneksi pencarian agar tidak idle dan diputus sepihak
    try: ftp.quit()
    except: pass

    hasil_download = []
    # UNDUH MENGGUNAKAN cURL BUKAN Python ftplib
    for nama_file in file_terbaru:
        local_path = os.path.join(LOCAL_DIR, nama_file)
        print(f"\nMengunduh {nama_file} menggunakan cURL...")
        
        # URL lengkap menuju file FTP
        url_ftp = f"ftp://{FTP_HOST}{remote_dir}/{nama_file}"
        
        try:
            # Panggil cURL via terminal dengan batas waktu maksimal 10 menit
            subprocess.run([
                "curl", "-u", f"{FTP_USER}:{FTP_PASS}",
                "--ftp-pasv",
                "--connect-timeout", "30",
                "--max-time", "900",
                url_ftp, "-o", local_path
            ], check=True)
            
            hasil_download.append(local_path)
            print(f"[SUKSES] Selesai unduh: {nama_file}")
        except subprocess.CalledProcessError as e:
            print(f"[GAGAL] cURL gagal mengunduh {nama_file}: {e}")

    return hasil_download

# =============================================================
# SUBPROCESS: RADAR, BACA DATA, PLOT, ANGIN
# =============================================================
def ambil_data_radar_api():
    """Memanggil skrip unduh_radar_api.py untuk mengambil gambar radar terbaru."""
    if not os.path.exists(SCRIPT_UNDUH_RADAR):
        print(f"[RADAR] Dilewati -- {SCRIPT_UNDUH_RADAR} tidak ditemukan.")
        return
    
    try:
        subprocess.run(
            [PYTHON_EXE, SCRIPT_UNDUH_RADAR],
            timeout=60,
            capture_output=False
        )
    except subprocess.TimeoutExpired:
        print("[RADAR] Timeout (>60s) saat mengunduh radar. Dilewati.")
    except Exception as e:
        print(f"[RADAR] Terjadi error: {e}")

def jalankan_subprocess(argumen, label):
    try:
        hasil = subprocess.run(
            [PYTHON_EXE] + argumen,
            timeout=TIMEOUT_PROSES_SATU_LANGKAH,
            capture_output=True,
            text=True,
        )
    except subprocess.TimeoutExpired:
        print(f"[GAGAL] {label}: timeout (>{TIMEOUT_PROSES_SATU_LANGKAH}s). Dilewati.")
        return False, ""

    if hasil.stdout:
        print(hasil.stdout.strip())

    if hasil.returncode == 0:
        return True, hasil.stdout

    print(f"[GAGAL] {label}: proses berhenti dengan kode {hasil.returncode}.")
    if hasil.stderr:
        print("Pesan error:", hasil.stderr.strip())
    else:
        print("(Tidak ada pesan error -- kemungkinan crash native di library.)")
    return False, hasil.stdout

def proses_satu_file(nc_file):
    nama_file = os.path.basename(nc_file)
    print(f"\n--> Memproses: {nama_file}")

    berhasil, _ = jalankan_subprocess([SCRIPT_BACA_DATA, nc_file], "baca_data.py")
    if not berhasil:
        return False

    npz_path = os.path.join(CACHE_DIR, os.path.splitext(nama_file)[0] + ".npz")
    if not os.path.exists(npz_path):
        print(f"[GAGAL] File .npz tidak ditemukan setelah baca_data.py: {npz_path}")
        return False

    berhasil_plot, _ = jalankan_subprocess([SCRIPT_PLOT, npz_path], "plot_dari_npz.py")
    return berhasil_plot

def proses_semua_file():
    file_nc = [
        os.path.join(LOCAL_DIR, f) for f in os.listdir(LOCAL_DIR)
        if f.lower().endswith(".nc") and f"_{BAND}_" in f
    ]
    file_nc = sorted(file_nc, key=lambda x: ambil_timestamp(os.path.basename(x)))

    if not file_nc:
        print("Tidak ada file NetCDF.")
        return

    berhasil = gagal = 0
    for nc_file in file_nc:
        if proses_satu_file(nc_file):
            berhasil += 1
        else:
            gagal += 1

    print(f"\nRingkasan: {berhasil} berhasil (data+gambar), {gagal} gagal dari {len(file_nc)} file.")

def ambil_data_angin_aws():
    if not os.path.exists(SCRIPT_AMBIL_ANGIN):
        print(f"[ANGIN] Dilewati -- {SCRIPT_AMBIL_ANGIN} tidak ditemukan.")
        return
    try:
        hasil = subprocess.run(
            [PYTHON_EXE, SCRIPT_AMBIL_ANGIN],
            timeout=TIMEOUT_AMBIL_ANGIN,
            capture_output=True,
            text=True,
        )
        if hasil.stdout:
            print(hasil.stdout.strip())
        if hasil.returncode != 0:
            print(f"[ANGIN] Gagal (kode {hasil.returncode}).")
            if hasil.stderr:
                print("Pesan error:", hasil.stderr.strip())
    except subprocess.TimeoutExpired:
        print(f"[ANGIN] Timeout (>{TIMEOUT_AMBIL_ANGIN}s) saat mengambil data AWS. Dilewati.")
    except Exception as e:
        print(f"[ANGIN] Terjadi error: {e}")
        
# =============================================================
# BUAT GIF ANIMASI (SATELIT & RADAR)
# =============================================================
NAMA_FILE_GIF = "HIMAWARI_B13_ANIMASI.gif"
LEBAR_GIF_PIKSEL = 700
DURASI_PER_FRAME_MS = 700
JEDA_FRAME_TERAKHIR_MS = 2000

def buat_gif_dari_daftar(daftar_file, output_gif, background_hitam=False):
    try:
        from PIL import Image as PILImage
    except ImportError:
        print("[GIF] Pillow (PIL) tidak tersedia.")
        return

    if len(daftar_file) < 2: return

    frame_list = []
    for path_png in daftar_file:
        try:
            with PILImage.open(path_png) as im:
                if background_hitam:
                    im = im.convert("RGBA")
                    bg = PILImage.new("RGB", im.size, (15, 15, 15)) 
                    bg.paste(im, mask=im.split()[3] if len(im.split())==4 else None)
                    gambar_final = bg
                else:
                    gambar_final = im.convert("RGB")

                rasio = LEBAR_GIF_PIKSEL / gambar_final.width
                ukuran_baru = (LEBAR_GIF_PIKSEL, int(gambar_final.height * rasio))
                frame_list.append(gambar_final.resize(ukuran_baru, PILImage.LANCZOS))
        except Exception as e:
            print(f"[GIF] Gagal membaca {os.path.basename(path_png)}: {e}")

    if len(frame_list) < 2: return
    durasi_tiap_frame = [DURASI_PER_FRAME_MS] * (len(frame_list) - 1) + [JEDA_FRAME_TERAKHIR_MS]
    
    try:
        frame_list[0].save(
            output_gif, save_all=True, append_images=frame_list[1:],
            duration=durasi_tiap_frame, loop=0, optimize=True,
        )
        print(f"[GIF] Animasi dibuat: {os.path.basename(output_gif)} ({len(frame_list)} frame)")
    except Exception as e:
        print(f"[GIF] Gagal menyimpan animasi: {e}")

def buat_semua_gif():
    # 1. Animasi Satelit
    daftar_satelit = [
        os.path.join(LOCAL_DIR, f) for f in os.listdir(LOCAL_DIR)
        if f.lower().endswith(".png") and f != "HIMAWARI_B13_TERBARU.png" and not f.startswith("RADAR_") and not f.startswith("MAP_RADAR_")
    ]
    daftar_satelit = sorted(daftar_satelit, key=lambda p: ambil_timestamp(os.path.basename(p)))
    buat_gif_dari_daftar(daftar_satelit, os.path.join(LOCAL_DIR, NAMA_FILE_GIF), background_hitam=False)

    # 2. Animasi Radar Surabaya & Denpasar (Diberi Peta Dasar)
    for radar in ["SURABAYA", "DENPASAR"]:
        raw_radar = [
            os.path.join(LOCAL_DIR, f) for f in os.listdir(LOCAL_DIR)
            if f.startswith(f"RADAR_{radar}_") and f.lower().endswith(".png")
        ]
        raw_radar = sorted(raw_radar)[-5:] # Ambil 5 frame terbaru
        
        map_radar_frames = []
        for raw_file in raw_radar:
            nama_file_map = "MAP_" + os.path.basename(raw_file)
            path_map = os.path.join(LOCAL_DIR, nama_file_map)
            
            # Buat petanya jika belum ada di cache
            if not os.path.exists(path_map):
                try:
                    subprocess.run([PYTHON_EXE, SCRIPT_PLOT_RADAR, radar, raw_file, path_map], timeout=30)
                except Exception as e:
                    print(f"[RADAR MAP] Gagal menggambar {nama_file_map}: {e}")
            
            if os.path.exists(path_map):
                map_radar_frames.append(path_map)

        if map_radar_frames:
            buat_gif_dari_daftar(map_radar_frames, os.path.join(LOCAL_DIR, f"RADAR_{radar}_ANIMASI.gif"), background_hitam=False)

# =============================================================
# MAIN LOGIC (Satu Kali Eksekusi untuk GitHub Actions)
# =============================================================
if __name__ == "__main__":
    print("=== AUTO HIMAWARI B13 + RADAR SIDARMA + LOG EWS (CLOUD VERSION) ===")

    try:
        # 1. Download Satelit
        hasil_download = auto_ftp_download()
        
        # 2. Download Radar
        ambil_data_radar_api()
        
        # 3. Eksekusi Proses (Hanya jika ada satelit)
        if hasil_download:
            proses_semua_file()
            buat_semua_gif()
        else:
            print("Tidak ada file satelit baru.")

        # 4. Ambil Angin
        print("\n--- Ambil data angin AWS Center ---")
        ambil_data_angin_aws()
        
        print("\n=== SEMUA PROSES SELESAI DENGAN SUKSES ===")
        
    except Exception as e:
        print(f"Terjadi error kritis pada eksekusi utama: {e}")
