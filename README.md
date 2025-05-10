# Academic-PDF-Anonymizer-Platform
# 🕵️ Academic PDF Anonymizer Platform  Bu Flask tabanlı sistem, akademik makaleleri anonimleştirerek çift kör hakem değerlendirme süreçlerinde kullanılmak üzere geliştirilmiştir.

## 🔍 Özellikler

- 📁 PDF yükleme ve analiz
- 🧠 İsim, kurum, iletişim ve görsel sansürleme (`censorship.py`, `anonymizer.py`)
- 🔐 Yetkili giriş (editör, hakem) (`auth.py`)
- ✉️ Hakeme atama ve mesajlaşma sistemi (`routes.py`)
- 🧾 Loglama desteği (`app.log`, `log_service.py`)
- 📄 Jinja2 ile şablonlu web arayüz

## 📂 Proje Yapısı
Academic-PDF-Anonymizer-Platform/
├── app.py # Ana Flask uygulaması
├── auth.py # Giriş ve kullanıcı kontrol
├── anonymizer.py # Anonimleştirme algoritması
├── censorship.py # PDF içeriği sansürleme
├── routes.py # Sayfa yönlendirme ve işlevler
├── static/ # CSS, görseller
├── templates/ # HTML şablonları
├── uploads/ # Yüklenen PDF'ler
├── outputs/ # Sansürlenmiş çıktılar
├── db.py # Veritabanı bağlantısı (muhtemelen SQLite)
├── config.py # Ayarlar
└── app.log # Uygulama logları
