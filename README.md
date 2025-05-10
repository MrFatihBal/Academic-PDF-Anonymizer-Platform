# Academic-PDF-Anonymizer-Platform
# 🕵️ Academic PDF Anonymizer Platform  Bu Flask tabanlı sistem, akademik makaleleri anonimleştirerek çift kör hakem değerlendirme süreçlerinde kullanılmak üzere geliştirilmiştir.

## 🔍 Özellikler

- 📁 PDF yükleme ve analiz
- 🧠 İsim, kurum, iletişim ve görsel sansürleme 
- 🔐 Yetkili giriş (editör, hakem) 
- ✉️ Hakeme atama ve mesajlaşma sistemi 
- 🧾 Loglama desteği 
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
├── db.py # Veritabanı bağlantısı 
├── config.py # Ayarlar
└── app.log # Uygulama logları
