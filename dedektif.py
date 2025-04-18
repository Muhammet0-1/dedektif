import sys
import asyncio
import aiohttp
import ssl
import os
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                             QLineEdit, QLabel, QFileDialog, QGroupBox, QTextBrowser,
                             QMessageBox, QProgressBar, QComboBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QTextCursor, QIcon

# --- Search Worker Thread ---
class SearchWorker(QThread):
    """Arka planda ağ aramalarını yürüten iş parçacığı."""
    result_signal = pyqtSignal(str)       # Bulunan/bulunmayan sonuç metnini gönderir
    progress_signal = pyqtSignal(int)    # İlerleme yüzdesini gönderir
    finished_signal = pyqtSignal()       # Arama bittiğinde sinyal gönderir
    error_signal = pyqtSignal(str)         # Hata mesajı gönderir

    def __init__(self, usernames, category, sites_data):
        super().__init__()
        self.usernames = usernames
        self.category = category
        self.sites_data = sites_data
        self.is_running = True

    async def run_search_for_user(self, username, category, sites_config):
        """Belirli bir kullanıcı adı için tüm sitelerde asenkron arama yapar."""
        if category != "Hepsi":
            sites = [site for site in sites_config if site['category'] == category]
        else:
            sites = sites_config

        total_sites = len(sites)
        tasks = []
        # SSL doğrulaması olmayan siteler için özel connector
        connector_no_ssl = aiohttp.TCPConnector(ssl=False)
        # SSL doğrulaması olan siteler için varsayılan connector
        connector_ssl = aiohttp.TCPConnector() # Varsayılan SSL doğrulaması

        async with aiohttp.ClientSession(connector=connector_ssl) as session_ssl, \
                   aiohttp.ClientSession(connector=connector_no_ssl) as session_no_ssl:

            current_site_index = 0
            for site in sites:
                if not self.is_running: # Thread durdurulduysa çık
                    break

                use_no_ssl_session = not site.get("ssl_verify", True)
                current_session = session_no_ssl if use_no_ssl_session else session_ssl

                if site.get('api', False): # API kontrolü için ayrı fonksiyon
                    tasks.append(self.search_api(username, site, current_session))
                else: # Web sitesi kontrolü
                    tasks.append(self.search_website(username, site, current_session))

                # İlerlemeyi güncelle (her site kontrolünden sonra)
                # Toplam ilerleme, mevcut kullanıcı ve mevcut siteye göre hesaplanır
                # Bu kısmı daha doğru bir ilerleme için ana run metoduna taşımak daha iyi olabilir.
                # Şimdilik basit tutalım: Her site kontrolü ilerlemeyi artırsın.
                # Bu worker sadece tek bir kullanıcı için çalıştığından, ilerleme o kullanıcıya aittir.
                # Ana GUI'de bu, toplam kullanıcı sayısına göre ayarlanmalı.

            if not self.is_running: # Thread durdurulduysa taskları çalıştırma
                 await connector_no_ssl.close() # Connector'ları kapat
                 await connector_ssl.close()
                 return

            results = await asyncio.gather(*tasks, return_exceptions=True) # Hataları da yakala

            for result in results:
                 if isinstance(result, Exception):
                     self.error_signal.emit(f"Bir sitede arama sırasında hata oluştu: {result}")
                 elif result is not None: # None dönen taskları atla (örn. API hatası)
                     self.result_signal.emit(result) # Sonucu GUI'ye gönder

        await connector_no_ssl.close() # Connector'ları kapat
        await connector_ssl.close()


    async def search_api(self, username, site, session):
        """API tabanlı site araması yapar."""
        try:
            # GitHub API için özel başlık gerekebilir
            headers = {}
            if "github.com" in site['url']:
                headers = {'Accept': 'application/vnd.github.v3+json'}

            async with session.get(site['url'], headers=headers, timeout=10) as response:
                if response.status == 200:
                    try:
                        data = await response.json()
                        # API'ye özel URL alma mantığı (GitHub örneği)
                        profile_url = data.get("html_url", site['url']) # URL yoksa varsayılanı kullan
                        return self.format_result(username, site['name'], profile_url, True)
                    except aiohttp.ContentTypeError:
                        # JSON olmayan yanıt, yine de başarılı sayılabilir (siteye bağlı)
                         return self.format_result(username, site['name'], site['url'], True)
                elif response.status == 404:
                    return self.format_result(username, site['name'], site['url'], False)
                else:
                    # Diğer durumlar (rate limit vb.) hata olarak bildirilebilir veya bulunamadı sayılabilir
                    return self.format_result(username, site['name'], site['url'], False, f" (Durum Kodu: {response.status})")
        except asyncio.TimeoutError:
             return self.format_result(username, site['name'], site['url'], False, " (Zaman Aşımı)")
        except aiohttp.ClientError as e:
            return self.format_result(username, site['name'], site['url'], False, f" (Ağ Hatası: {type(e).__name__})")
        except Exception as e:
            # Genel hataları da yakala
            self.error_signal.emit(f"{site['name']} API hatası: {e}")
            return None # Hata durumunda None döndür


    async def search_website(self, username, site, session):
        """Web sitesi tabanlı arama yapar (HTTP durum koduna göre)."""
        try:
            # HEAD isteği genellikle daha hızlıdır ve varlığı kontrol etmek için yeterlidir
            async with session.head(site["url"], timeout=10, allow_redirects=True) as response:
                # 2xx veya 3xx durum kodları genellikle var olduğunu gösterir (ancak yanıltıcı olabilir)
                # 404 kesinlikle yok demektir. Diğer 4xx/5xx kodları sorun olduğunu gösterir.
                if 200 <= response.status < 400:
                     # HEAD başarılıysa, tam URL'yi almak için GET deneyebiliriz (isteğe bağlı)
                     # Ancak basitlik için şimdilik sadece HEAD durumuna bakalım
                     return self.format_result(username, site["name"], str(response.url), True) # Yönlendirilmiş URL'yi kullan
                elif response.status == 404:
                    return self.format_result(username, site["name"], site["url"], False)
                else:
                     # Diğer hata durumları
                     return self.format_result(username, site["name"], site["url"], False, f" (Durum Kodu: {response.status})")

        except asyncio.TimeoutError:
             return self.format_result(username, site['name'], site['url'], False, " (Zaman Aşımı)")
        except aiohttp.ClientError as e:
             # Bağlantı hataları vb.
             return self.format_result(username, site["name"], site["url"], False, f" (Ağ Hatası: {type(e).__name__})")
        except Exception as e:
             self.error_signal.emit(f"{site['name']} web sitesi hatası: {e}")
             return None # Hata durumunda None döndür


    def format_result(self, username, site_name, url, found, note=""):
        """Sonuçları HTML formatında döndürür."""
        if found:
            icon = "✔️"
            link = f'<a href="{url}" style="text-decoration:none; color:#4CAF50;">{username}</a>'
            return f'<div>{icon} {link} {site_name} üzerinde bulundu{note}</div>'
        else:
            icon = "❌"
            return f'<div style="color:#AAAAAA;">{icon} {username} {site_name} üzerinde bulunamadı{note}</div>' # Daha soluk renk

    def run(self):
        """Thread'in ana çalışma fonksiyonu."""
        total_usernames = len(self.usernames)
        processed_usernames = 0

        for username in self.usernames:
            username = username.strip()
            if username and self.is_running:
                # Her kullanıcı adı için asyncio.run çağır
                try:
                    asyncio.run(self.run_search_for_user(username, self.category, self.sites_data))
                except Exception as e:
                    self.error_signal.emit(f"'{username}' aranırken genel hata: {str(e)}")

                processed_usernames += 1
                progress = int((processed_usernames / total_usernames) * 100)
                self.progress_signal.emit(progress) # Kullanıcı bazlı ilerleme

            elif not self.is_running:
                break # Döngüden çık

        if self.is_running:
             self.finished_signal.emit() # Tamamlandığında sinyal gönder

    def stop(self):
        self.is_running = False

# --- Ana Uygulama Penceresi ---
class DedektifUygulama(QWidget):
    def __init__(self): # __init__ olarak düzeltildi
        super().__init__()

        # icon.ico dosyasının yolunu belirle (script ile aynı dizinde varsayalım)
        script_dir = os.path.dirname(os.path.realpath(__file__))
        icon_path = os.path.join(script_dir, 'icon.ico')

        self.setWindowTitle("Dedektif")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        else:
            print(f"Uyarı: icon.ico dosyası bulunamadı: {icon_path}")

        # Site verisini burada tanımla
        self.sites_data = [
            {"name": "GitHub", "url": "https://api.github.com/users/{}", "api": True, "category": "Hepsi"}, # URL formatı {} kullanır
            {"name": "Reddit", "url": "https://www.reddit.com/user/{}", "api": False, "category": "Forumlar"},
            {"name": "Instagram", "url": "https://www.instagram.com/{}/", "api": False, "category": "Sosyal Medya"},
            {"name": "X (Twitter)", "url": "https://x.com/{}", "api": False, "category": "Sosyal Medya"}, # Twitter -> X
            {"name": "LinkedIn", "url": "https://www.linkedin.com/in/{}/", "api": False, "category": "Sosyal Medya"},
            {"name": "9GAG", "url": "https://9gag.com/u/{}", "api": False, "category": "Forumlar"},
            {"name": "1337x", "url": "https://1337x.to/user/{}/", "api": False, "category": "Forumlar"},
            {"name": "Twitch", "url": "https://www.twitch.tv/{}", "api": False, "category": "Video Platformları"},
            {"name": "Pinterest", "url": "https://www.pinterest.com/{}/", "api": False, "category": "Sosyal Medya"},
             # {"name": "Discord", "url": "https://discord.com/users/{}", "api": False, "ssl_verify": False, "category": "Sosyal Medya"}, # Discord kullanıcı ID'si gerektirir, username ile çalışmaz
            {"name": "Facebook", "url": "https://www.facebook.com/{}", "api": False, "category": "Sosyal Medya"},
            {"name": "YouTube Kanal", "url": "https://www.youtube.com/@{}", "api": False, "category": "Video Platformları"}, # Youtube URL düzeltildi
            {"name": "Tumblr", "url": "https://{}.tumblr.com/", "api": False, "category": "Sosyal Medya"},
            {"name": "Flickr", "url": "https://www.flickr.com/people/{}/", "api": False, "category": "Sosyal Medya"},
            {"name": "SoundCloud", "url": "https://soundcloud.com/{}", "api": False, "category": "Sosyal Medya"},
            {"name": "Steam", "url": "https://steamcommunity.com/id/{}", "api": False, "category": "Sosyal Medya"},
            {"name": "DeviantArt", "url": "https://www.deviantart.com/{}", "api": False, "ssl_verify": False, "category": "Forumlar"},
            {"name": "VK", "url": "https://vk.com/{}", "api": False, "category": "Sosyal Medya"},
            {"name": "Medium", "url": "https://medium.com/@{}", "api": False, "category": "Sosyal Medya"},
            # {"name": "StackOverflow", "url": "https://stackoverflow.com/users/{}", "api": False, "category": "Forumlar"}, # StackOverflow ID gerektirir
            {"name": "HackerNews", "url": "https://news.ycombinator.com/user?id={}", "api": False, "category": "Forumlar"},
            {"name": "Vimeo", "url": "https://vimeo.com/{}", "api": False, "category": "Video Platformları"},
            {"name": "TikTok", "url": "https://www.tiktok.com/@{}", "api": False, "category": "Sosyal Medya"},
            {"name": "MyAnimeList", "url": "https://myanimelist.net/profile/{}", "api": False, "category": "Sosyal Medya"},
            {"name": "Dribbble", "url": "https://dribbble.com/{}", "api": False, "category": "Sosyal Medya"},
            {"name": "Behance", "url": "https://www.behance.net/{}", "api": False, "category": "Sosyal Medya"},
            {"name": "Foursquare", "url": "https://foursquare.com/{}", "api": False, "category": "Sosyal Medya"},
            {"name": "Dailymotion", "url": "https://www.dailymotion.com/{}", "api": False, "category": "Video Platformları"},
            # {"name": "Slack", "url": "https://{}.slack.com", "api": False, "category": "Sosyal Medya"}, # Slack workspace adı gerektirir
            {"name": "Unsplash", "url": "https://unsplash.com/@{}", "api": False, "category": "Sosyal Medya"},
            {"name": "ProductHunt", "url": "https://www.producthunt.com/@{}", "api": False, "category": "Sosyal Medya"},
            {"name": "Telegram", "url": "https://t.me/{}", "api": False, "category": "Sosyal Medya"},
            {"name": "Snapchat", "url": "https://www.snapchat.com/add/{}", "api": False, "category": "Sosyal Medya"},
            {"name": "Quora", "url": "https://www.quora.com/profile/{}", "api": False, "category": "Sosyal Medya"},
            {"name": "OK.ru", "url": "https://ok.ru/{}", "api": False, "category": "Sosyal Medya"},
            # Aşağıdakiler kullanıcı adı araması için pek uygun değil veya farklı yapıları var
            # {"name": "Weibo", "url": f"https://weibo.com/{username}", "api": False, "category": "Sosyal Medya"},
            # {"name": "Douyin", "url": f"https://www.douyin.com/user/{username}", "api": False, "category": "Sosyal Medya"},
            # {"name": "Baidu", "url": f"https://www.baidu.com/s?wd={username}", "api": False, "category": "Sosyal Medya"}
         ]
        # URL formatını düzelt
        for site in self.sites_data:
             if "{}" not in site["url"]:
                  # Eski formatı düzelt (f-string yerine {} kullan)
                  if f"/{username}" in site["url"]:
                      site["url"] = site["url"].replace(f"/{username}", "/{}")
                  elif f"@{username}" in site["url"]:
                       site["url"] = site["url"].replace(f"@{username}", "@{}")
                  elif f"?id={username}" in site["url"]:
                       site["url"] = site["url"].replace(f"?id={username}", "?id={}")
                  # Gerekirse diğer formatları da ekle

        self.search_thread = None # Arama iş parçacığını tutmak için
        self.initUI()

    def initUI(self):
        main_layout = QVBoxLayout()

        user_input_group = QGroupBox("Kullanıcı Adı Ara (Virgülle ayırarak birden fazla arayabilirsiniz)") # Yazım hatası düzeltildi
        user_input_group.setStyleSheet("""
        QGroupBox {
            border: 1px solid gray; /* Daha ince kenarlık */
            border-radius: 5px;
            margin-top: 10px; /* Daha az üst boşluk */
            background-color: #f0f0f0; /* Biraz daha koyu arka plan */
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top center;
            padding: 0 5px;
            font-size: 11pt; /* Biraz daha küçük başlık */
            font-weight: bold;
            color: #333;
        }
        """)
        user_input_layout = QVBoxLayout()
        self.label = QLabel("Kullanıcı Adı Girin:")
        self.label.setFont(QFont('Arial', 10, QFont.Bold)) # Font boyutu ayarlandı
        self.label.setStyleSheet("color: #333; margin-bottom: 5px;") # Alt boşluk eklendi

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText(
            "Kullanıcı adlarını virgülle ayırarak girin (örnek: kullanıcı1,kullanıcı2)" # Örnekteki boşluk kaldırıldı
        )
        self.username_input.setFont(QFont('Arial', 10)) # Font boyutu ayarlandı
        self.username_input.returnPressed.connect(self.start_search) # start_search çağıracak
        self.username_input.setStyleSheet("""
        QLineEdit {
            background-color: #fff;
            border: 1px solid #ccc;
            padding: 8px; /* Biraz daha az padding */
            border-radius: 4px;
            color: #333;
        }
        """)

        user_input_layout.addWidget(self.label)
        user_input_layout.addWidget(self.username_input)
        user_input_group.setLayout(user_input_layout)

        # Kategori ve Butonları içeren yatay layout
        control_layout = QHBoxLayout()

        # Kategori Seçimi
        category_group = QGroupBox("Kategori")
        category_group_layout = QHBoxLayout() # İç layout
        self.category_label = QLabel("Seçim:")
        self.category_label.setFont(QFont('Arial', 10, QFont.Bold))
        self.category_selector = QComboBox()
        self.category_selector.addItems([
            "Hepsi", "Sosyal Medya", "Forumlar", "Video Platformları"
        ])
        self.category_selector.setFont(QFont('Arial', 10))
        self.category_selector.setStyleSheet("""
        QComboBox {
            background-color: #fff; border: 1px solid #ccc; padding: 5px; border-radius: 4px; color: #333;
        }
        QComboBox::drop-down { border: none; }
        QComboBox::down-arrow { image: none; } /* Oku kaldırmak için */
         """)
        category_group_layout.addWidget(self.category_label)
        category_group_layout.addWidget(self.category_selector)
        category_group.setLayout(category_group_layout)

        # Butonlar
        button_group = QGroupBox("İşlemler")
        button_group_layout = QHBoxLayout()
        self.search_button = QPushButton("Ara")
        self.search_button.setFont(QFont('Arial', 10, QFont.Bold))
        self.search_button.clicked.connect(self.start_search)
        self.search_button.setStyleSheet("""
        QPushButton{ background-color: #4CAF50; color: white; padding: 8px; border-radius: 5px; border: none; }
        QPushButton:hover{ background-color: #45a049; }
        QPushButton:disabled{ background-color: #cccccc; } /* Devre dışı görünümü */
        """)

        self.save_button = QPushButton("Kaydet")
        self.save_button.setFont(QFont('Arial', 10, QFont.Bold))
        self.save_button.clicked.connect(self.save_results)
        self.save_button.setStyleSheet("""
        QPushButton{ background-color: #008CBA; color: white; padding: 8px; border-radius: 5px; border: none; }
        QPushButton:hover{ background-color: #007bb5; }
         """)
        button_group_layout.addWidget(self.search_button)
        button_group_layout.addWidget(self.save_button)
        button_group.setLayout(button_group_layout)

        control_layout.addWidget(category_group)
        control_layout.addWidget(button_group)


        self.progress_bar = QProgressBar(self)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False) # Yüzdeyi gizle
        self.progress_bar.setStyleSheet("""
        QProgressBar{ border: 1px solid #8f8f91; border-radius: 5px; background: #e0e0e0; height: 15px; }
        QProgressBar::chunk{ background-color: #4CAF50; width: 10px; margin: 0.5px; }
        """) # Stil güncellendi

        self.result_area = QTextBrowser()
        self.result_area.setFont(QFont('Arial', 10)) # Font boyutu ayarlandı
        self.result_area.setStyleSheet("""
        QTextBrowser {
            background-color: #ffffff; border-radius: 5px; padding: 10px; border: 1px solid #ccc; color: #333;
        }
        """)
        self.result_area.setOpenExternalLinks(True)
        self.result_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)

        main_layout.addWidget(user_input_group)
        main_layout.addLayout(control_layout) # Kategori ve butonları ekle
        main_layout.addWidget(self.progress_bar)
        main_layout.addWidget(self.result_area)

        self.setLayout(main_layout)
        self.setMinimumSize(550, 450) # Minimum boyut
        self.resize(600, 500) # Başlangıç boyutu
        self.username_input.setFocus()
        self.results = [] # Sonuçları saklamak için liste

    def start_search(self):
        """Arama işlemini başlatan ana fonksiyon."""
        # Eğer önceki arama hala çalışıyorsa durdur
        if self.search_thread and self.search_thread.isRunning():
            self.search_thread.stop() # İş parçacığına durma sinyali gönder
            self.search_thread.wait() # İş parçacığının bitmesini bekle
            QMessageBox.information(self, "Bilgi", "Önceki arama durduruldu.")
            self.search_button.setEnabled(True) # Butonu tekrar etkinleştir

        usernames_text = self.username_input.text()
        if not usernames_text.strip():
            QMessageBox.warning(self, "Hata", "Lütfen en az bir kullanıcı adı girin.")
            return

        usernames = [u.strip() for u in usernames_text.split(',') if u.strip()]
        if not usernames:
             QMessageBox.warning(self, "Hata", "Geçerli bir kullanıcı adı girin.")
             return

        self.result_area.clear()
        self.results = [] # Eski sonuçları temizle
        self.progress_bar.setValue(0)
        self.search_button.setEnabled(False) # Arama sırasında butonu devre dışı bırak

        selected_category = self.category_selector.currentText()

        # URL'leri kullanıcı adlarıyla formatla (her kullanıcı için worker içinde yapılacak)
        # Sadece site listesini ve seçili kategoriyi gönder
        current_sites_data = []
        for site in self.sites_data:
             # URL'yi burada formatlama, worker içinde yap
             # Site verisini kopyala ki orijinal liste değişmesin
             site_copy = site.copy()
             # Formatlama için yer tutucuyu doğrula/ekle
             if '{}' not in site_copy['url']:
                  # Basit yer tutucu ekleme mantığı (gerekirse geliştirilmeli)
                   if '@' in site_copy['url']: site_copy['url'] = site_copy['url'].split('@')[0] + '@{}'
                   elif 'id=' in site_copy['url']: site_copy['url'] = site_copy['url'].split('id=')[0] + 'id={}'
                   elif 'user/' in site_copy['url']: site_copy['url'] = site_copy['url'].split('user/')[0] + 'user/{}' + site_copy['url'].split('user/')[-1].split('/')[1:] # Daha dikkatli olmalı
                   elif '.com/' in site_copy['url'] and site_copy['url'].endswith('/'): site_copy['url'] += '{}'
                   elif '.com/' in site_copy['url']: site_copy['url'] += '/{}'
                   else: # Varsayılan olarak sona ekle
                       site_copy['url'] += '/{}'

                 # Kullanıcı adı formatlamasını dinamik hale getir (örneğin medium için @)
                 if "medium.com" in site_copy["url"]:
                     site_copy["url_format"] = site_copy["url"].replace("@{}", "{}") # Worker içinde @ eklenecek
                     site_copy["prefix"] = "@"
                 elif "tiktok.com" in site_copy["url"]:
                      site_copy["url_format"] = site_copy["url"] # Zaten @ içeriyor
                      site_copy["prefix"] = "@"
                 elif "unsplash.com" in site_copy["url"]:
                      site_copy["url_format"] = site_copy["url"] # Zaten @ içeriyor
                      site_copy["prefix"] = "@"
                 elif "producthunt.com" in site_copy["url"]:
                      site_copy["url_format"] = site_copy["url"] # Zaten @ içeriyor
                      site_copy["prefix"] = "@"
                 else:
                      site_copy["url_format"] = site_copy["url"]
                      site_copy["prefix"] = ""


                 # API URL'sini de doğru formatla
                 if site_copy.get("api"):
                     site_copy["url"] = site_copy["url"].replace(f"/{username}", "/{}") # Eski f-string kalıntısını düzelt


                 # URL'deki {} yer tutucusunu kullanarak formatla
                 # Formatlamayı worker içinde username ile yapacağız
                 current_sites_data.append(site_copy)

        # Worker thread'i başlat
        self.search_thread = SearchWorker(usernames, selected_category, current_sites_data)
        self.search_thread.result_signal.connect(self.append_result)
        self.search_thread.progress_signal.connect(self.update_progress)
        self.search_thread.finished_signal.connect(self.search_finished)
        self.search_thread.error_signal.connect(self.show_error)
        self.search_thread.start()

    @staticmethod # Statik metod olarak işaretle, self'e ihtiyacı yok
    def _format_url(site_template, username):
        """URL'yi kullanıcı adıyla doğru şekilde formatlar."""
        # Özel durumlar (varsa)
        if "medium.com" in site_template["url"]:
            return site_template["url"].replace("{}", username)
        if "tumblr.com" in site_template["url"]:
            return site_template["url"].replace("{}", username) # Subdomain
        # Genel durum
        return site_template["url"].format(username)


    def update_progress(self, value):
        """İlerleme çubuğunu günceller."""
        self.progress_bar.setValue(value)

    def append_result(self, result_html):
        """Sonuç alanına metin ekler ve listeye kaydeder."""
        self.result_area.append(result_html)
        self.result_area.moveCursor(QTextCursor.Start)
        # HTML olmayan metni listeye ekle (kaydetmek için)
        # Basit bir HTML temizleme yapalım (daha iyisi için kütüphane gerekebilir)
        import re
        clean_text = re.sub('<[^<]+?>', '', result_html) # Basit HTML tag temizliği
        # İkonları ve linkleri temizle
        clean_text = clean_text.replace("✔️","+").replace("❌","-")
        self.results.append(clean_text.strip()) # Temizlenmiş metni ekle


    def search_finished(self):
        """Arama bittiğinde çağrılır."""
        self.search_button.setEnabled(True) # Butonu tekrar etkinleştir
        QMessageBox.information(self, "Bilgi", "Arama Tamamlandı!")

    def show_error(self, error_message):
         """Hata mesajını gösterir."""
         self.result_area.append(f'<div style="color:red;">HATA: {error_message}</div>')


    def save_results(self):
        """Sonuçları bir metin dosyasına kaydeder."""
        if not self.results:
            QMessageBox.warning(self,"Uyarı","Kaydedilecek sonuç bulunamadı.")
            return

        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog # İsteğe bağlı: Platformun kendi dialogunu kullanma
        filename, _ = QFileDialog.getSaveFileName(self, "Sonuçları Kaydet", "",
                                                  "Text Files (*.txt);;All Files (*)", options=options)
        if filename:
            # Dosya adının .txt ile bittiğinden emin ol (eğer seçilmediyse)
            if not filename.lower().endswith(".txt"):
                 filename += ".txt"

            try:
                with open(filename, 'w', encoding='utf-8') as file:
                     # HTML yerine temizlenmiş metin listesini yaz
                    for line in self.results:
                        file.write(line + "\n") # Her sonucu yeni satıra yaz
                QMessageBox.information(self, "Bilgi", f"Sonuçlar başarıyla '{os.path.basename(filename)}' dosyasına kaydedildi!")
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Dosya kaydedilirken bir hata oluştu:\n{str(e)}")

    # Uygulama kapatılırken iş parçacığını durdur
    def closeEvent(self, event):
        if self.search_thread and self.search_thread.isRunning():
            self.search_thread.stop()
            self.search_thread.wait() # Thread'in bitmesini bekle
        event.accept()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    # Event loop politikası ayarı (Windows için gerekebilir)
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    dedektif = DedektifUygulama()
    dedektif.show()
    sys.exit(app.exec_())
