# Changelog

Bu projedeki önemli değişiklikler bu dosyada belgelenir.

## [3.0.0] - 2026-08-22

### Added

- Kurulabilir `src/dedektif_osint` paketi.
- Aynı motoru kullanan CLI ve isteğe bağlı PyQt5 arayüzü.
- Açık kullanım onayı, katı kullanıcı adı doğrulaması ve kaynak sınırları.
- `found`, `not_found`, `unknown`, `error` ve `cancelled` sonuç modeli.
- Terminal güvenli text, strict JSON ve JSONL raporlama.
- Ağ erişimini engelleyen test altyapısı ve regresyon testleri.
- Python 3.10–3.13 GitHub Actions matrisi.
- Lisans, güvenlik politikası ve katkı rehberi.

### Changed

- TLS doğrulamasını kapatan ve tüm platformları sınırsız eşzamanlı kontrol eden eski
  istek yolu kaldırıldı.
- Katalog, sabit HTTPS host allowlist'i kullanan küçük bir platform kümesine indirildi.
- HTTP 200/404 dışındaki sonuçlar sessizce kaybolmak yerine açıkça `unknown` olur.
- Anti-blocking, WAF bypass ve tarayıcı taklidi iddiaları kaldırıldı.

### Security

- Ortam proxy'leri ve redirect takibi kapatıldı.
- Yanıt gövdeleri tutulmuyor; hata ayrıntıları yalnızca istisna türüyle raporlanıyor.
- Hiçbir giriş, crawling, yeniden deneme veya koruma atlatma davranışı bulunmuyor.
