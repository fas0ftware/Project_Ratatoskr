from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time

# --- SADE TEST KODU (PROFİLSİZ) ---
def if __name__ == "__main__":
    test_connection():
    print("🌍 Test başlıyor: Profilsiz temiz bir Chrome açılıyor...")
    
    # Hiçbir ayar (options) eklemiyoruz, dümdüz açıyoruz.
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))

    try:
        driver.get("https://web.whatsapp.com")
        print("✅ Başarılı! Siteye gidildi.")
        
        # Kapanmaması için uzun süre bekletiyorum
        time.sleep(30)
        
    except Exception as e:
        print(f"❌ Hata: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    test_connection()