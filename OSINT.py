# Gerekli kütüphaneleri içe aktaralım
import sys
import asyncio
import aiohttp
import ssl
import os
import re  # HTML temizliği için düzenli ifadeler
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                             QLineEdit, QLabel, QFileDialog, QGroupBox, QTextBrowser,
                             QMessageBox, QProgressBar, QComboBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QTextCursor, QIcon

# --- Ağ Aramalarını Yapan Arka Plan İş Parçacığı ---
class SearchWorker(QThread):
    """
    Arka planda, GUI'yi dondurmadan ağ aramalarını asenkron olarak yürüten iş parçacığı.
    aiohttp ve asyncio kullanarak eş zamanlı site kontrolleri yapar.
    """
    # GUI ile iletişim kurmak için sinyaller tanımlanır
    result_signal = pyqtSignal(str)       # Bulunan/bulunmayan sonuç metnini (HTML formatında) gönderir
    progress_signal = pyqtSignal(int)    # Toplam ilerleme yüzdesini (işlenen kullanıcı sayısına göre) gönderir
    finished_signal = pyqtSignal()       # Tüm kullanıcı adları için arama bittiğinde sinyal gönderir
    error_signal = pyqtSignal(str)         # Arama sırasında oluşan hataları (ağ, site vb.) gönderir

    def __init__(self, usernames, category, sites_data):
        """
        Worker thread'i başlatır.

        Args:
            usernames (list): Aranacak kullanıcı adlarının listesi.
            category (str): Seçilen site kategorisi ("Hepsi", "Sosyal Medya" vb.).
            sites_data (list): Arama yapılacak sitelerin bilgilerini içeren sözlük listesi.
        """
        super().__init__()
        self.usernames = usernames
        self.category = category
        self.sites_data = sites_data
        self.is_running = True # Thread'in çalışıp çalışmadığını kontrol eden bayrak (durdurmak için)

    async def run_search_for_user(self, username, category, sites_config):
        """
        Belirli bir kullanıcı adı için seçilen kategorideki tüm sitelerde asenkron arama yapar.

        Args:
            username (str): Aranacak tek bir kullanıcı adı.
            category (str): Filtrelenecek site kategorisi.
            sites_config (list): Tüm sitelerin yapılandırma verisi.
        """
        # Seçilen kategoriye göre siteleri filtrele
        if category != "Hepsi":
            sites_to_search = [site for site in sites_config if site['category'] == category]
        else:
            sites_to_search = sites_config # "Hepsi" seçiliyse tüm siteleri al

        if not sites_to_search: # Eğer seçilen kategoride site yoksa veya site listesi boşsa
             self.error_signal.emit(f"'{category}' kategorisinde aranacak site bulunamadı.")
             return

        tasks = [] # Asenkron görevleri (her bir site araması) tutacak liste

        # Ağ istekleri için iki farklı aiohttp session oluşturuyoruz:
        # 1. connector_ssl: Varsayılan SSL sertifika doğrulamasını kullanır (çoğu site için).
        # 2. connector_no_ssl: SSL sertifika doğrulamasını kapatır (güvenilmeyen veya
        #    süresi geçmiş sertifikalara sahip siteler için gereklidir, örn: DeviantArt).
        #    UYARI: SSL doğrulamasını kapatmak güvenlik riski oluşturabilir (Man-in-the-Middle saldırıları).
        #           Sadece bilinen ve gerekli siteler için kullanılmalıdır.
        connector_no_ssl = aiohttp.TCPConnector(ssl=False)
        connector_ssl = aiohttp.TCPConnector() # Varsayılan SSL doğrulaması aktif

        # 'async with' blokları, session'ların ve connector'ların iş bittiğinde
        # veya bir hata oluştuğunda otomatik olarak kapanmasını sağlar.
        async with aiohttp.ClientSession(connector=connector_ssl) as session_ssl, \
                   aiohttp.ClientSession(connector=connector_no_ssl) as session_no_ssl:

            for site in sites_to_search:
                # Eğer thread durdurulmuşsa (kullanıcı iptal ettiyse), döngüden çık
                if not self.is_running:
                    self.error_signal.emit("Arama işlemi kullanıcı tarafından iptal edildi.")
                    break # For döngüsünden çık

                # Sitenin SSL doğrulaması isteyip istemediğine göre uygun session'ı seç
                use_no_ssl_session = not site.get("ssl_verify", True) # Varsayılan olarak SSL doğrulaması yapılır
                current_session = session_no_ssl if use_no_ssl_session else session_ssl

                # Arama görevini oluştur (API veya normal web sitesi kontrolü)
                if site.get('api', False): # Eğer site 'api': True olarak işaretlenmişse
                    # API tabanlı arama için bir asenkron görev oluştur
                    tasks.append(self.search_api(username, site, current_session))
                else: # Normal web sitesi kontrolü
                    # Web sitesi varlığını kontrol etmek için bir asenkron görev oluştur
                    tasks.append(self.search_website(username, site, current_session))

            # Eğer thread durdurulduysa, oluşturulan görevleri çalıştırma
            if not self.is_running:
                 # Connector'ları manuel olarak kapatmaya gerek yok, 'async with' bunu halleder.
                 # Sadece fonksiyondan çıkıyoruz.
                 return

            # Tüm site arama görevlerini eş zamanlı olarak çalıştır ve sonuçları topla
            # return_exceptions=True sayesinde, bir görev hata verse bile diğerleri çalışmaya devam eder
            # ve sonuçlar listesinde hata nesnesi olarak döner.
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Toplanan sonuçları işle
            for result in results:
                 if isinstance(result, Exception):
                     # Eğer sonuç bir Exception nesnesi ise, bunu hata olarak bildir
                     # Bu genellikle ağ hatası, zaman aşımı veya gather içindeki beklenmedik bir sorundur.
                     self.error_signal.emit(f"Bir sitede arama sırasında hata oluştu: {result}")
                 elif result is not None: # search_api/search_website None dönebilir (örn. iç hata loglandı)
                     # Geçerli bir sonuç (HTML string) geldiyse, bunu GUI'ye gönder
                     self.result_signal.emit(result)

        # async with blokları bittiğinde session'lar ve connector'lar otomatik olarak kapanır.
        # Manuel close() çağrılarına gerek yok.

    async def search_api(self, username, site, session):
        """
        API tabanlı bir sitede kullanıcı adı araması yapar.
        Genellikle JSON yanıtı beklenir.

        Args:
            username (str): Aranacak kullanıcı adı.
            site (dict): Aranacak site bilgileri (URL şablonu vb.).
            session (aiohttp.ClientSession): Kullanılacak aiohttp oturumu.

        Returns:
            str: Sonucu gösteren HTML formatında bir metin veya hata durumunda None.
        """
        try:
            # URL şablonunu kullanıcı adıyla formatla
            target_url = site['url'].format(username)

            # Bazı API'ler özel başlıklar (headers) gerektirebilir (örn. GitHub)
            headers = {}
            if "api.github.com" in target_url:
                headers = {'Accept': 'application/vnd.github.v3+json'}
                # Not: Kimlik doğrulaması olmadan GitHub API'sinin hız limitleri vardır.
                # Çok fazla istekte bulunursanız 403 hatası alabilirsiniz.

            # Belirtilen URL'ye GET isteği gönder (10 saniye zaman aşımı ile)
            async with session.get(target_url, headers=headers, timeout=10) as response:
                # HTTP durum kodunu kontrol et
                if response.status == 200: # Başarılı yanıt
                    try:
                        # Yanıtı JSON olarak ayrıştırmaya çalış
                        data = await response.json(content_type=None) # Content-Type kontrolünü esnetelim
                        # API yanıtından profil URL'sini almaya çalış (örneğin GitHub'da 'html_url')
                        # Eğer özel bir URL yoksa, istek yapılan URL'yi kullan
                        profile_url = data.get("html_url", target_url) if isinstance(data, dict) else target_url
                        # Başarılı sonucu formatla ve döndür
                        return self.format_result(username, site['name'], profile_url, True)
                    except (aiohttp.ContentTypeError, ValueError, TypeError):
                        # Yanıt JSON değilse veya beklenen yapıda değilse,
                        # yine de 200 OK döndüğü için var kabul edilebilir (siteye bağlı).
                        # Örneğin, bazı API'ler başarı durumunda boş yanıt veya metin dönebilir.
                        return self.format_result(username, site['name'], target_url, True, " (API Yanıtı Doğrulanamadı)")
                elif response.status == 404: # Not Found - Kullanıcı bulunamadı
                    return self.format_result(username, site['name'], target_url, False)
                elif response.status == 403: # Forbidden - Genellikle hız limiti veya yetkilendirme sorunu
                    return self.format_result(username, site['name'], target_url, False, f" (Erişim Engellendi - Hız Limiti?)")
                else: # Diğer HTTP hataları (5xx sunucu hataları vb.)
                    # Bunları bulunamadı olarak işaretleyebilir veya hata olarak loglayabiliriz.
                    # Şimdilik bulunamadı olarak işaretleyelim ve durum kodunu ekleyelim.
                    return self.format_result(username, site['name'], target_url, False, f" (Durum Kodu: {response.status})")
        except asyncio.TimeoutError:
             # İstek zaman aşımına uğradı
             return self.format_result(username, site['name'], site['url'].format(username), False, " (Zaman Aşımı)")
        except aiohttp.ClientError as e:
             # aiohttp ile ilgili ağ hataları (bağlantı kurulamadı, DNS çözülemedi vb.)
             return self.format_result(username, site['name'], site['url'].format(username), False, f" (Ağ Hatası: {type(e).__name__})")
        except KeyError:
             # site['url'].format(username) başarısız oldu (URL şablonunda {} yoksa)
             self.error_signal.emit(f"URL formatlama hatası: {site['name']} - URL: {site.get('url', 'URL Yok')}")
             return None # Hata GUI'ye gönderildi, sonuç döndürme
        except Exception as e:
             # Beklenmedik diğer tüm hataları yakala
             self.error_signal.emit(f"{site['name']} API araması sırasında beklenmedik hata: {e}")
             return None # Hata GUI'ye gönderildi, sonuç döndürme

    async def search_website(self, username, site, session):
        """
        Normal bir web sitesinde kullanıcı adının varlığını kontrol eder.
        Genellikle HTTP durum koduna veya yönlendirmelere bakar. HEAD isteği tercih edilir.

        Args:
            username (str): Aranacak kullanıcı adı.
            site (dict): Aranacak site bilgileri (URL şablonu vb.).
            session (aiohttp.ClientSession): Kullanılacak aiohttp oturumu.

        Returns:
            str: Sonucu gösteren HTML formatında bir metin veya hata durumunda None.
        """
        target_url = None  # Hata durumunda URL'yi loglamak için tanımla
        try:
            # URL şablonunu kullanıcı adıyla formatla
            target_url = site['url'].format(username)

            # HEAD isteği genellikle sayfanın tamamını indirmeden var olup olmadığını
            # kontrol etmek için daha hızlıdır. allow_redirects=True ile yönlendirmeleri takip ederiz.
            async with session.head(target_url, timeout=10, allow_redirects=True) as response:
                # Başarılı durum kodları (2xx) veya yönlendirme sonrası başarı (3xx sonrası 2xx)
                # genellikle profilin var olduğunu gösterir.
                # response.url, son yönlendirilen URL'yi verir, bu gerçek profil URL'si olabilir.
                if 200 <= response.status < 400:
                    # HEAD başarılıysa, kullanıcı muhtemelen vardır.
                    # Yönlendirme olmuşsa, son URL'yi kullanalım.
                    found_url = str(response.url)
                    return self.format_result(username, site["name"], found_url, True)
                elif response.status == 404:  # Not Found - Kesin olarak yok.
                    return self.format_result(username, site["name"], target_url, False)
                # Bazı siteler HEAD isteğine izin vermez (405 Method Not Allowed) veya farklı yanıtlar verebilir.
                # Bu durumlarda GET denemek bir seçenek olabilir ancak şimdilik diğer 4xx/5xx hatalarını
                # bulunamadı olarak işaretliyoruz.
                elif response.status == 405:  # Method Not Allowed (HEAD desteklenmiyor olabilir)
                    # Alternatif olarak burada GET denenebilir, ama şimdilik bulunamadı sayalım.
                    return self.format_result(username, site["name"], target_url, False, " (HEAD Desteklenmiyor?)")
                else:
                    # Diğer hata durumları (403 Forbidden, 5xx Server Error vb.)
                    return self.format_result(username, site["name"], target_url, False,
                                              f" (Durum Kodu: {response.status})")

        except asyncio.TimeoutError:
            # İstek zaman aşımına uğradı
            # target_url burada None olabilir eğer formatlama başarısız olursa, bu yüzden site['url'] kullanalım
            fallback_url = target_url if target_url else site.get('url', 'Bilinmeyen URL')
            return self.format_result(username, site['name'], fallback_url, False, " (Zaman Aşımı)")
        except aiohttp.ClientError as e:
            # Bağlantı hataları, SSL hataları vb.
            fallback_url = target_url if target_url else site.get('url', 'Bilinmeyen URL')
            error_note = f" (Ağ Hatası: {type(e).__name__})"
            # Hata SSL ile ilgiliyse not ekleyelim (connector kontrolü kaldırıldı)
            if isinstance(e, (aiohttp.ClientConnectorError, aiohttp.ClientSSLError)):  # ClientConnectorError daha genel
                error_note += " - Bağlantı/SSL sorunu olabilir."
            return self.format_result(username, site["name"], fallback_url, False, error_note)
        except KeyError:
            # site['url'].format(username) başarısız oldu (URL şablonunda {} yoksa)
            self.error_signal.emit(f"URL formatlama hatası: {site['name']} - URL: {site.get('url', 'URL Yok')}")
            return None  # Hata GUI'ye gönderildi, sonuç döndürme
        except Exception as e:
            # Beklenmedik diğer tüm hataları yakala
            fallback_url = target_url if target_url else site.get('url', 'URL Yok')
            self.error_signal.emit(
                f"{site['name']} ({fallback_url}) web sitesi kontrolü sırasında beklenmedik hata: {e}")
            return None  # Hata GUI'ye gönderildi, sonuç döndürme
    def format_result(self, username, site_name, url, found, note=""):
        """
        Arama sonucunu GUI'de gösterilecek HTML formatına dönüştürür.

        Args:
            username (str): Aranan kullanıcı adı.
            site_name (str): Sitenin adı.
            url (str): Bulunan veya kontrol edilen URL.
            found (bool): Kullanıcı adının bulunup bulunmadığı.
            note (str, optional): Sonuca eklenecek ek not (örn. hata kodu). Defaults to "".

        Returns:
            str: HTML formatında sonuç metni.
        """
        if found:
            # Bulunduysa: Yeşil onay işareti, tıklanabilir link ve site adı
            icon = "✔️"
            # URL'yi HTML'e uygun hale getir (özel karakterler varsa diye)
            safe_url = url.replace('"', '&quot;')
            link = f'<a href="{safe_url}" style="text-decoration:none; color:#28a745; font-weight:bold;">{username}</a>' # Yeşil ve kalın link
            return f'<div style="margin-bottom: 3px;">{icon} {link} <span style="color:#555;">({site_name}) üzerinde bulundu</span>{note}</div>'
        else:
            # Bulunamadıysa: Kırmızı çarpı işareti, kullanıcı adı, site adı ve soluk renk
            icon = "❌"
            # Bulunamayanlar için URL'yi göstermeye gerek yok, sadece site adını belirtelim
            return f'<div style="color:#AAAAAA; margin-bottom: 3px;">{icon} {username} <span style="font-style: italic;">({site_name})</span> üzerinde bulunamadı{note}</div>' # Daha soluk ve italik site adı

    def run(self):
        """
        QThread'in ana çalışma fonksiyonu. Kullanıcı adı listesini işler.
        Her kullanıcı adı için asenkron arama fonksiyonunu (`run_search_for_user`) çalıştırır.
        """
        total_usernames = len(self.usernames)
        processed_usernames = 0

        for username in self.usernames:
            # Her döngü başında thread'in hala çalışıyor olması gerekip gerekmediğini kontrol et
            if not self.is_running:
                self.error_signal.emit("Arama işlemi durduruldu.")
                break # Döngüden çık

            username = username.strip() # Kullanıcı adının başındaki/sonundaki boşlukları temizle
            if username: # Boş kullanıcı adlarını atla
                self.result_signal.emit(f'<h4>{username} için arama yapılıyor...</h4>') # Kullanıcı bazlı başlık
                try:
                    # Her kullanıcı adı için yeni bir asyncio olay döngüsü başlatıp
                    # asenkron arama fonksiyonunu çalıştırıyoruz.
                    # asyncio.run(), verilen async fonksiyon tamamlanana kadar bekler.
                    asyncio.run(self.run_search_for_user(username, self.category, self.sites_data))
                except Exception as e:
                    # asyncio.run veya run_search_for_user içinde beklenmedik bir hata olursa
                    self.error_signal.emit(f"'{username}' aranırken kritik hata: {str(e)}")

                # Kullanıcı adının işlenmesi bittiğinde ilerlemeyi güncelle
                processed_usernames += 1
                # İlerlemeyi yüzde olarak hesapla ve GUI'ye gönder
                progress = int((processed_usernames / total_usernames) * 100)
                self.progress_signal.emit(progress)

        # Döngü bittiğinde (ya tüm kullanıcılar işlendi ya da durduruldu)
        if self.is_running:
             # Eğer durdurulmadıysa, işlemin normal şekilde bittiğini bildir
             self.finished_signal.emit()
        # `run` metodu bittiğinde QThread otomatik olarak sonlanır.

    def stop(self):
        """
        İş parçacığını durdurmak için çağrılır. 'is_running' bayrağını False yapar.
        Bu bayrak, `run` ve `run_search_for_user` içindeki döngülerde kontrol edilir.
        """
        self.is_running = False
        self.error_signal.emit("Durdurma sinyali alındı...") # Kullanıcıya bilgi ver

# --- Ana Uygulama Penceresi ---
class DedektifUygulama(QWidget):
    """
    Ana PyQt5 uygulama penceresi. Kullanıcı arayüzünü oluşturur,
    kullanıcı girdilerini alır ve SearchWorker'ı başlatıp yönetir.
    """
    def __init__(self):
        """ Pencereyi ve içindeki bileşenleri başlatır. """
        super().__init__()

        # Uygulama ikonunu ayarla (opsiyonel)
        self._set_window_icon()

        self.setWindowTitle("Dedektif Kullanıcı Adı Arama")
        self.setGeometry(100, 100, 650, 550) # Pencere başlangıç konumu ve boyutu

        # Arama yapılacak sitelerin listesi.
        # Her site bir sözlüktür ve şu anahtarları içerebilir:
        # - name: Sitenin kullanıcı arayüzünde görünecek adı (Zorunlu).
        # - url: Kullanıcı adını formatlamak için URL şablonu ('{}' yer tutucusunu içermeli) (Zorunlu).
        # - api: Bu site için API mi kullanılacak (True/False). Varsayılan False.
        # - category: Sitenin ait olduğu kategori (Filtreleme için). (Zorunlu).
        # - ssl_verify: Bu siteye bağlanırken SSL sertifikası doğrulaması yapılsın mı?
        #               Varsayılan True. False yapılırsa güvenlik riski olabilir.
        self.sites_data = [
            {"name": "GitHub", "url": "https://api.github.com/users/{}", "api": True, "category": "Sosyal Medya"},
            {"name": "Reddit", "url": "https://www.reddit.com/user/{}", "api": False, "category": "Forumlar"},
            {"name": "Instagram", "url": "https://www.instagram.com/{}/", "api": False, "category": "Sosyal Medya"},
            {"name": "X (Twitter)", "url": "https://x.com/{}", "api": False, "category": "Sosyal Medya"},
            {"name": "LinkedIn", "url": "https://www.linkedin.com/in/{}/", "api": False, "category": "Sosyal Medya"}, # Genellikle özel profiller bulunmaz
            {"name": "9GAG", "url": "https://9gag.com/u/{}", "api": False, "category": "Forumlar"},
            {"name": "1337x", "url": "https://1337x.to/user/{}/", "api": False, "category": "Forumlar"},
            {"name": "Twitch", "url": "https://www.twitch.tv/{}", "api": False, "category": "Video Platformları"},
            {"name": "Pinterest", "url": "https://www.pinterest.com/{}/", "api": False, "category": "Sosyal Medya"},
            {"name": "Facebook", "url": "https://www.facebook.com/{}", "api": False, "category": "Sosyal Medya"}, # Genellikle doğrudan kullanıcı adı ile bulunmaz
            {"name": "YouTube", "url": "https://www.youtube.com/@{}", "api": False, "category": "Video Platformları"}, # Yeni @handle formatı
            {"name": "Tumblr", "url": "https://{}.tumblr.com/", "api": False, "category": "Sosyal Medya"}, # Subdomain kullanır
            {"name": "Flickr", "url": "https://www.flickr.com/people/{}/", "api": False, "category": "Sosyal Medya"},
            {"name": "SoundCloud", "url": "https://soundcloud.com/{}", "api": False, "category": "Sosyal Medya"},
            {"name": "Steam", "url": "https://steamcommunity.com/id/{}", "api": False, "category": "Sosyal Medya"}, # Custom URL için
            # {"name": "Steam Profile", "url": "https://steamcommunity.com/profiles/{}", "api": False, "category": "Sosyal Medya"}, # SteamID64 için
            {"name": "DeviantArt", "url": "https://www.deviantart.com/{}", "api": False, "ssl_verify": False, "category": "Forumlar"}, # SSL sorunu olabilir
            {"name": "VK", "url": "https://vk.com/{}", "api": False, "category": "Sosyal Medya"},
            {"name": "Medium", "url": "https://medium.com/@{}", "api": False, "category": "Sosyal Medya"}, # @ işareti kullanır
            {"name": "HackerNews", "url": "https://news.ycombinator.com/user?id={}", "api": False, "category": "Forumlar"},
            {"name": "Vimeo", "url": "https://vimeo.com/{}", "api": False, "category": "Video Platformları"},
            {"name": "TikTok", "url": "https://www.tiktok.com/@{}", "api": False, "category": "Sosyal Medya"}, # @ işareti kullanır
            {"name": "MyAnimeList", "url": "https://myanimelist.net/profile/{}", "api": False, "category": "Sosyal Medya"},
            {"name": "Dribbble", "url": "https://dribbble.com/{}", "api": False, "category": "Sosyal Medya"},
            {"name": "Behance", "url": "https://www.behance.net/{}", "api": False, "category": "Sosyal Medya"},
            {"name": "Foursquare", "url": "https://foursquare.com/{}", "api": False, "category": "Sosyal Medya"},
            {"name": "Dailymotion", "url": "https://www.dailymotion.com/{}", "api": False, "category": "Video Platformları"},
            {"name": "Unsplash", "url": "https://unsplash.com/@{}", "api": False, "category": "Sosyal Medya"}, # @ işareti kullanır
            {"name": "ProductHunt", "url": "https://www.producthunt.com/@{}", "api": False, "category": "Sosyal Medya"}, # @ işareti kullanır
            {"name": "Telegram", "url": "https://t.me/{}", "api": False, "category": "Sosyal Medya"}, # Kanal/Kullanıcı linki
            {"name": "Snapchat", "url": "https://www.snapchat.com/add/{}", "api": False, "category": "Sosyal Medya"},
            {"name": "Quora", "url": "https://www.quora.com/profile/{}", "api": False, "category": "Sosyal Medya"},
            {"name": "OK.ru", "url": "https://ok.ru/{}", "api": False, "category": "Sosyal Medya"},
         ]
         # URL şablonlarının doğruluğunu kontrol et (geliştirme aşamasında yardımcı olabilir)
        # for site in self.sites_data:
        #     if "{}" not in site['url']:
        #         print(f"Uyarı: '{site['name']}' için URL şablonunda '{{}}' bulunamadı: {site['url']}")

        self.search_thread = None # Arama iş parçacığını tutacak değişken
        self.results = []         # Kaydetmek için temizlenmiş sonuçları tutacak liste
        self.initUI()             # Kullanıcı arayüzünü oluştur

    def _set_window_icon(self):
        """ Uygulama ikonunu ayarlar (varsa). """
        try:
            # Betiğin çalıştığı dizini bul
            script_dir = os.path.dirname(os.path.realpath(__file__))
            icon_path = os.path.join(script_dir, 'icon.ico')
            if os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
            else:
                # İkon bulunamazsa bir uyarı yazdırabiliriz (opsiyonel)
                print(f"Bilgi: Uygulama ikonu ('icon.ico') bulunamadı: {icon_path}")
        except Exception as e:
            print(f"İkon ayarlanırken hata oluştu: {e}")

    def initUI(self):
        """ Kullanıcı arayüzü bileşenlerini oluşturur ve düzenler. """
        main_layout = QVBoxLayout(self) # Ana dikey düzenleyici

        # --- Kullanıcı Adı Giriş Alanı ---
        user_input_group = QGroupBox("Aranacak Kullanıcı Adları")
        user_input_group.setStyleSheet("""
        QGroupBox {
            border: 1px solid #ccc;
            border-radius: 5px;
            margin-top: 1ex; /* Başlık için üst boşluk */
            background-color: #f9f9f9;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left; /* Başlığı sola al */
            padding: 0 5px 0 5px;
            margin-left: 10px; /* Sol boşluk */
            font-size: 10pt;
            font-weight: bold;
            color: #333;
        }
        """)
        user_input_layout = QVBoxLayout()
        self.username_input_label = QLabel("Kullanıcı adlarını virgül (,) ile ayırarak girin:")
        self.username_input_label.setFont(QFont('Segoe UI', 9)) # Daha modern font
        self.username_input_label.setStyleSheet("color: #555; margin-bottom: 3px;")

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("örnek: kullanici1, test_user, baska_bir_kullanici")
        self.username_input.setFont(QFont('Segoe UI', 10))
        # Enter tuşuna basıldığında da aramayı başlat
        self.username_input.returnPressed.connect(self.start_search)
        self.username_input.setStyleSheet("""
        QLineEdit {
            background-color: #fff;
            border: 1px solid #ccc;
            padding: 7px;
            border-radius: 4px;
            color: #333;
        }
        QLineEdit:focus {
            border: 1px solid #0078d4; /* Odaklandığında mavi kenarlık */
        }
        """)
        user_input_layout.addWidget(self.username_input_label)
        user_input_layout.addWidget(self.username_input)
        user_input_group.setLayout(user_input_layout)

        # --- Kontrol Alanı (Kategori ve Butonlar) ---
        control_layout = QHBoxLayout() # Yatay düzenleyici

        # Kategori Seçimi
        category_group = QGroupBox("Kategori Filtresi")
        category_group_layout = QHBoxLayout()
        self.category_selector = QComboBox()
        # Kategorileri dinamik olarak site verisinden alabiliriz veya sabit tutabiliriz.
        # Şimdilik sabit tutalım:
        categories = ["Hepsi"] + sorted(list(set(site['category'] for site in self.sites_data)))
        self.category_selector.addItems(categories)
        self.category_selector.setFont(QFont('Segoe UI', 10))
        self.category_selector.setStyleSheet("""
        QComboBox {
            background-color: #fff; border: 1px solid #ccc; padding: 6px; border-radius: 4px; color: #333; min-width: 150px;
        }
        QComboBox::drop-down { border: none; }
        QComboBox QAbstractItemView { /* Açılır liste stili */
            background-color: white;
            border: 1px solid #ccc;
            selection-background-color: #0078d4; /* Seçim rengi */
        }
        """)
        category_group_layout.addWidget(self.category_selector)
        category_group.setLayout(category_group_layout)
        category_group.setStyleSheet(user_input_group.styleSheet()) # Benzer stil

        # Butonlar
        button_group = QGroupBox("İşlemler")
        button_group_layout = QHBoxLayout()
        self.search_button = QPushButton("🔍 Ara") # İkon ekleyelim
        self.search_button.setFont(QFont('Segoe UI', 10, QFont.Bold))
        self.search_button.clicked.connect(self.start_search)
        self.search_button.setMinimumHeight(32) # Buton yüksekliği
        self.search_button.setStyleSheet("""
        QPushButton{ background-color: #28a745; color: white; padding: 8px 12px; border-radius: 5px; border: none; }
        QPushButton:hover{ background-color: #218838; }
        QPushButton:pressed{ background-color: #1e7e34; }
        QPushButton:disabled{ background-color: #cccccc; color: #666666; }
        """)

        self.save_button = QPushButton("💾 Kaydet") # İkon ekleyelim
        self.save_button.setFont(QFont('Segoe UI', 10, QFont.Bold))
        self.save_button.clicked.connect(self.save_results)
        self.save_button.setMinimumHeight(32)
        self.save_button.setStyleSheet("""
        QPushButton{ background-color: #007bff; color: white; padding: 8px 12px; border-radius: 5px; border: none; }
        QPushButton:hover{ background-color: #0069d9; }
        QPushButton:pressed{ background-color: #005cbf; }
         """)
        button_group_layout.addWidget(self.search_button)
        button_group_layout.addWidget(self.save_button)
        button_group.setLayout(button_group_layout)
        button_group.setStyleSheet(user_input_group.styleSheet()) # Benzer stil

        control_layout.addWidget(category_group)
        control_layout.addWidget(button_group)
        control_layout.addStretch(1) # Butonları sola yasla

        # --- İlerleme Çubuğu ---
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False) # Yüzde yazısını gizle
        self.progress_bar.setStyleSheet("""
        QProgressBar{
            border: 1px solid #bbb;
            border-radius: 5px;
            background: #e0e0e0;
            height: 12px; /* Biraz daha ince */
            text-align: center; /* Yazı görünürse ortala */
            color: #333;
        }
        QProgressBar::chunk{
            background-color: #28a745; /* Arama butonuyla aynı yeşil */
            border-radius: 4px;
            margin: 0.5px;
        }
        """)

        # --- Sonuç Alanı ---
        self.result_area = QTextBrowser() # HTML gösterebilen ve linkleri açabilen alan
        self.result_area.setFont(QFont('Segoe UI', 10))
        self.result_area.setStyleSheet("""
        QTextBrowser {
            background-color: #ffffff;
            border-radius: 5px;
            padding: 10px;
            border: 1px solid #ccc;
            color: #333;
        }
        """)
        self.result_area.setOpenExternalLinks(True) # Linklerin varsayılan tarayıcıda açılmasını sağlar
        self.result_area.setReadOnly(True)
        self.result_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn) # Kaydırma çubuğu her zaman görünsün

        # Bileşenleri ana düzene ekle
        main_layout.addWidget(user_input_group)
        main_layout.addLayout(control_layout)
        main_layout.addWidget(self.progress_bar)
        main_layout.addWidget(self.result_area, 1) # Sonuç alanı genişlesin (stretch factor 1)

        self.setLayout(main_layout)
        self.username_input.setFocus() # Başlangıçta imleç kullanıcı adı girişinde olsun

    def start_search(self):
        """
        Kullanıcı 'Ara' butonuna tıkladığında veya Enter'a bastığında tetiklenir.
        Girdileri alır, SearchWorker'ı başlatır ve UI'yi günceller.
        """
        # Eğer önceki arama hala çalışıyorsa, kullanıcıya sor ve durdurma seçeneği sun
        if self.search_thread and self.search_thread.isRunning():
            reply = QMessageBox.question(self, 'Devam Eden Arama',
                                         "Zaten devam eden bir arama var. Durdurup yenisini başlatmak ister misiniz?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.search_thread.stop() # İş parçacığına durma sinyali gönder
                # wait() thread bitene kadar bekler, GUI donabilir, kısa bir süre için kabul edilebilir.
                # Alternatif: Durdurma sinyali sonrası hemen yeni aramayı başlat, eski thread kendi kendine durur.
                # Şimdilik wait() kullanalım, daha güvenli.
                if not self.search_thread.wait(1000): # Max 1 saniye bekle
                    QMessageBox.warning(self, "Uyarı", "Önceki arama zamanında durdurulamadı.")
                else:
                    QMessageBox.information(self, "Bilgi", "Önceki arama durduruldu.")
                self.search_button.setEnabled(True) # Butonu tekrar etkinleştir
            else:
                return # Yeni aramayı başlatma

        # Kullanıcı adı girdisini al ve temizle
        usernames_text = self.username_input.text()
        if not usernames_text.strip():
            QMessageBox.warning(self, "Giriş Hatası", "Lütfen aranacak en az bir kullanıcı adı girin.")
            return

        # Virgülle ayrılmış kullanıcı adlarını listeye dönüştür, boşlukları temizle
        usernames = [u.strip() for u in usernames_text.split(',') if u.strip()]
        if not usernames:
             QMessageBox.warning(self, "Giriş Hatası", "Geçerli bir kullanıcı adı bulunamadı. Lütfen kontrol edin.")
             return

        # Arayüzü arama için hazırla
        self.result_area.clear() # Önceki sonuçları temizle
        self.results = [] # Kaydedilecek temiz sonuç listesini sıfırla
        self.progress_bar.setValue(0) # İlerleme çubuğunu sıfırla
        self.search_button.setEnabled(False) # Arama sırasında butonu devre dışı bırak
        self.result_area.append("<h3>Arama Başlatılıyor...</h3>") # Başlangıç mesajı

        # Seçilen kategoriyi al
        selected_category = self.category_selector.currentText()

        # Yeni SearchWorker thread'ini oluştur ve başlat
        # Worker'a formatlanmamış site verisini gönderiyoruz, formatlama worker içinde yapılacak.
        self.search_thread = SearchWorker(usernames, selected_category, self.sites_data)

        # Worker'dan gelen sinyalleri ilgili GUI metodlarına bağla
        self.search_thread.result_signal.connect(self.append_result)
        self.search_thread.progress_signal.connect(self.update_progress)
        self.search_thread.finished_signal.connect(self.search_finished)
        self.search_thread.error_signal.connect(self.show_error)

        # Thread'i başlat (bu, run() metodunu çağırır)
        self.search_thread.start()

    def update_progress(self, value):
        """ SearchWorker'dan gelen ilerleme sinyalini alır ve progress bar'ı günceller. """
        self.progress_bar.setValue(value)

    def append_result(self, result_html):
        """ SearchWorker'dan gelen sonuç (HTML) sinyalini alır, GUI'ye ekler ve temiz halini listeye kaydeder. """
        self.result_area.append(result_html) # HTML olarak QTextBrowser'a ekle
        # İmleci sona değil başa taşımak sonuçların yukarıdan aşağı akmasını sağlar gibi görünür ama
        # append zaten sona ekler. Eğer yeni sonuçların üstte görünmesi isteniyorsa insertHtml kullanılmalı.
        # Şimdilik append ile devam edelim, doğal akış aşağı doğrudur.
        # self.result_area.moveCursor(QTextCursor.End) # İmleci sona taşı (append zaten yapar)

        # Kaydetmek için HTML'den arındırılmış metni oluştur
        try:
            # Basit HTML etiketlerini temizle
            clean_text = re.sub('<[^>]+>', '', result_html)
            # Özel karakterleri/ikonları değiştir (+ bulundu, - bulunamadı)
            clean_text = clean_text.replace("✔️", "[+]").replace("❌", "[-]")
            # Fazla boşlukları temizle ve listeye ekle
            self.results.append(clean_text.strip())
        except Exception as e:
            # Temizleme sırasında hata olursa logla (nadiren olmalı)
            print(f"Sonuç metni temizlenirken hata: {e} - Metin: {result_html}")

    def search_finished(self):
        """ SearchWorker normal şekilde bittiğinde çağrılır. """
        self.search_button.setEnabled(True) # Butonu tekrar etkinleştir
        if self.search_thread and self.search_thread.is_running:
            # Bu durum aslında olmamalı, finished sinyali thread durduktan sonra gelmeli.
             QMessageBox.information(self, "Bilgi", "Arama tamamlandı!")
        elif self.search_thread and not self.search_thread.is_running:
             # Eğer thread 'stop' ile durdurulduysa farklı bir mesaj verebiliriz
             # Ancak 'finished_signal' sadece normal bitişte emit ediliyor.
             # Bu yüzden burası sadece normal bitişte çalışır.
             QMessageBox.information(self, "Bilgi", "Arama Tamamlandı!")
             self.progress_bar.setValue(100) # Bitişte %100 yapalım
        else:
             # Thread yoksa veya beklenmedik durum
              QMessageBox.information(self, "Bilgi", "İşlem tamamlandı.")


    def show_error(self, error_message):
         """ SearchWorker'dan gelen hata sinyalini alır ve GUI'de kırmızı renkte gösterir. """
         self.result_area.append(f'<div style="color:red; font-weight:bold;">HATA: {error_message}</div>')
         # Hata durumunda da imleci sona taşıyalım
         self.result_area.moveCursor(QTextCursor.End)

    def save_results(self):
        """
        Arama sonuçlarını (temizlenmiş metin listesini) bir dosyaya kaydeder.
        Kullanıcıya dosya kaydetme dialoğu gösterir.
        """
        if not self.results:
            QMessageBox.warning(self,"Kaydetme Hatası","Kaydedilecek sonuç bulunamadı. Lütfen önce bir arama yapın.")
            return

        # Dosya adı önerisi oluştur (ilk kullanıcı adı ile)
        try:
            first_user = self.username_input.text().split(',')[0].strip()
            default_filename = f"dedektif_sonuc_{first_user}.txt" if first_user else "dedektif_sonuclar.txt"
        except:
            default_filename = "dedektif_sonuclar.txt"

        # QFileDialog kullanarak kullanıcıdan dosya yolunu al
        options = QFileDialog.Options()
        # options |= QFileDialog.DontUseNativeDialog # İsteğe bağlı: Platformun kendi dialogunu kullanma
        filename, _ = QFileDialog.getSaveFileName(self,
                                                  "Arama Sonuçlarını Kaydet",
                                                  default_filename, # Önerilen dosya adı
                                                  "Metin Dosyaları (*.txt);;Tüm Dosyalar (*)",
                                                  options=options)

        if filename: # Kullanıcı bir dosya adı seçtiyse (iptal etmediyse)
            # Dosya adının .txt ile bittiğinden emin ol (eğer seçili filtre txt değilse)
            if not filename.lower().endswith(".txt") and ".txt" in _.lower():
                 filename += ".txt"
            elif "." not in os.path.basename(filename): # Uzantı yoksa .txt ekle
                filename += ".txt"

            try:
                # Dosyayı yazdırma modunda ('w') ve UTF-8 kodlamasıyla aç
                with open(filename, 'w', encoding='utf-8') as file:
                     # Temizlenmiş sonuç listesindeki her satırı dosyaya yaz
                    for line in self.results:
                        file.write(line + "\n") # Her sonucu yeni bir satıra yaz
                # Başarılı kaydetme mesajı
                QMessageBox.information(self, "Başarılı", f"Sonuçlar başarıyla '{os.path.basename(filename)}' dosyasına kaydedildi!")
            except Exception as e:
                # Dosya yazma sırasında bir hata olursa kullanıcıyı bilgilendir
                QMessageBox.critical(self, "Dosya Yazma Hatası", f"Dosya kaydedilirken bir hata oluştu:\n{str(e)}")

    # --- Pencere Kapatma Olayı ---
    def closeEvent(self, event):
        """
        Kullanıcı pencereyi kapattığında tetiklenir.
        Eğer arama thread'i hala çalışıyorsa, onu durdurmaya çalışır.
        """
        if self.search_thread and self.search_thread.isRunning():
            self.search_thread.stop() # Durdurma sinyali gönder
            # Thread'in bitmesini bekleyelim ki kaynaklar serbest bırakılsın.
            # Kısa bir timeout ile bekleyelim, tamamen bitmezse de uygulamayı kapatalım.
            if not self.search_thread.wait(500): # 500 milisaniye bekle
                 print("Uyarı: Arama iş parçacığı kapatılırken zamanında durmadı.")
            else:
                 print("Arama iş parçacığı başarıyla durduruldu.")
        event.accept() # Pencerenin kapanmasına izin ver


# --- Uygulama Başlangıç Noktası ---
if __name__ == '__main__':
    # PyQt uygulamasını başlat
    app = QApplication(sys.argv)

    # Windows'ta asyncio ve PyQt/GUI kütüphaneleri birlikte kullanılırken
    # bazen olay döngüsü (event loop) politikası sorun çıkarabilir.
    # Bu ayar, uyumluluğu artırmaya yardımcı olabilir.
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    # Ana uygulama penceremizi oluştur
    dedektif_window = DedektifUygulama()
    # Pencereyi göster
    dedektif_window.show()

    # Uygulamanın olay döngüsünü başlat ve çıkış kodunu sisteme ilet
    sys.exit(app.exec_())
