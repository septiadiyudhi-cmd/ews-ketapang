# -*- coding: utf-8 -*-
"""
LOGIN SIDARMA & SIMPAN COOKIE
=============================================================
Dijalankan MANUAL (interaktif) sekali saja untuk menyimpan
sesi login SIDARMA, mirip dengan login AWS Center.
"""
import json
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# Mengambil URL dari Secret (jika di Cloud) atau meminta input manual (jika di PC)
LOGIN_URL = os.environ.get("SIDARMA_LOGIN_URL")
if not LOGIN_URL:
    LOGIN_URL = input("Masukkan URL Login SIDARMA: ")

LOCAL_DIR = "./Satelit"
COOKIE_FILE = os.path.join(LOCAL_DIR, "sidarma_cookies.json")

def login_dan_simpan():
    options = webdriver.ChromeOptions()
    options.add_argument("--disable-infobars")
    
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )
    
    try:
        driver.get(LOGIN_URL)
        print("Browser terbuka. Silakan login ke SIDARMA secara manual.")
        input("Tekan ENTER di terminal ini SETELAH peta radar utama muncul di browser...\n")
        
        cookies = driver.get_cookies()
        
        os.makedirs(LOCAL_DIR, exist_ok=True)
        with open(COOKIE_FILE, "w", encoding="utf-8") as f:
            json.dump(cookies, f, indent=2)
            
        print(f"\nBerhasil! Cookie SIDARMA disimpan ke: {COOKIE_FILE}")
        print(f"Jumlah cookie tersimpan: {len(cookies)}")
    finally:
        driver.quit()

if __name__ == "__main__":
    login_dan_simpan()
