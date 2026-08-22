# Güvenlik Politikası

## Desteklenen sürüm

Güvenlik düzeltmeleri güncel `main` dalı ve son yayımlanan sürüm için hazırlanır.

## Bildirim

Hassas bir güvenlik sorununu herkese açık issue içinde exploit ayrıntılarıyla paylaşmayın.
GitHub deposundaki **Security → Report a vulnerability** özel bildirim akışını kullanın.
Bu özellik kullanılamıyorsa, yalnızca yeniden üretim için gerekli en az bilgiyi içeren bir
issue açıp özel iletişim kanalı isteyin.

Bildirimde şunlar bulunmalıdır:

- Etkilenen sürüm veya commit.
- Güvenli ve en küçük yeniden üretim adımları.
- Beklenen ve gözlenen davranış.
- Olası etki ve önerilen düzeltme.

Gerçek kişilere ait kullanıcı adlarını, erişim tokenlarını, cookie'leri veya gereksiz
kişisel verileri eklemeyin.

## Kapsam

Özellikle şu sınıflar güvenlik sorunu olarak değerlendirilir:

- TLS doğrulamasının, host allowlist'inin veya kullanım onayının atlanması.
- İzin verilen istek, eşzamanlılık, timeout veya redirect sınırlarının aşılması.
- Ortam proxy'si veya beklenmeyen hostname üzerinden istek gönderilmesi.
- Terminal/GUI kontrol karakteri enjeksiyonu veya gizli yanıt içeriğinin saklanması.
- Ağsız testlerin dış sisteme bağlanabilmesi.

Platformların değişen HTTP davranışından kaynaklanan yanlış pozitif/negatif sonuçlar,
tek başına güvenlik açığı değildir; yine de dokümantasyon veya sınıflandırma iyileştirmesi
olarak raporlanabilir.
