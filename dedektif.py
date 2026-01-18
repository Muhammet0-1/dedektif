import sys
import asyncio
import aiohttp
import os
import re
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                             QLineEdit, QLabel, QFileDialog, QGroupBox, QTextBrowser,
                             QMessageBox, QProgressBar, QComboBox, QFrame)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QIcon, QColor, QPalette

# === KONFIGURASYON VE SABITLER ===
APP_NAME = "Dedektif v2.0"
VERSION = "2.0.0"
AUTHOR = "LordMs"

# Kendimizi tarayıcı gibi göstermek için User-Agent (WAF Bypass)
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# Site Veritabanı
SITES_DB = [
    {"name": "GitHub", "url": "https://api.github.com/users/{}", "api": True, "category": "Kodlama"},
    {"name": "Instagram", "url": "https://www.instagram.com/{}/", "api": False, "category": "Sosyal Medya"},
    {"name": "Twitter (X)", "url": "https://x.com/{}", "api": False, "category": "Sosyal Medya"},
    {"name": "Reddit", "url": "https://www.reddit.com/user/{}", "api": False, "category": "Forum"},
    {"name": "Twitch", "url": "https://www.twitch.tv/{}", "api": False, "category": "Yayın"},
    {"name": "Spotify", "url": "https://open.spotify.com/user/{}", "api": False, "category": "Müzik"},
    {"name": "Steam", "url": "https://steamcommunity.com/id/{}", "api": False, "category": "Oyun"},
    {"name": "Pinterest", "url": "https://www.pinterest.com/{}/", "api": False, "category": "Sosyal Medya"},
    {"name": "Medium", "url": "https://medium.com/@{}", "api": False, "category": "Blog"},
    {"name": "Telegram", "url": "https://t.me/{}", "api": False, "category": "Mesajlaşma"},
    {"name": "GitLab", "url": "https://gitlab.com/{}", "api": False, "category": "Kodlama"},
    {"name": "HackTheBox", "url": "https://www.hackthebox.eu/home/users/profile/{}", "api": False, "category": "Siber Güvenlik"},
    {"name": "TryHackMe", "url": "https://tryhackme.com/p/{}", "api": False, "category": "Siber Güvenlik"},
    {"name": "Pastebin", "url": "https://pastebin.com/u/{}", "api": False, "category": "Araçlar"},
    {"name": "Wattpad", "url": "https://www.wattpad.com/user/{}", "api": False, "category": "Blog"},
    {"name": "Wikipedia", "url": "https://en.wikipedia.org/wiki/User:{}", "api": False, "category": "Bilgi"},
]

# --- Arka Plan İşçisi (Worker Thread) ---
class SearchWorker(QThread):
    result_signal = pyqtSignal(str, str) # HTML sonuç, Temiz Metin
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal()
    error_signal = pyqtSignal(str)

    def __init__(self, usernames, category):
        super().__init__()
        self.usernames = usernames
        self.category = category
        self.is_running = True

    async def check_site(self, session, username, site):
        if not self.is_running: return None

        target_url = site['url'].format(username)
        site_name = site['name']

        try:
            # API Kontrolü
            if site.get('api'):
                async with session.get(target_url, headers=HEADERS, timeout=10) as response:
                    if response.status == 200:
                        return (True, site_name, target_url)
                    elif response.status == 404:
                        return (False, site_name, target_url)
                    else:
                        return (False, site_name, f"Hata: {response.status}")

            # Normal Site Kontrolü (HEAD isteği daha hızlıdır)
            # Bazı siteler HEAD reddeder, o yüzden fallback olarak GET kullanılabilir ama şimdilik HEAD.
            else:
                async with session.get(target_url, headers=HEADERS, timeout=10) as response:
                    # 200 OK ve yönlendirme kontrolü
                    if response.status == 200:
                        # Yanlış pozitifleri önlemek için basit bir içerik kontrolü eklenebilir
                        # Ancak genel kullanım için status code yeterlidir.
                        return (True, site_name, str(response.url))
                    elif response.status == 404:
                        return (False, site_name, target_url)
                    else:
                        return (False, site_name, f"Status: {response.status}")

        except Exception as e:
            return (False, site_name, f"Error: {str(e)}")

    async def run_async_search(self):
        connector = aiohttp.TCPConnector(ssl=False) # SSL hatalarını yoksay
        async with aiohttp.ClientSession(connector=connector) as session:

            # Kategori Filtreleme
            if self.category == "Hepsi":
                target_sites = SITES_DB
            else:
                target_sites = [s for s in SITES_DB if s['category'] == self.category]

            total_ops = len(self.usernames) * len(target_sites)
            completed_ops = 0

            for user in self.usernames:
                if not self.is_running: break

                tasks = []
                self.result_signal.emit(f"<h3 style='color:#00e5ff'>🔎 Hedef: {user}</h3>", f"--- Hedef: {user} ---")

                # Asenkron görevleri oluştur
                for site in target_sites:
                    tasks.append(self.check_site(session, user, site))

                # Hepsini aynı anda başlat
                results = await asyncio.gather(*tasks)

                # Sonuçları işle
                for found, name, url in results:
                    completed_ops += 1
                    progress = int((completed_ops / total_ops) * 100)
                    self.progress_signal.emit(progress)

                    if found:
                        html = f"<div style='color:#00ff00'>[+] <b>{name}</b>: <a href='{url}' style='color:#00ff00'>{url}</a></div>"
                        text = f"[+] {name}: {url}"
                        self.result_signal.emit(html, text)
                    elif "Error" in url or "Status" in url:
                        # Hataları sarı göster
                        pass # Hata kalabalığı yapmamak için gizleyebilirsin veya loglayabilirsin
                    else:
                        # Bulunamayanları gri göster
                        html = f"<div style='color:#555'>[-] {name}: Bulunamadı</div>"
                        text = f"[-] {name}: Bulunamadı"
                        self.result_signal.emit(html, text)

                self.result_signal.emit("<br>", "") # Kullanıcılar arası boşluk

    def run(self):
        asyncio.run(self.run_async_search())
        self.finished_signal.emit()

    def stop(self):
        self.is_running = False

# --- Ana Arayüz (Modern Dark Theme) ---
class DedektifApp(QWidget):
    def __init__(self):
        super().__init__()
        self.raw_results = [] # Kayıt için temiz metinler
        self.initUI()

    def initUI(self):
        self.setWindowTitle(f"{APP_NAME} - OSINT Tool")
        self.setGeometry(200, 200, 800, 600)
        self.setStyleSheet("background-color: #121212; color: #e0e0e0; font-family: 'Segoe UI', sans-serif;")

        main_layout = QVBoxLayout()
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # 1. Başlık
        title = QLabel("🕵️‍♂️ DEDEKTİF")
        title.setFont(QFont("Segoe UI", 24, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #00e5ff; letter-spacing: 2px;")
        main_layout.addWidget(title)

        # 2. Giriş Alanı
        input_group = QGroupBox("Hedef Kullanıcılar")
        input_group.setStyleSheet("QGroupBox { border: 1px solid #333; border-radius: 5px; margin-top: 10px; color: #aaa; font-weight: bold; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }")
        input_layout = QVBoxLayout()

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Kullanıcı adlarını virgülle ayırın (örn: lordms, admin, testuser)")
        self.input_field.setStyleSheet("padding: 10px; border: 1px solid #333; border-radius: 5px; background-color: #1e1e1e; color: #fff; font-size: 14px;")
        input_layout.addWidget(self.input_field)
        input_group.setLayout(input_layout)
        main_layout.addWidget(input_group)

        # 3. Kontroller (Kategori ve Butonlar)
        controls_layout = QHBoxLayout()

        # Kategori
        self.cat_combo = QComboBox()
        categories = ["Hepsi"] + sorted(list(set([s['category'] for s in SITES_DB])))
        self.cat_combo.addItems(categories)
        self.cat_combo.setStyleSheet("padding: 8px; background-color: #1e1e1e; color: #fff; border: 1px solid #333; border-radius: 5px; min-width: 150px;")
        controls_layout.addWidget(self.cat_combo)

        # Ara Butonu
        self.btn_search = QPushButton("TARAMAYI BAŞLAT")
        self.btn_search.setStyleSheet("""
            QPushButton { background-color: #00e5ff; color: #000; font-weight: bold; padding: 10px; border-radius: 5px; }
            QPushButton:hover { background-color: #00b8cc; }
            QPushButton:pressed { background-color: #008ba3; }
            QPushButton:disabled { background-color: #333; color: #555; }
        """)
        self.btn_search.clicked.connect(self.start_scan)
        controls_layout.addWidget(self.btn_search)

        # Kaydet Butonu
        self.btn_save = QPushButton("💾")
        self.btn_save.setStyleSheet("background-color: #333; color: #fff; padding: 10px; border-radius: 5px;")
        self.btn_save.clicked.connect(self.save_results)
        controls_layout.addWidget(self.btn_save)

        main_layout.addLayout(controls_layout)

        # 4. Progress Bar
        self.progress = QProgressBar()
        self.progress.setStyleSheet("""
            QProgressBar { border: none; background-color: #1e1e1e; height: 5px; text-align: center; }
            QProgressBar::chunk { background-color: #00e5ff; }
        """)
        main_layout.addWidget(self.progress)

        # 5. Sonuç Ekranı
        self.console = QTextBrowser()
        self.console.setOpenExternalLinks(True)
        self.console.setStyleSheet("background-color: #000; border: 1px solid #333; border-radius: 5px; padding: 10px; font-family: 'Consolas', monospace; font-size: 13px;")
        main_layout.addWidget(self.console)

        self.setLayout(main_layout)

    def start_scan(self):
        users_text = self.input_field.text().strip()
        if not users_text:
            QMessageBox.warning(self, "Hata", "Lütfen en az bir kullanıcı adı girin!")
            return

        self.console.clear()
        self.raw_results = []
        self.btn_search.setEnabled(False)
        self.progress.setValue(0)

        usernames = [u.strip() for u in users_text.split(",") if u.strip()]
        category = self.cat_combo.currentText()

        self.worker = SearchWorker(usernames, category)
        self.worker.result_signal.connect(self.update_console)
        self.worker.progress_signal.connect(self.progress.setValue)
        self.worker.finished_signal.connect(self.scan_finished)
        self.worker.start()

    def update_console(self, html, text):
        self.console.append(html)
        if text: self.raw_results.append(text)

    def scan_finished(self):
        self.btn_search.setEnabled(True)
        self.progress.setValue(100)
        QMessageBox.information(self, "Bitti", "Tarama tamamlandı!")

    def save_results(self):
        if not self.raw_results:
            QMessageBox.warning(self, "Uyarı", "Kaydedilecek veri yok.")
            return

        path, _ = QFileDialog.getSaveFileName(self, "Kaydet", "dedektif_sonuclar.txt", "Text Files (*.txt)")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"--- {APP_NAME} Tarama Sonuçları ---\n")
                f.write("\n".join(self.raw_results))
            QMessageBox.information(self, "Başarılı", "Dosya kaydedildi.")

if __name__ == '__main__':
    # Windows/Linux Asyncio Loop Policy Ayarı
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    app = QApplication(sys.argv)
    window = DedektifApp()
    window.show()
    sys.exit(app.exec_())
