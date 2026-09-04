# -*- coding: utf-8 -*-
"""
DASHBOARD EARLY WARNING SYSTEM - DETEKSI CUMULONIMBUS
Penyeberangan Ketapang - Gilimanuk (Satelit + Radar)
"""

import os
import time

# Paksa server menggunakan zona waktu WIB
os.environ['TZ'] = 'Asia/Jakarta'
try:
    time.tzset()
except AttributeError:
    pass

import glob
import json
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from streamlit_autorefresh import st_autorefresh

from buat_pdf_peringatan import buat_pdf_peringatan

# =============================================================
# KONFIGURASI
# =============================================================
LOCAL_DIR = "./Satelit"

LOG_CSV = os.path.join(LOCAL_DIR, "log_status_cb.csv")
PNG_TERBARU = os.path.join(LOCAL_DIR, "HIMAWARI_B13_TERBARU.png")
GIF_ANIMASI = os.path.join(LOCAL_DIR, "HIMAWARI_B13_ANIMASI.gif")
GIF_RADAR_SBY = os.path.join(LOCAL_DIR, "RADAR_SURABAYA_ANIMASI.gif")
GIF_RADAR_DPS = os.path.join(LOCAL_DIR, "RADAR_DENPASAR_ANIMASI.gif")

AMBANG_SEL_SIGNIFIKAN_C = -34.0
LUAS_MIN_SEL_KM2 = 10.0
RADIUS_SIAGA_KM = 10
RADIUS_WASPADA_KM = 20

WARNA_STATUS = {
    "AMAN": "#33cc66",
    "WASPADA": "#ffcc00",
    "SIAGA": "#ff3333",
}

LOKASI_EWS = "Penyeberangan Ketapang - Gilimanuk"
PERINGATAN_CSV = os.path.join(LOCAL_DIR, "peringatan_log.csv")
MAKS_BARIS_PERINGATAN = 200
KOLOM_PERINGATAN = [
    "lokasi", "forecaster", "initial_time", "valid_until",
    "narasi", "dipublikasikan_pada",
]
PDF_DIR = os.path.join(LOCAL_DIR, "peringatan_pdf")

# =============================================================
# SETUP HALAMAN
# =============================================================
st.set_page_config(
    page_title="EWS Multi-Sensor - Ketapang-Gilimanuk",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# REFRESH OTOMATIS TIAP 10 MENIT
st_autorefresh(interval=10 * 60 * 1000, key="ews_refresh")

# Inisialisasi Session State
if "pdf_terakhir" not in st.session_state:
    st.session_state["pdf_terakhir"] = None
if "pesan_notif" not in st.session_state:
    st.session_state["pesan_notif"] = None

st.markdown(
    """
    <style>
    .stApp { background-color: #0e1117; }
    </style>
    """,
    unsafe_allow_html=True,
)

# =============================================================
# FUNGSI BANTUAN
# =============================================================
@st.cache_data(ttl=60)
def muat_log():
    if not os.path.exists(LOG_CSV):
        return pd.DataFrame()
    df = pd.read_csv(LOG_CSV)
    if df.empty:
        return df
    
    kolom_wajib = [
        "jumlah_sel_signifikan", "luas_sel_terbesar_km2", "jarak_terdekat_km",
        "initial_heading_deg", "initial_speed_kmh", "cell_lat", "cell_lon", "dbz_maks_radar"
    ]
    for kolom in kolom_wajib:
        if kolom not in df.columns:
            df[kolom] = pd.NA
            
    df["waktu_wib_dt"] = pd.to_datetime(df["waktu_wib"], errors="coerce")
    df = df.dropna(subset=["waktu_wib_dt"]).sort_values("waktu_wib_dt")
    return df

def daftar_png_histori():
    semua_png = glob.glob(os.path.join(LOCAL_DIR, "*.png"))
    hasil = [p for p in semua_png if os.path.basename(p) != "HIMAWARI_B13_TERBARU.png" and not os.path.basename(p).startswith("RADAR_") and not os.path.basename(p).startswith("MAP_")]
    return sorted(hasil)

def muat_peringatan():
    if not os.path.exists(PERINGATAN_CSV): return pd.DataFrame(columns=KOLOM_PERINGATAN)
    try: df = pd.read_csv(PERINGATAN_CSV)
    except Exception: return pd.DataFrame(columns=KOLOM_PERINGATAN)
    if df.empty: return df
    df["initial_time_dt"] = pd.to_datetime(df["initial_time"], errors="coerce")
    df["valid_until_dt"] = pd.to_datetime(df["valid_until"], errors="coerce")
    df["dipublikasikan_pada_dt"] = pd.to_datetime(df["dipublikasikan_pada"], errors="coerce")
    return df.sort_values("dipublikasikan_pada_dt")

def simpan_peringatan(baris_baru: dict):
    df_lama = muat_peringatan()
    df_lama = df_lama[KOLOM_PERINGATAN] if not df_lama.empty else pd.DataFrame(columns=KOLOM_PERINGATAN)
    df_gabung = pd.concat([df_lama, pd.DataFrame([baris_baru])], ignore_index=True).tail(MAKS_BARIS_PERINGATAN)
    df_gabung.to_csv(PERINGATAN_CSV, index=False)

# =============================================================
# MUAT DATA
# =============================================================
df_log = muat_log()

if df_log.empty:
    st.warning("Belum ada data log yang ditemukan. Pastikan proses background sedang berjalan.")
    st.stop()

baris_terbaru = df_log.iloc[-1]
status_terbaru = baris_terbaru["status"]
waktu_terbaru = baris_terbaru["waktu_wib"]
suhu_10km_terbaru = baris_terbaru["suhu_min_10km"]
suhu_20km_terbaru = baris_terbaru["suhu_min_20km"]
dbz_terbaru = baris_terbaru.get("dbz_maks_radar")

try:
    selisih_menit = (datetime.now() - pd.to_datetime(waktu_terbaru)).total_seconds() / 60
    data_basi = selisih_menit > 20
except Exception:
    data_basi = True

kategori_radar = "Belum Terdeteksi"
warna_radar = "gray"
if pd.notna(dbz_terbaru) and dbz_terbaru != "":
    val = float(dbz_terbaru)
    if val >= 40:
        kategori_radar, warna_radar = "Hujan Lebat (>40 dBZ)", "#ff3333"
    elif val >= 20:
        kategori_radar, warna_radar = "Hujan Sedang (20-40 dBZ)", "#ffcc00"
    elif val >= 5:
        kategori_radar, warna_radar = "Hujan Ringan (5-19 dBZ)", "#33cc66"

# =============================================================
# TAMPILAN DASHBOARD
# =============================================================
col_logo, col_judul = st.columns([1.5, 10])  # Jatah kolom logo diperlebar (dari 1 menjadi 1.5)
with col_logo: 
    if os.path.exists("logo_bmkg.png"):
        st.image("logo_bmkg.png", width=130) # Ukuran logo dibesarkan (misal dari 80 menjadi 130)
    else:
        st.markdown("### 🌊")
with col_judul:
    st.markdown("## EARLY WARNING SYSTEM - MULTI SENSOR (Satelit & Radar)")
    st.markdown("**Kantor Layanan Meteorologi Maritim Ketapang-Gilimanuk**")

st.divider()

col_status, col_suhu, col_radar = st.columns([2, 2, 3])
with col_status:
    warna = WARNA_STATUS.get(status_terbaru, "gray")
    st.markdown(
        f"""
        <div style="background-color:{warna}22; border:2px solid {warna}; border-radius:8px; padding:16px; text-align:center;">
            <div style="font-size:14px; color:#cccccc;">Status Saat Ini</div>
            <div style="font-size:32px; font-weight:bold; color:{warna};">{status_terbaru}</div>
            <div style="font-size:12px; color:#aaaaaa;">Pukul {waktu_terbaru} WIB</div>
        </div>
        """, unsafe_allow_html=True
    )

with col_suhu:
    st.metric("Suhu Min. (Radius 10 km)", f"{suhu_10km_terbaru} °C" if pd.notna(suhu_10km_terbaru) else "-")
    st.metric("Suhu Min. (Radius 20 km)", f"{suhu_20km_terbaru} °C" if pd.notna(suhu_20km_terbaru) else "-")

with col_radar:
    st.markdown(
        f"""
        <div style="background-color:{warna_radar}22; border:2px solid {warna_radar}; border-radius:8px; padding:16px;">
            <div style="font-size:14px; color:#cccccc;">Intensitas Radar Maksimum (Radius 20 km)</div>
            <div style="font-size:24px; font-weight:bold; color:{warna_radar}; margin-top:8px;">
                {dbz_terbaru if pd.notna(dbz_terbaru) and dbz_terbaru != "" else "-"} dBZ
            </div>
            <div style="font-size:16px; color:#ffffff;">{kategori_radar}</div>
        </div>
        """, unsafe_allow_html=True
    )

st.divider()

# =============================================================
# PERINGATAN RESMI AKTIF
# =============================================================
df_peringatan = muat_peringatan()
peringatan_aktif = None

if not df_peringatan.empty:
    sekarang_dt = pd.Timestamp(datetime.now())
    df_masih_berlaku = df_peringatan[df_peringatan["valid_until_dt"] >= sekarang_dt]
    if not df_masih_berlaku.empty:
        peringatan_aktif = df_masih_berlaku.iloc[-1]

st.markdown("#### 📢 Peringatan Resmi Aktif")

if peringatan_aktif is not None:
    st.markdown(
        f"""
        <div style="border:2px solid #ff9900; border-radius:8px; padding:16px; background-color:#ff990011;">
            <div style="font-size:13px; color:#aaaaaa;">Lokasi</div>
            <div style="font-size:18px; font-weight:bold; color:#fff8cf; margin-bottom:8px;">{peringatan_aktif['lokasi']}</div>
            <div style="display:flex; gap:32px; margin-bottom:8px;">
                <div><span style="color:#aaaaaa; font-size:12px;">Forecaster</span><br>{peringatan_aktif['forecaster']}</div>
                <div><span style="color:#aaaaaa; font-size:12px;">Initial time</span><br>{peringatan_aktif['initial_time']}</div>
                <div><span style="color:#aaaaaa; font-size:12px;">Valid until</span><br>{peringatan_aktif['valid_until']}</div>
            </div>
            <div style="color:#aaaaaa; font-size:12px;">Narasi</div>
            <div style="font-size:14px;">{peringatan_aktif['narasi']}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    st.info("Belum ada peringatan resmi yang aktif saat ini. Forecaster dapat membuat peringatan baru di bagian bawah halaman.")

st.divider()

# =============================================================
# CITRA & ANALISIS
# =============================================================
col_peta, col_kanan = st.columns([1, 1])

with col_peta:
    st.markdown("#### 🗺️ Citra Satelit Enhanced IR (Animasi)")
    if os.path.exists(GIF_ANIMASI):
        st.image(GIF_ANIMASI, width="stretch")
    elif os.path.exists(PNG_TERBARU):
        st.image(PNG_TERBARU, width="stretch")
    else:
        st.info("Belum ada citra satelit yang tersedia.")
        
    daftar_png = daftar_png_histori()
    if daftar_png:
        with st.expander("🔍 Lihat citra per-waktu (bukan animasi)"):
            nama_tampil = [os.path.basename(p) for p in daftar_png]
            pilihan = st.select_slider(
                "Pilih waktu citra:",
                options=nama_tampil,
                value=nama_tampil[-1],
            )
            path_terpilih = daftar_png[nama_tampil.index(pilihan)]
            st.image(path_terpilih, width="stretch")

with col_kanan:
    st.markdown("#### 📊 Analisis Sel Konvektif Gabungan")
    
    jumlah_sel = baris_terbaru.get("jumlah_sel_signifikan", "")
    luas_terbesar = baris_terbaru.get("luas_sel_terbesar_km2", "")
    jarak_terdekat = baris_terbaru.get("jarak_terdekat_km", "")
    heading = baris_terbaru.get("initial_heading_deg", "")
    speed = baris_terbaru.get("initial_speed_kmh", "")

    def _fmt(nilai, satuan): return "-" if pd.isna(nilai) or nilai == "" else f"{nilai} {satuan}"

    col_a1, col_a2 = st.columns(2)
    with col_a1:
        st.metric("Sel Signifikan (Satelit/Radar)", int(jumlah_sel) if pd.notna(jumlah_sel) and jumlah_sel != "" else 0)
        st.metric("Sel Terbesar", _fmt(luas_terbesar, "km²"))
        st.metric("Jarak Terdekat", _fmt(jarak_terdekat, "km"))
    with col_a2:
        st.metric("Arah Pergerakan", _fmt(heading, "°"))
        st.metric("Kecepatan Awal", _fmt(speed, "km/h"))

    st.markdown("#### 📈 Tren Suhu Puncak Awan (24 Jam Terakhir)")
    df_24jam = df_log[df_log["waktu_wib_dt"] >= (df_log["waktu_wib_dt"].max() - timedelta(hours=24))]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_24jam["waktu_wib_dt"], y=df_24jam["suhu_min_10km"], mode="lines+markers", name="Suhu Min. 10km", line=dict(color="#ff3333")))
    fig.add_trace(go.Scatter(x=df_24jam["waktu_wib_dt"], y=df_24jam["suhu_min_20km"], mode="lines+markers", name="Suhu Min. 20km", line=dict(color="#ffcc00")))
    fig.add_hline(y=AMBANG_SEL_SIGNIFIKAN_C, line_dash="dash", line_color="#ff9900", annotation_text="Ambang Satelit")
    fig.update_layout(template="plotly_dark", height=300, margin=dict(l=10, r=10, t=30, b=10))
    st.plotly_chart(fig, width="stretch")

st.divider()

# =============================================================
# PANEL ANIMASI RADAR MANDIRI
# =============================================================
st.markdown("#### 📡 Animasi Radar Cuaca Mandiri (CMAX)")

col_r1, col_r2 = st.columns(2)
with col_r1:
    st.markdown("**Radar Surabaya**")
    if os.path.exists(GIF_RADAR_SBY):
        st.image(GIF_RADAR_SBY, width="stretch")
    else:
        st.info("Animasi Radar Surabaya sedang disiapkan...")

with col_r2:
    st.markdown("**Radar Denpasar (Gilimanuk)**")
    if os.path.exists(GIF_RADAR_DPS):
        st.image(GIF_RADAR_DPS, width="stretch")
    else:
        st.info("Animasi Radar Denpasar sedang disiapkan...")

st.divider()

# =============================================================
# TABEL RIWAYAT
# =============================================================
st.markdown("#### 📋 Riwayat Status (Terbaru di Atas)")

df_tabel = df_log[[
        "waktu_wib", "suhu_min_10km", "suhu_min_20km", "dbz_maks_radar", "status",
        "jumlah_sel_signifikan", "luas_sel_terbesar_km2", "jarak_terdekat_km",
        "initial_heading_deg", "initial_speed_kmh", "file_sumber",
    ]] \
    .sort_values("waktu_wib", ascending=False) \
    .rename(columns={
        "waktu_wib": "Waktu (WIB)",
        "suhu_min_10km": "Suhu 10km (°C)",
        "suhu_min_20km": "Suhu 20km (°C)",
        "dbz_maks_radar": "Radar Maks (dBZ)",
        "status": "Status",
        "jumlah_sel_signifikan": "Sel Signifikan",
        "luas_sel_terbesar_km2": "Sel Terbesar (km²)",
        "jarak_terdekat_km": "Jarak Terdekat (km)",
        "initial_heading_deg": "Arah Pergerakan (°)",
        "initial_speed_kmh": "Kecepatan Awal (km/h)",
        "file_sumber": "File Sumber",
    })

st.dataframe(df_tabel, width="stretch", height=350)
st.caption(
    "Data diproses otomatis dari citra Himawari-9 kanal B13 tiap 10 menit. "
    f"Sel awan dengan suhu puncak ≤ {AMBANG_SEL_SIGNIFIKAN_C}°C dianggap signifikan."
)
st.divider()


# =============================================================
# FORMULIR: BUAT & PUBLIKASIKAN PERINGATAN
# =============================================================
st.markdown("### 📝 Early Warning System")
st.markdown(f"**Location : {LOKASI_EWS}**")

# TAMPILKAN NOTIFIKASI DAN TOMBOL DOWNLOAD PDF (Tepat di atas Form)
if st.session_state.get("pesan_notif"):
    if "gagal" in st.session_state["pesan_notif"].lower():
        st.error(st.session_state["pesan_notif"])
    else:
        st.success(st.session_state["pesan_notif"])
    st.session_state["pesan_notif"] = None # Reset agar tidak muncul terus

if st.session_state.get("pdf_terakhir") and os.path.exists(st.session_state["pdf_terakhir"]):
    with open(st.session_state["pdf_terakhir"], "rb") as f:
        pdf_bytes = f.read()
    st.download_button(
        label="📄 Download PDF Peringatan Terakhir",
        data=pdf_bytes,
        file_name=os.path.basename(st.session_state["pdf_terakhir"]),
        mime="application/pdf",
    )
    st.markdown("<br>", unsafe_allow_html=True)


# =============================================================
# DATA ANGIN AWS CENTER
# =============================================================
ANGIN_AWS_JSON = os.path.join(LOCAL_DIR, "angin_aws_terkini.json")
BATAS_BASI_ANGIN_MENIT = 20

def muat_data_angin_aws():
    if not os.path.exists(ANGIN_AWS_JSON): return None
    try:
        with open(ANGIN_AWS_JSON, "r", encoding="utf-8") as f: data = json.load(f)
    except Exception: return None
    if data.get("kecepatan_maks_knot") is None: return None
    try: waktu_ambil_dt = datetime.strptime(data["waktu_ambil"], "%Y-%m-%d %H:%M:%S")
    except (KeyError, ValueError): return None
    if (datetime.now() - waktu_ambil_dt).total_seconds() / 60 > BATAS_BASI_ANGIN_MENIT: return None 
    return data

data_angin_aws = muat_data_angin_aws()

TEMPLATE_DAMPAK = {
    "WASPADA": { "intensitas_hujan": "ringan hingga sedang", "sebut_petir": False, "kecepatan_angin_kt_default": 15, "tinggi_gelombang_m": 0.75, "jarak_pandang_km": None },
    "SIAGA": { "intensitas_hujan": "sedang hingga lebat", "sebut_petir": True, "kecepatan_angin_kt_default": 20, "tinggi_gelombang_m": 1.0, "jarak_pandang_km": 4 },
}

_valid_until_default_dt = datetime.now() + timedelta(hours=1)
_valid_until_default_str = _valid_until_default_dt.strftime("%H:%M")

# --- FORMAT TANGGAL INDONESIA ---
try:
    w_dt = datetime.strptime(waktu_terbaru, "%Y-%m-%d %H:%M")
    bln = ["", "Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
    waktu_terbaru_fmt = f"{w_dt.day} {bln[w_dt.month]} {w_dt.year} pukul {w_dt.strftime('%H:%M')}"
except Exception:
    waktu_terbaru_fmt = f"pukul {waktu_terbaru}"
# --------------------------------

if status_terbaru not in TEMPLATE_DAMPAK:
    narasi_saran = (
        f"Kondisi cuaca di sekitar {LOKASI_EWS} secara umum aman, tidak terpantau "
        f"indikasi signifikan awan konvektif (Cumulonimbus) dalam radius pemantauan "
        f"pada {waktu_terbaru_fmt} WIB. Kondisi ini diperkirakan dapat berlaku "
        f"hingga pukul {_valid_until_default_str} WIB."
    )
else:
    info = TEMPLATE_DAMPAK[status_terbaru]
    kecepatan_angin_kt = data_angin_aws["kecepatan_maks_knot"] if data_angin_aws else info["kecepatan_angin_kt_default"]
    bagian_petir = " disertai petir dan angin kencang" if info["sebut_petir"] else " disertai angin kencang"
    bagian_jarak_pandang = f", beserta penurunan jarak pandang hingga kurang dari {info['jarak_pandang_km']} km" if info["jarak_pandang_km"] else ""
    narasi_saran = (
        f"Terdapat potensi perkembangan cuaca menjadi hujan dengan intensitas "
        f"{info['intensitas_hujan']}{bagian_petir} yang dapat mencapai "
        f"{kecepatan_angin_kt} knot dan peningkatan tinggi gelombang hingga "
        f"{info['tinggi_gelombang_m']} m{bagian_jarak_pandang} di sekitar {LOKASI_EWS}. "
        f"Kondisi ini diperkirakan dapat berlaku hingga pukul {_valid_until_default_str} WIB."
    )

if data_angin_aws:
    detail = data_angin_aws.get("detail_per_stasiun", {})
    baris_detail = [f"{nama}: {d['kecepatan_maks_asli']} {d['satuan_asli']} pukul {d['waktu_data_utc']} UTC" for nama, d in detail.items() if d.get("kecepatan_maks_asli")]
    st.info(f"🌬️ **Data AWS Center (10 menit terakhir):** Maksimum **{data_angin_aws['kecepatan_maks_knot']} knot**. Detail: {'; '.join(baris_detail)}.")
else:
    st.warning(f"🌬️ Data angin AWS Center belum tersedia atau usang (> {BATAS_BASI_ANGIN_MENIT} menit) -- draft narasi memakai nilai default.")


with st.form("form_peringatan", clear_on_submit=False):
    st.text_input("Location", value=LOKASI_EWS, disabled=True)
    forecaster = st.text_input("Forecaster", placeholder="Nama forecaster yang bertanggung jawab")

    col_awal, col_akhir = st.columns(2)
    with col_awal:
        st.markdown("**Initial time**")
        tgl_awal = st.date_input("Tanggal mulai", value=datetime.now().date(), key="tgl_awal")
        jam_awal = st.time_input("Jam mulai (WIB)", value=datetime.now().time().replace(second=0, microsecond=0), key="jam_awal")

    with col_akhir:
        st.markdown("**Valid until**")
        tgl_akhir = st.date_input("Tanggal berakhir", value=(datetime.now() + timedelta(hours=1)).date(), key="tgl_akhir")
        jam_akhir = st.time_input("Jam berakhir (WIB)", value=(datetime.now() + timedelta(hours=1)).time().replace(second=0, microsecond=0), key="jam_akhir")

    narasi = st.text_area(
        "Naration", value=narasi_saran, height=140,
        key=f"narasi_input_{waktu_terbaru}",
    )

    konfirmasi = st.checkbox("I checked the satellite images and confirm the warning based on my expertise")
    tombol_submit = st.form_submit_button("Submit and Publish", width="stretch")

    if tombol_submit:
        initial_time_dt = datetime.combine(tgl_awal, jam_awal)
        valid_until_dt = datetime.combine(tgl_akhir, jam_akhir)

        if not forecaster.strip():
            st.error("Kolom **Forecaster** wajib diisi.")
        elif not narasi.strip():
            st.error("Kolom **Naration** wajib diisi.")
        elif valid_until_dt <= initial_time_dt:
            st.error("**Valid until** harus lebih lambat dari **Initial time**.")
        elif not konfirmasi:
            st.error("Silakan centang konfirmasi terlebih dahulu.")
        else:
            initial_time_fmt = initial_time_dt.strftime("%Y-%m-%d %H:%M")
            valid_until_fmt = valid_until_dt.strftime("%Y-%m-%d %H:%M")
            dipublikasikan_fmt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            simpan_peringatan({
                "lokasi": LOKASI_EWS,
                "forecaster": forecaster.strip(),
                "initial_time": initial_time_fmt,
                "valid_until": valid_until_fmt,
                "narasi": narasi.strip(),
                "dipublikasikan_pada": dipublikasikan_fmt,
            })

            try:
                os.makedirs(PDF_DIR, exist_ok=True)
                nama_pdf = f"peringatan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                path_pdf = os.path.join(PDF_DIR, nama_pdf)
                daftar_png_saat_ini = daftar_png_histori()
                png_untuk_pdf = daftar_png_saat_ini[-1] if daftar_png_saat_ini else PNG_TERBARU

                analysis_untuk_pdf = {
                    "jumlah_sel_signifikan": baris_terbaru.get("jumlah_sel_signifikan"),
                    "luas_sel_terbesar_km2": baris_terbaru.get("luas_sel_terbesar_km2"),
                    "jarak_terdekat_km": baris_terbaru.get("jarak_terdekat_km"),
                    "initial_heading_deg": baris_terbaru.get("initial_heading_deg"),
                    "initial_speed_kmh": baris_terbaru.get("initial_speed_kmh"),
                }

                buat_pdf_peringatan(
                    output_path=path_pdf,
                    lokasi=LOKASI_EWS,
                    forecaster=forecaster.strip(),
                    initial_time_str=initial_time_fmt,
                    valid_until_str=valid_until_fmt,
                    narasi=narasi.strip(),
                    png_path=png_untuk_pdf,
                    analysis=analysis_untuk_pdf,
                    dipublikasikan_pada_str=dipublikasikan_fmt,
                )

                st.session_state["pdf_terakhir"] = path_pdf
                st.session_state["pesan_notif"] = "✅ Peringatan berhasil dipublikasikan & PDF siap di-download!"
            except Exception as e:
                st.session_state["pdf_terakhir"] = None
                st.session_state["pesan_notif"] = f"⚠️ Peringatan dipublikasikan, tapi PDF gagal dibuat: {e}"

            st.rerun()
