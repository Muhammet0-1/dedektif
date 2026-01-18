# 🕵️‍♂️ Dedektif - OSINT Username Search Tool

![Python](https://img.shields.io/badge/Python-3.8%2B-blue?style=for-the-badge&logo=python)
![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20Windows-lightgrey?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)

**Dedektif**, siber güvenlik uzmanları ve OSINT araştırmacıları için geliştirilmiş, yüksek hızlı ve asenkron çalışan bir kullanıcı adı tespit aracıdır. Sosyal medya, forumlar ve kodlama platformlarında hedef kullanıcı adının izini sürer.

## 🚀 Özellikler

* **Asenkron Mimari:** `aiohttp` ve `asyncio` kullanarak saniyeler içinde onlarca siteyi tarar.
* **Modern GUI:** PyQt5 tabanlı, kullanıcı dostu ve "Dark Mode" temalı arayüz.
* **Akıllı Filtreleme:** Sadece "Sosyal Medya", "Oyun" veya "Yazılım" kategorilerinde arama yapabilme.
* **Anti-Blocking:** User-Agent rotasyonu ve header manipülasyonu ile bot korumalarını atlatır.
* **Raporlama:** Sonuçları temiz bir `.txt` formatında dışa aktarma.

## 🛠️ Kurulum

Arch Linux ve diğer dağıtımlar için:

```bash
# Projeyi klonlayın
git clone [https://github.com/Muhammet0-1/dedektif.git](https://github.com/Muhammet0-1/dedektif.git)
cd dedektif

# Sanal ortam oluşturun (Önerilen)
python -m venv venv
source venv/bin/activate

# Gereksinimleri yükleyin
pip install aiohttp PyQt5

💻 Kullanım

Aracı başlatmak için terminale şunu yazın:
Bash

python dedektif.py

    Hedef kullanıcı adlarını virgülle ayırarak girin (örn: testuser, admin123).

    Kategori seçin (veya "Hepsi" diyerek full tarama yapın).

    TARAMAYI BAŞLAT butonuna basın ve sonuçları canlı izleyin.

⚠️ Yasal Uyarı

Bu yazılım sadece açık kaynak istihbaratı (OSINT) eğitimleri ve yasal güvenlik testleri için geliştirilmiştir. Başkalarının gizliliğini ihlal etmek veya taciz amacıyla kullanılması kesinlikle yasaktır. Geliştirici, aracın kötüye kullanımından sorumlu tutulamaz.
