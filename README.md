========================================
 YouTube Downloader - Tek Tik Kullanim
========================================

BU PROGRAM NE YAPIYOR?
----------------------
- YouTube video veya playlist indirir
- MP4 (video) veya MP3 (ses) olarak kaydeder
- Ilk kullanimda kayit klasorlerini sorar
- Sonraki calistirmalarda ayarlari hatirlar
- Indirilemeyen videolar icin detayli neden raporu verir
- Tamamen PORTABLE calisir (tek klasor)


NASIL CALISTIRILIR?
-------------------
1) Bu klasorun icindeki:
   -> Run.bat
   dosyasina CIFT TIKLA

2) Ilk calistirmada:
   - Gerekli programlar otomatik kurulur
     (Python, yt-dlp, ffmpeg, deno)
   - Bu islem 2-3 dakika surebilir

3) Sonra program acilir ve:
   - Kayit klasorlerini sorar (sadece ilk kez)
   - Video URL ister
   - MP4 / MP3 secmeni ister
   - Gerekli ayarlari sorar


GEREKENLER
----------
- Windows 10 / Windows 11
- Internet baglantisi
- Ilk kurulum icin yonetici izni gerekebilir


KLASOR YAPISI (PORTABLE)
------------------------
Program calistikca su klasorler otomatik olusur:

YouTubeDownloader\
│
├─ Run.bat            -> Cift tikla, her seyi baslatir
├─ downloader.py      -> Asil program
├─ install.ps1        -> Ilk kurulumlari yapar
├─ README.txt         -> Bu dosya
├─ config.json        -> Kayit klasor ayarlari (otomatik)
│
├─ logs\              -> Tum calistirma loglari
│   └─ yt-dlp_*.log
│
└─ archives\          -> Indirilen videolarin kaydi
    └─ *.txt


LOG DOSYALARI
-------------
- Tum calistirma kayitlari:
  logs\ klasoru icine yazilir

- Bir sorun olursa:
  -> logs\ klasorundeki SON .log dosyasini incele
  -> veya bu dosyayi gelistiriciye gonder


ARCHIVE (INDIRME KAYDI)
-----------------------
- Daha once indirilen videolar tekrar indirilmez
- Playlist devam ettirilebilir
- Tum kayitlar:
  archives\ klasoru icindedir


AYARLAR (config.json)
---------------------
- Ilk calistirmada olusur
- Video ve Muzik klasorlerini hatirlar
- Sonraki calistirmalarda tekrar sormaz

Ayar secenekleri:
- Program icinden:
  -> "Klasorleri degistir"
  -> "Ayarlari sifirla"

- Manuel sifirlama:
  -> config.json dosyasini sil


PROGRAMI TASIMAK
----------------
- Tum program TEK klasorde calisir
- Baska bilgisayara tasimak icin:
  -> Klasoru ZIP yap
  -> Diger bilgisayara kopyala
  -> Run.bat'e cift tikla

Ayarlar, loglar ve archive bilgileri
AYNI klasorde korunur.


SORUN GIDERME
-------------
- Run.bat calismazsa:
  -> Sag tik > Yonetici olarak calistir

- Indirme baslamazsa:
  -> Internet baglantisini kontrol et
  -> logs\ klasorundeki log dosyasini incele

- Program kapanirsa:
  -> Log dosyasi nedeni gosterir


NOTLAR
------
- MP4 modunda:
  -> Uyumluluk veya Kalite profili secilebilir
- MP3 modunda:
  -> En yuksek kalite MP3 uretilir
- Playlist indirirken:
  -> Atlanan videolarin nedeni listelenir


KEYIFLI KULLANIMLAR 🚀
----------------------------------------
Bu arac egitim ve kisisel kullanim amaciyla
hazirlanmistir.
