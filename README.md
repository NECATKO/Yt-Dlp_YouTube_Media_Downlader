# YouTube Downloader - Tek Tik Kullanim

Basit bir arayuzle YouTube videolarini veya playlistlerini indirip MP4 ya da MP3 olarak kaydeden portable arac.

## Bu Program Ne Yapiyor?
- YouTube video veya playlist indirir
- MP4 (video) veya MP3 (ses) olarak kaydeder
- Ilk kullanimda kayit klasorlerini sorar ve kaydeder
- Sonraki calistirmalarda ayarlari hatirlar
- Indirilemeyen videolar icin detayli neden raporu verir
- Tamamen portable calisir (tek klasor yeterlidir)

## Kurulum ve Calistirma
1. Klasor icindeki `Run.bat` dosyasina cift tikla.
2. Ilk calistirmada gerekli programlar otomatik kurulur (Python, yt-dlp, ffmpeg, deno). Bu adim 2-3 dakika surebilir.
3. Program acilinca kayit klasorlerini sorar (yalnizca ilk kez), video URL ister, MP4/MP3 secmeni ve diger ayarlari ister.

## Gerekenler
- Windows 10 veya Windows 11
- Internet baglantisi
- Ilk kurulum icin yonetici izni gerekebilir

## Klasor Yapisi (Portable)
Program calistikca asagidaki klasorler otomatik olusur ve ayni klasorde tasinabilir.

```
YouTubeDownloader/
|
|-- Run.bat            -> Cift tikla, her seyi baslatir
|-- downloader.py      -> Asil program
|-- install.ps1        -> Ilk kurulumlari yapar
|-- README.md          -> Bu dosya
|-- config.json        -> Kayit klasor ayarlari (otomatik)
|
|-- logs/              -> Tum calistirma loglari
|   `-- yt-dlp_*.log
|
`-- archives/          -> Indirilen videolarin kaydi
    `-- *.txt
```

## Log Dosyalari
- Tum calistirma kayitlari `logs/` klasorune yazilir.
- Bir sorun olursa son `.log` dosyasini inceleyebilir veya gelistiriciyle paylasabilirsin.

## Archive (Indirme Kaydi)
- Daha once indirilen videolar tekrar indirilmez.
- Playlist indirmeleri kaldigi yerden devam eder.
- Tum kayitlar `archives/` klasoru icindedir.

## Ayarlar (`config.json`)
- Ilk calistirmada olusur ve video/muzik klasorlerini hatirlar.
- Sonraki calistirmalarda bu bilgiler dogrudan kullanilir.
- Program icinden "Klasorleri degistir" veya "Ayarlari sifirla" secenekleriyle ayarlari yenileyebilirsin.
- Manuel sifirlama icin `config.json` dosyasini silmek yeterlidir.

## Programi Tasimak
- Tum program tek klasorde calistigi icin klasoru ZIP yapip baska bilgisayara tasiyabilirsin.
- Yeni bilgisayarda sadece `Run.bat` dosyasina cift tiklamak yeterlidir; ayarlar, loglar ve arsiv bilgileri ayni klasorde korunur.

## Sorun Giderme
- `Run.bat` calismazsa dosyaya sag tiklayip **Yonetici olarak calistir** sec.
- Indirme baslamazsa internet baglantisini kontrol et ve `logs/` icindeki log dosyasina bak.
- Program aniden kapanirsa log dosyasi nedeni gosterir.

## Notlar
- MP4 modunda uyumluluk veya kalite profili secilebilir.
- MP3 modunda en yuksek kalite MP3 olusturulur.
- Playlist indirirken atlanan videolarin nedenleri ayrintili olarak listelenir.

## Keyifli Kullanimlar
Bu arac egitim ve kisisel kullanim amaciyla hazirlanmistir.
