from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
import os
import time

def send_whatsapp_dedicated(contact_name, message):
    options = Options()
    
    # --- EN ÖNEMLİ KISIM ---
    # Bot için C diskinde özel bir klasör oluşturuyoruz.
    # Böylece senin ana Chrome'unla çakışmayacak.
    
    # Klasör yolunu belirle (C:\Ratatoskr_Data)
    user_data_path = os.path.join("C:\\", "Ratatoskr_Data")
    
    # Eğer klasör yoksa oluştur (Otomatik)
    if not os.path.exists(user_data_path):
        os.makedirs(user_data_path)
        print(f"📁 Yeni profil klasörü oluşturuldu: {user_data_path}")
    
    options.add_argument(f"user-data-dir={user_data_path}") 
    # Profil dizini belirtmeye gerek yok, otomatik 'Default' oluşturur.

    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    print("🌍 Ratatoskr: Özel profil ile başlatılıyor...")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    driver.get("https://web.whatsapp.com")
    
    print("⏳ WhatsApp bekleniyor...")
    
    # --- İLK GİRİŞ KONTROLÜ ---
    # Eğer bu kodu İLK kez çalıştırıyorsan QR kodu okutman için süreye ihtiyacın var.
    # Aşağıdaki süreyi (30 saniye) QR kodu rahatça okutmak için kullan.
    # Bir kere okuttuktan sonra burayı kısaltabilirsin (örn: 10).
    print("⚠️ DİKKAT: Eğer giriş yapmadıysan QR Kodu okutman için 30 saniyen var!")
    time.sleep(10) 

    try:
        # Arama kutusu
        search_box = driver.find_element(By.XPATH, '//div[@contenteditable="true"][@data-tab="3"]')
        search_box.click()
        time.sleep(1)
        
        # Kişi Arama
        print(f"🐿️ Ratatoskr: '{contact_name}' aranıyor...")
        search_box.send_keys(contact_name)
        time.sleep(2)
        search_box.send_keys(Keys.ENTER)
        time.sleep(2)
        for i in range(10):#Çoklu mesaj için
            # Mesaj Yazma
            message_box = driver.find_element(By.XPATH, '//div[@contenteditable="true"][@data-tab="10"]')
            message_box.click()
        
            print(f"📨 Mesaj atılıyor...")
            message_box.send_keys(message)
            time.sleep(1)
            message_box.send_keys(Keys.ENTER)
            print(f"✅ Başarılı! Mesaj gitti.")
        
        time.sleep(3)

    except Exception as e:
        print(f"❌ Hata (Muhtemelen QR okutulmadı veya süre yetmedi): {e}")
    
    finally:
        # Test bittiğinde kapanmasın istiyorsan bu satırı sil veya yorum satırı yap (#)
        driver.quit()
        print("🔌 Ratatoskr kapandı.")

# --- TEST ---
target_person = "Namık Deveci" 
msg = "Balon Fatihi sikenler kulubune kabul edildiniz"

send_whatsapp_dedicated(target_person, msg)