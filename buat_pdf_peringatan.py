# -*- coding: utf-8 -*-
"""
GENERATOR PDF - MARINE WEATHER WARNING UPDATE
=============================================================
Membuat dokumen PDF peringatan resmi (mirip format BMKG) dari
data yang disubmit forecaster di dashboard, lengkap dengan
citra satelit dan panel analisis sel awan.

Dipanggil dari dashboard_cb_streamlit.py setelah tombol
"Submit and Publish" ditekan.

Bisa juga dijalankan sendiri untuk uji coba (lihat bagian
__main__ di bawah).
"""

import os
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image, HRFlowable,
)

try:
    from PIL import Image as PILImage
except ImportError:
    PILImage = None


# =============================================================
# KONFIGURASI INSTANSI / KOP SURAT
# -----------------------------------------------------------
# SILAKAN SESUAIKAN dengan instansi/unit kerja Anda yang
# sebenarnya (nama, alamat, telepon, email, logo).
# =============================================================

NAMA_INSTANSI_1 = "BADAN METEOROLOGI KLIMATOLOGI DAN GEOFISIKA"
NAMA_UNIT = "KANTOR LAYANAN METEOROLOGI MARITIM KETAPANG-GILIMANUK"
ALAMAT = "Jl. Situbondo - Banyuwangi, Bulusan, Kalipuro, Banyuwangi"
TELP = "081130569102"
EMAIL = "ketapangbmkg.gmail.com"

# Isi dengan path file logo (PNG/JPG) kalau ada, contoh:
LOGO_PATH = r"C:\Users\bmkg bwi\Documents\Yudhi\logo_bmkg.png"
#LOGO_PATH = None

JUDUL_DOKUMEN = "PERINGATAN DINI CUACA PENYEBERANGAN KETAPANG-GILIMANUK"

TEKS_FOOTER = (
    f"Hak Cipta {datetime.now().year} BMKG - Layanan Informasi Cuaca. "
    "Dokumen dihasilkan otomatis oleh sistem Peringatan Dini."
)


# =============================================================
# FUNGSI BANTUAN
# =============================================================

def _format_tanggal_wib(dt: datetime) -> str:
    """Format: '19 Agu 2026 pukul 04:00 WIB'"""
    bulan_indonesia = {
        "Jan": "Januari", "Feb": "Februari", "Mar": "Maret", "Apr": "April", "May": "Mei",
        "Jun": "Juni", "Jul": "Juli", "Aug": "Agustus", "Sep": "September", "Oct": "Oktober",
        "Nov": "November", "Dec": "Desember",
    }
    bulan_en = dt.strftime("%b")
    bulan_id = bulan_indonesia.get(bulan_en, bulan_en)
    tanggal_str = dt.strftime("%d ") + bulan_id + dt.strftime(" %Y")
    return tanggal_str + " pukul " + dt.strftime("%H:%M") + " WIB"


def _parse_waktu(waktu_str: str) -> datetime:
    """Parse string 'YYYY-MM-DD HH:MM' menjadi datetime."""
    return datetime.strptime(waktu_str, "%Y-%m-%d %H:%M")


def _fmt_analisis(nilai, satuan=""):
    if nilai is None or nilai == "" or (isinstance(nilai, float) and str(nilai) == "nan"):
        return "-"
    if satuan:
        return f"{nilai} {satuan}"
    return f"{nilai}"


# =============================================================
# FUNGSI UTAMA
# =============================================================

def buat_pdf_peringatan(
    output_path: str,
    lokasi: str,
    forecaster: str,
    initial_time_str: str,
    valid_until_str: str,
    narasi: str,
    png_path: str,
    analysis: dict,
    dipublikasikan_pada_str: str = None,
    koordinat_str: str = None,
):
    """
    Membuat file PDF peringatan resmi.
    """

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    initial_time_dt = _parse_waktu(initial_time_str)
    valid_until_dt = _parse_waktu(valid_until_str)

    if dipublikasikan_pada_str:
        try:
            issued_dt = datetime.strptime(dipublikasikan_pada_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            issued_dt = datetime.now()
    else:
        issued_dt = datetime.now()

    styles = getSampleStyleSheet()

    style_center_bold = ParagraphStyle(
        "CenterBold", parent=styles["Normal"],
        alignment=TA_CENTER, fontName="Helvetica-Bold", fontSize=13, leading=16,
    )
    style_center_small = ParagraphStyle(
        "CenterSmall", parent=styles["Normal"],
        alignment=TA_CENTER, fontName="Helvetica", fontSize=9, leading=12,
    )
    style_header_kop = ParagraphStyle(
        "HeaderKop", parent=styles["Normal"],
        alignment=TA_CENTER, fontName="Helvetica", leading=16,
    )
    style_judul_dokumen = ParagraphStyle(
        "JudulDokumen", parent=styles["Normal"],
        alignment=TA_CENTER, fontName="Helvetica-Bold", fontSize=12, leading=16,
        spaceBefore=4, spaceAfter=4,
    )
    style_label_bold = ParagraphStyle(
        "LabelBold", parent=styles["Normal"],
        fontName="Helvetica-Bold", fontSize=9, leading=13,
    )
    style_normal = ParagraphStyle(
        "NormalKecil", parent=styles["Normal"],
        fontName="Helvetica", fontSize=9, leading=13,
    )
    style_warning_title = ParagraphStyle(
        "WarningTitle", parent=styles["Normal"],
        fontName="Helvetica-Bold", fontSize=10, leading=14, spaceAfter=4,
    )
    style_narasi = ParagraphStyle(
        "Narasi", parent=styles["Normal"],
        fontName="Helvetica", fontSize=10, leading=15, alignment=TA_JUSTIFY,
        spaceAfter=10,
    )
    style_analisis_judul = ParagraphStyle(
        "AnalisisJudul", parent=styles["Normal"],
        fontName="Helvetica-Bold", fontSize=8.5, leading=11, spaceAfter=4,
    )
    style_footer = ParagraphStyle(
        "Footer", parent=styles["Normal"],
        alignment=TA_CENTER, fontName="Helvetica-Oblique", fontSize=7.5,
        textColor=colors.grey,
    )

    story = []

    # ---------------------------------------------------------
    # HEADER / KOP SURAT
    # ---------------------------------------------------------

    teks_header = (
        f"<font size=11><b>{NAMA_INSTANSI_1}</b></font><br/>"
        f"<font size=10><b>{NAMA_UNIT}</b></font><br/>"
        f"<font size=9>{ALAMAT}</font><br/>"
        f"<font size=9>Telp: {TELP}   email: {EMAIL}</font>"
    )
    paragraf_header = Paragraph(teks_header, style_header_kop)

    if LOGO_PATH:
        if os.path.exists(LOGO_PATH):
            try:
                if PILImage is not None:
                    with PILImage.open(LOGO_PATH) as im_logo:
                        lw, lh = im_logo.size
                    # Jaga rasio aspek asli logo
                    if lw >= lh:
                        w_logo = 20 * mm
                        h_logo = 20 * mm * lh / lw
                    else:
                        h_logo = 20 * mm
                        w_logo = 20 * mm * lw / lh
                else:
                    w_logo = h_logo = 20 * mm
                sel_logo = Image(LOGO_PATH, width=w_logo, height=h_logo)
                print(f"[PDF] Logo dimuat dari: {LOGO_PATH}")
            except Exception as e:
                print(f"[PDF] LOGO_PATH ditemukan tapi GAGAL dibaca sebagai gambar: {LOGO_PATH} | Error: {e}")
                sel_logo = Spacer(20 * mm, 20 * mm)
        else:
            print(f"[PDF] PERINGATAN: LOGO_PATH tidak ditemukan di path ini: {LOGO_PATH}")
            sel_logo = Spacer(20 * mm, 20 * mm)
    else:
        sel_logo = Spacer(20 * mm, 20 * mm)

    tabel_header = Table(
        [[sel_logo, paragraf_header]],
        colWidths=[25 * mm, 145 * mm],
    )
    tabel_header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (0, 0), "CENTER"),
    ]))

    story.append(tabel_header)
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=1.2, color=colors.black))
    story.append(Spacer(1, 4))
    story.append(Paragraph(JUDUL_DOKUMEN, style_judul_dokumen))
    story.append(HRFlowable(width="100%", thickness=1.2, color=colors.black))
    story.append(Spacer(1, 8))

    # ---------------------------------------------------------
    # INFO: LOCATION (kiri) | ISSUED AT / VALID UNTIL / FORECASTER (kanan)
    # ---------------------------------------------------------

    teks_lokasi = f"<b>Lokasi :</b><br/>{lokasi}"
    if koordinat_str:
        teks_lokasi += f"<br/><font size=8>{koordinat_str}</font>"

    isi_kiri = Paragraph(teks_lokasi, style_normal)

    isi_kanan = Table(
        [
            [Paragraph("<b>Diterbitkan</b>", style_label_bold), Paragraph(f": {_format_tanggal_wib(issued_dt)}", style_normal)],
            [Paragraph("<b>Berlaku hingga</b>", style_label_bold), Paragraph(f": {_format_tanggal_wib(valid_until_dt)}", style_normal)],
            [Paragraph("<b>Prakirawan</b>", style_label_bold), Paragraph(f": {forecaster}", style_normal)],
        ],
        colWidths=[30 * mm, 75 * mm],
    )
    isi_kanan.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]))

    tabel_info = Table(
        [[isi_kiri, isi_kanan]],
        colWidths=[74 * mm, 105 * mm],
    )
    tabel_info.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))

    story.append(tabel_info)
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=0.8, color=colors.grey))
    story.append(Spacer(1, 10))

    # ---------------------------------------------------------
    # JUDUL PERINGATAN + NARASI
    # ---------------------------------------------------------

    judul_peringatan = (
        f"Peringatan Cuaca pada {_format_tanggal_wib(initial_time_dt)} :"
    )
    story.append(Paragraph(judul_peringatan, style_warning_title))
    story.append(Paragraph(narasi.replace("\n", "<br/>"), style_narasi))

    # ---------------------------------------------------------
    # CITRA SATELIT + PANEL ANALISIS
    # ---------------------------------------------------------

    lebar_gambar = 105 * mm
    tinggi_gambar = 105 * mm  

    if png_path and os.path.exists(png_path):
        if PILImage is not None:
            with PILImage.open(png_path) as im:
                iw, ih = im.size
            tinggi_gambar = lebar_gambar * ih / iw
        gambar_satelit = Image(png_path, width=lebar_gambar, height=tinggi_gambar)
    else:
        gambar_satelit = Paragraph("(Citra satelit tidak tersedia)", style_normal)

    baris_analisis = [
        ["Sel Signifikan", ": " + _fmt_analisis(analysis.get("jumlah_sel_signifikan"))],
        ["Sel Terbesar", ": " + _fmt_analisis(analysis.get("luas_sel_terbesar_km2"), "km²")],
        ["Jarak Terdekat", ": " + _fmt_analisis(analysis.get("jarak_terdekat_km"), "km")],
        ["", ""],
        ["Arah Pergerakan", ": " + _fmt_analisis(analysis.get("initial_heading_deg"), "derajat")],
        ["Kecepatan Awal", ": " + _fmt_analisis(analysis.get("initial_speed_kmh"), "km/jam")],
    ]

    style_baris_analisis = ParagraphStyle(
        "BarisAnalisis", parent=styles["Normal"], fontName="Helvetica", fontSize=8, leading=12,
    )

    tabel_analisis_data = [
        [Paragraph(f"<b>{label}</b>" if label else "", style_baris_analisis), Paragraph(nilai, style_baris_analisis)]
        for label, nilai in baris_analisis
    ]

    tabel_analisis = Table(tabel_analisis_data, colWidths=[32 * mm, 24 * mm])
    tabel_analisis.setStyle(TableStyle([
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))

    isi_panel_kanan = [
        Paragraph(f"Analisis untuk {lokasi.split(',')[0]}:", style_analisis_judul),
        tabel_analisis,
    ]

    tabel_utama_citra = Table(
        [[gambar_satelit, isi_panel_kanan]],
        colWidths=[lebar_gambar + 4, 60 * mm],
    )
    tabel_utama_citra.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 1, colors.black),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))

    story.append(tabel_utama_citra)
    story.append(Spacer(1, 16))

    # ---------------------------------------------------------
    # FOOTER
    # ---------------------------------------------------------

    story.append(HRFlowable(width="100%", thickness=0.8, color=colors.grey))
    story.append(Spacer(1, 4))
    story.append(Paragraph(TEKS_FOOTER, style_footer))

    # ---------------------------------------------------------
    # BUILD
    # ---------------------------------------------------------

    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=15 * mm, bottomMargin=15 * mm,
        title=JUDUL_DOKUMEN,
    )
    doc.build(story)

    return output_path


# =============================================================
# UJI COBA MANDIRI
# =============================================================

if __name__ == "__main__":
    hasil = buat_pdf_peringatan(
        output_path="./contoh_peringatan.pdf",
        lokasi="Penyeberangan Ketapang - Gilimanuk",
        forecaster="admin",
        initial_time_str="2026-08-19 04:10",
        valid_until_str="2026-08-19 05:10",
        narasi=(
            "Risk of moderate to heavy rain followed by thunderstorm and fresh "
            "wind up to 20kts with 0.1-0.5m sea rise may occur on 19 Aug 2026 "
            "at 03:50 LT. This condition is predicted until 19 August 2026 at "
            "04:50 LT."
        ),
        png_path="", 
        analysis={
            "jumlah_sel_signifikan": 1,
            "luas_sel_terbesar_km2": 1437,
            "jarak_terdekat_km": 30,
            "initial_heading_deg": 220,
            "initial_speed_kmh": "",
        },
        dipublikasikan_pada_str="2026-08-19 04:00:00",
        koordinat_str="4.179325,106.21283056",
    )
    print("PDF dibuat:", hasil)