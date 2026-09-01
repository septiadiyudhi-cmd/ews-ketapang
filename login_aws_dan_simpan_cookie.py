# -*- coding: utf-8 -*-
"""
Created on Mon Aug 31 08:29:19 2026

@author: bmkg bwi
"""

# -*- coding: utf-8 -*-
"""
LOGIN AWS CENTER BMKG & SIMPAN SESSION COOKIE
=============================================================
Dijalankan MANUAL (interaktif) -- setiap kali sesi login AWS
Center kadaluarsa (biasanya kalau ambil_angin_aws.py mulai gagal
terus-menerus dengan pesan "sesi kadaluarsa").

Cara pakai:
    python login_aws_dan_simpan_cookie.py

Browser Chrome akan terbuka -> login manual seperti biasa ->
kembali ke terminal -> tekan ENTER -> cookie sesi disimpan ke
file, dipakai otomatis oleh ambil_angin_aws.py setiap 10 menit
tanpa perlu login ulang (sampai sesi itu kadaluarsa lagi).
"""

import json
import os

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

LOGIN_URL = "https://awscenter.bmkg.go.id/base"

# HARUS SAMA dengan LOCAL_DIR di script lain
LOCAL_DIR = "./Satelit"
COOKIE_FILE = os.path.join(LOCAL_DIR, "aws_center_cookies.json")

# Wajib False -- browser harus tampil supaya bisa login manual
HEADLESS = False


def login_dan_simpan_cookie():
    options = webdriver.ChromeOptions()
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-extensions")
    if HEADLESS:
        options.add_argument("--headless")

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options,
    )

    try:
        driver.get(LOGIN_URL)
        print("Browser terbuka. Silakan login AWS Center secara manual di jendela itu.")
        input("Tekan ENTER di sini (terminal ini) setelah berhasil login...\n")

        cookies = driver.get_cookies()

        os.makedirs(LOCAL_DIR, exist_ok=True)
        with open(COOKIE_FILE, "w", encoding="utf-8") as f:
            json.dump(cookies, f, indent=2)

        print(f"\nBerhasil! Cookie session disimpan ke: {COOKIE_FILE}")
        print(f"Jumlah cookie tersimpan: {len(cookies)}")
        print("Sekarang ambil_angin_aws.py bisa mengambil data otomatis tanpa login ulang.")

    finally:
        driver.quit()


if __name__ == "__main__":
    login_dan_simpan_cookie()