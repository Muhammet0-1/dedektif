# Katkıda bulunma

Katkılar küçük, incelenebilir ve güvenli varsayılanları koruyan değişiklikler olmalıdır.

## Yerel akış

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
make bootstrap PYTHON=.venv/bin/python
make verify PYTHON=.venv/bin/python
```

Pull request açmadan önce son komutun eksiksiz geçtiğini doğrulayın. GitHub Actions aynı
hedefi desteklenen dört Python sürümünde çalıştırır.

## Katalog değişiklikleri

Yeni uç nokta eklemek için:

- Uç nokta herkese açık ve HTTPS olmalıdır.
- Tek bir `GET` yeterli olmalı; giriş, cookie, token, redirect veya crawling gerektirmemelidir.
- Sabit hostname ve açık profil URL şablonu kullanılmalıdır.
- Yanlış pozitif/negatif davranışı README'de belgelenmelidir.
- Gerçek ağ kullanmayan transport ve sınıflandırma testleri eklenmelidir.

CAPTCHA/WAF atlatma, tarayıcı taklidi, proxy rotasyonu, kimlik bilgisi kullanımı, rate-limit
atlatma, toplu veri hasadı veya gizli/korumalı veri erişimi kabul edilmez.

## Kod kalitesi

- Yeni davranış için regresyon testi ekleyin.
- Hataları sessizce yutmayın ve hassas ayrıntıları rapora taşımayın.
- Ağ erişimini testlerde mock'layın; `tests/conftest.py` dış erişimi fail-closed engeller.
- Kullanıcı girdisini URL, terminal ve GUI sınırlarında doğrulayın veya güvenli biçimde sunun.
- Commit mesajlarını emir kipinde ve tek amaçlı tutun.
