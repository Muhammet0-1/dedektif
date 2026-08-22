# Dedektif

Dedektif, en fazla beş kullanıcı adını küçük ve açıkça tanımlanmış bir platform
kataloğundaki kamusal profil uç noktalarında kontrol eden savunma amaçlı bir OSINT
istemcisidir. Kurulabilir Python paketi, komut satırı arayüzü ve isteğe bağlı PyQt5
masaüstü arayüzü aynı doğrulanmış motoru kullanır.

> Bir HTTP başarı durumu yalnızca **aday profil** sinyalidir. Kimlik, hesap sahipliği,
> kişinin aynı kişi olduğu veya içeriğin doğru olduğu sonucunu kanıtlamaz.

## Güvenlik sınırları

- Bir çalıştırmada en fazla 5 kullanıcı adı ve katalogdaki 9 uç nokta kontrol edilir.
- Eşzamanlı istek sayısı 4, zaman aşımı 20 saniye ve istekler arası gecikme 1 saniye
  ile sınırlandırılmıştır.
- TLS sertifikası ve hostname doğrulaması zorunludur.
- Ortam proxy'leri kullanılmaz ve HTTP yönlendirmeleri izlenmez.
- Cookie saklama kapalıdır; platformlar arasında oturum durumu taşınmaz.
- Yeniden deneme, crawling, CAPTCHA/WAF atlatma, tarayıcı taklidi, giriş yapma veya
  korumalı veriye erişme davranışı yoktur.
- Açıklayıcı `Dedektif/3.0` User-Agent değeri kullanılır.
- Yanıt gövdeleri analiz edilmez veya saklanmaz; yalnızca HTTP durum kodu ve varsa
  yönlendirme sinyali değerlendirilir.
- Kullanıcı, kamusal verileri hukuka ve ilgili platform koşullarına uygun kullanacağını
  açıkça onaylamadan istek gönderilemez.

## Sonuç durumları

| Durum | Anlamı |
|---|---|
| `found` | Uç nokta 2xx döndürdü; yalnızca aday profil sinyali |
| `not_found` | Uç nokta 404 veya 410 döndürdü |
| `unknown` | Yönlendirme, erişim kısıtı, hız sınırı veya başka belirsiz durum |
| `error` | Sınırlandırılmış HTTP işlemi tamamlanamadı |
| `cancelled` | Kontrol gönderilmeden önce kullanıcı tarafından iptal edildi |

Platformların davranışları zamanla değişebilir. Giriş duvarları, bot korumaları,
coğrafi farklılıklar, rate limit ve herkese 200 döndüren sayfalar yanlış pozitif veya
yanlış negatif üretebilir. Dedektif bu belirsizliği gizlemez.

## Kurulum

Python 3.10–3.13 desteklenir.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e .
```

Masaüstü arayüzü için:

```bash
.venv/bin/python -m pip install -e '.[gui]'
```

## CLI kullanımı

Katalog:

```bash
.venv/bin/dedektif catalog
```

Kamusal profil kontrolü:

```bash
.venv/bin/dedektif check alice bob \
  --acknowledge-public-data \
  --category development \
  --format json
```

Tüm seçenekler:

```bash
.venv/bin/dedektif check --help
```

`--fail-on-found`, aday profil bulunduğunda çıkış kodunu `3` yapar. Bu seçenek CI veya
yerel doğrulama akışlarında yalnızca sinyal üretmek içindir; güvenlik bulgusu anlamına
gelmez.

## Masaüstü arayüzü

```bash
.venv/bin/dedektif-gui
```

Kaynak checkout'undan eski başlatıcı da kullanılabilir:

```bash
.venv/bin/python dedektif.py
```

Arayüz, kullanıcı adlarını doğrular, açık kullanım onayı ister, kategori ve kaynak
sınırlarını gösterir, iptal isteğini çalışan motora iletir ve sonuçları düzenlenemez bir
tabloda sunar.

## Katalog

Katalog; GitHub, GitLab, Reddit, Twitch, Steam Community, Medium, Telegram, Pastebin ve
Wikipedia için sabit HTTPS uç noktaları içerir. Instagram, X, Spotify ve benzeri
giriş/anti-bot/redirect davranışı sık değişen servisler, güvenilir olmayan ikili sonuçlar
üretmemek için varsayılan katalogdan çıkarılmıştır.

## Geliştirme ve doğrulama

İlk kez, Codex oturumunu başlatmadan önce geliştirme ortamını kurun:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
make bootstrap PYTHON=.venv/bin/python
```

Sonra yerelde ve her Codex değişikliğinden sonra tek kanonik komutu çalıştırın:

```bash
make verify PYTHON=.venv/bin/python
```

GitHub Actions da aynı `make verify` hedefini Python 3.10, 3.11, 3.12 ve 3.13 için
çalıştırır. Hedef; format, lint, strict mypy, ağsız testler, byte compilation, sdist,
wheel, paket içeriği ve ağsız CLI self-test kontrollerini kapsar. Paketler, geliştirme
bağımlılıklarıyla yerel olarak kurulan build backend'i kullanılarak `--no-isolation`
seçeneğiyle oluşturulur; doğrulama sırasında paket indeksine erişilmez.

## Etik ve hukuki kullanım

Yalnızca hukuken erişme ve işleme hakkınız olan kamusal verilerde kullanın. İlgili
platformların kullanım koşullarına, mahremiyet hükümlerine, yerel mevzuata ve kurum
politikalarına uyun. Sonuçları taciz, profilleme, kimlik ilişkilendirme, toplu veri
hasadı veya erişim kontrollerini aşmak için kullanmayın.

Güvenlik bildirimi için [SECURITY.md](SECURITY.md), katkı akışı için
[CONTRIBUTING.md](CONTRIBUTING.md) dosyasına bakın.

## Lisans

[MIT License](LICENSE) — Copyright (c) 2026 Muhammet0-1
