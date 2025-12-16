"""
Internationalization (i18n) support for yt-dlp-wrapper.
Supports Turkish (tr) and English (en) languages.
"""

from __future__ import annotations

from typing import Literal

Language = Literal["tr", "en"]

# Default language
DEFAULT_LANGUAGE: Language = "en"

# Message keys and translations
MESSAGES: dict[str, dict[Language, str]] = {
    # General
    "app_name": {
        "en": "yt-dlp YouTube Media Downloader",
        "tr": "yt-dlp YouTube Medya İndirici",
    },
    "exit": {
        "en": "Exiting.",
        "tr": "Çıkılıyor.",
    },
    "no_url_provided": {
        "en": "No URL provided. Exiting.",
        "tr": "URL girilmedi. Çıkılıyor.",
    },
    "all_tasks_completed": {
        "en": "All tasks completed.",
        "tr": "Tüm işlemler tamamlandı.",
    },
    "operation_cancelled": {
        "en": "Operation cancelled by user (Ctrl+C).",
        "tr": "İşlem kullanıcı tarafından iptal edildi (Ctrl+C).",
    },
    
    # Prompts
    "prompt_url": {
        "en": "Enter video or playlist URL (blank = exit): ",
        "tr": "Video veya playlist URL'si girin (boş = çıkış): ",
    },
    "prompt_download_type": {
        "en": "What do you want to download?",
        "tr": "Ne indirmek istiyorsunuz?",
    },
    "prompt_playlist_action": {
        "en": "URL looks like a playlist. What do you want?",
        "tr": "URL bir playlist gibi görünüyor. Ne yapmak istiyorsunuz?",
    },
    "prompt_mp4_profile": {
        "en": "Choose MP4 behavior (profile):",
        "tr": "MP4 davranışını seçin (profil):",
    },
    "prompt_container": {
        "en": "Container preference for Quality profile:",
        "tr": "Kalite profili için konteyner tercihi:",
    },
    "prompt_what_next": {
        "en": "What next?",
        "tr": "Şimdi ne yapalım?",
    },
    "prompt_exit_on_failure": {
        "en": "An error occurred. Do you want to exit? (Y/N): ",
        "tr": "Bir hata oluştu. Çıkmak istiyor musunuz? (E/H): ",
    },
    "prompt_select": {
        "en": "Select (numbers only): ",
        "tr": "Seçin (sadece rakam): ",
    },
    "prompt_path": {
        "en": "Path: ",
        "tr": "Yol: ",
    },
    
    # Options
    "opt_video_mp4": {
        "en": "Video (MP4)",
        "tr": "Video (MP4)",
    },
    "opt_audio_mp3": {
        "en": "Audio (MP3)",
        "tr": "Ses (MP3)",
    },
    "opt_download_playlist": {
        "en": "Download the entire playlist",
        "tr": "Tüm playlist'i indir",
    },
    "opt_download_single": {
        "en": "Download only this video (ignore playlist)",
        "tr": "Sadece bu videoyu indir (playlist'i yoksay)",
    },
    "opt_mp4_compatibility": {
        "en": "Compatibility: force MP4 (lossless when possible, otherwise recode)",
        "tr": "Uyumluluk: MP4 zorla (mümkünse kayıpsız, değilse yeniden kodla)",
    },
    "opt_mp4_quality": {
        "en": "Quality: no recode; remux if possible, otherwise keep container",
        "tr": "Kalite: yeniden kodlama yok; mümkünse remux, değilse konteyneri koru",
    },
    "opt_container_mkv": {
        "en": "Safe (recommended): MKV",
        "tr": "Güvenli (önerilen): MKV",
    },
    "opt_container_mp4": {
        "en": "Try MP4 (remux only; may fail if codecs incompatible)",
        "tr": "MP4 dene (sadece remux; codec uyumsuzsa başarısız olabilir)",
    },
    "opt_download_another": {
        "en": "Download another URL",
        "tr": "Başka bir URL indir",
    },
    "opt_exit": {
        "en": "Exit",
        "tr": "Çıkış",
    },
    
    # Errors
    "error_yt_dlp_not_found": {
        "en": "ERROR: 'yt-dlp' not found. Run install.ps1 first.",
        "tr": "HATA: 'yt-dlp' bulunamadı. Önce install.ps1 çalıştırın.",
    },
    "error_invalid_url": {
        "en": "ERROR: Invalid URL. Please enter a valid YouTube URL.",
        "tr": "HATA: Geçersiz URL. Lütfen geçerli bir YouTube URL'si girin.",
    },
    "error_playlist_fetch": {
        "en": "Could not fetch playlist entries; skip report may be incomplete.",
        "tr": "Playlist bilgileri alınamadı; atlama raporu eksik olabilir.",
    },
    "error_unexpected": {
        "en": "Unexpected error. Check logs if available.",
        "tr": "Beklenmeyen hata. Varsa logları kontrol edin.",
    },
    "error_invalid_choice": {
        "en": "Invalid choice. Please enter one of the listed numbers.",
        "tr": "Geçersiz seçim. Lütfen listelenen numaralardan birini girin.",
    },
    
    # Warnings
    "warn_ffmpeg_not_found": {
        "en": (
            "WARNING: ffmpeg not found.\n"
            "- MP3 mode may fail to convert audio.\n"
            "- MP4 mode may fail to merge/recode and attach thumbnails.\n"
            "Fix: run install.ps1 or install ffmpeg and add it to PATH."
        ),
        "tr": (
            "UYARI: ffmpeg bulunamadı.\n"
            "- MP3 modu ses dönüştürmede başarısız olabilir.\n"
            "- MP4 modu birleştirme/yeniden kodlama ve küçük resim eklemede başarısız olabilir.\n"
            "Çözüm: install.ps1 çalıştırın veya ffmpeg kurup PATH'e ekleyin."
        ),
    },
    "warn_deno_not_found": {
        "en": (
            "WARNING: Deno runtime not found.\n"
            "- Some videos may fail if yt-dlp cannot solve JS challenges.\n"
            "- Install Deno (https://deno.com) or rerun install.ps1."
        ),
        "tr": (
            "UYARI: Deno runtime bulunamadı.\n"
            "- yt-dlp JS zorluklarını çözemezse bazı videolar başarısız olabilir.\n"
            "- Deno kurun (https://deno.com) veya install.ps1 tekrar çalıştırın."
        ),
    },
    
    # Info
    "info_mode": {
        "en": "Mode",
        "tr": "Mod",
    },
    "info_is_playlist": {
        "en": "Is playlist?",
        "tr": "Playlist mi?",
    },
    "info_output_folder": {
        "en": "Output folder",
        "tr": "Çıktı klasörü",
    },
    "info_output_template": {
        "en": "Output template",
        "tr": "Çıktı şablonu",
    },
    "info_archive_file": {
        "en": "Archive file",
        "tr": "Arşiv dosyası",
    },
    "info_log_file": {
        "en": "Log file",
        "tr": "Log dosyası",
    },
    "info_deno_available": {
        "en": "Deno available",
        "tr": "Deno mevcut",
    },
    "info_mp4_profile": {
        "en": "MP4 profile",
        "tr": "MP4 profili",
    },
    "info_compatibility": {
        "en": "Compatibility",
        "tr": "Uyumluluk",
    },
    "info_quality": {
        "en": "Quality",
        "tr": "Kalite",
    },
    "info_config": {
        "en": "Config",
        "tr": "Ayarlar",
    },
    "info_log": {
        "en": "Log",
        "tr": "Log",
    },
    "info_yes": {
        "en": "Yes",
        "tr": "Evet",
    },
    "info_no": {
        "en": "No",
        "tr": "Hayır",
    },
    
    # Config setup
    "config_not_set": {
        "en": "Download folders not set yet. Configure them now (this is only asked once).",
        "tr": "İndirme klasörleri henüz ayarlanmadı. Şimdi yapılandırın (bu sadece bir kez sorulur).",
    },
    "config_enter_folder": {
        "en": "Enter folder path for {label} (blank = default):",
        "tr": "{label} için klasör yolu girin (boş = varsayılan):",
    },
    "config_default": {
        "en": "Default",
        "tr": "Varsayılan",
    },
    "config_saved": {
        "en": "Settings saved:",
        "tr": "Ayarlar kaydedildi:",
    },
    "config_videos": {
        "en": "Videos",
        "tr": "Videolar",
    },
    "config_music": {
        "en": "Music",
        "tr": "Müzik",
    },
    "config_using_folders": {
        "en": "Using download folders (Videos: {v_dir} | Music: {m_dir}).",
        "tr": "İndirme klasörleri kullanılıyor (Videolar: {v_dir} | Müzik: {m_dir}).",
    },
    "config_edit_hint": {
        "en": "To change these later, edit config.json at: {path}",
        "tr": "Bunları daha sonra değiştirmek için config.json dosyasını düzenleyin: {path}",
    },
    
    # Language selection
    "prompt_language": {
        "en": "Select language / Dil seçin:",
        "tr": "Select language / Dil seçin:",
    },
    "opt_english": {
        "en": "English",
        "tr": "English",
    },
    "opt_turkish": {
        "en": "Türkçe",
        "tr": "Türkçe",
    },
    
    # Stages
    "stage_compat_1": {
        "en": "### STAGE 1 (Compatibility): lossless MP4 when avc1+mp4a is available...",
        "tr": "### AŞAMA 1 (Uyumluluk): avc1+mp4a mevcut olduğunda kayıpsız MP4...",
    },
    "stage_compat_2": {
        "en": "### STAGE 2 (Compatibility): download remaining items and recode to MP4...",
        "tr": "### AŞAMA 2 (Uyumluluk): kalan öğeleri indirip MP4'e yeniden kodla...",
    },
    "stage_quality_mkv": {
        "en": "### QUALITY: No recode. Output container: MKV",
        "tr": "### KALİTE: Yeniden kodlama yok. Çıktı konteyneri: MKV",
    },
    "stage_quality_mp4": {
        "en": "### QUALITY: No recode. Will try MP4 remux.",
        "tr": "### KALİTE: Yeniden kodlama yok. MP4 remux denenecek.",
    },
    "stage_mp3": {
        "en": "### MP3: Downloading best audio and converting to MP3...",
        "tr": "### MP3: En iyi ses indiriliyor ve MP3'e dönüştürülüyor...",
    },
    
    # Skip report
    "skip_report_header": {
        "en": "SKIPPED ITEMS (not downloaded)",
        "tr": "ATLANAN ÖĞELER (indirilmedi)",
    },
    "skip_report_title": {
        "en": "Title",
        "tr": "Başlık",
    },
    "skip_report_reason": {
        "en": "Reason",
        "tr": "Sebep",
    },
    "skip_report_none": {
        "en": "All playlist items appear archived (no skips).",
        "tr": "Tüm playlist öğeleri arşivlenmiş görünüyor (atlanan yok).",
    },
}


class Translator:
    """
    Simple translator class that returns messages in the configured language.
    """

    def __init__(self, language: Language = DEFAULT_LANGUAGE) -> None:
        self._language = language

    @property
    def language(self) -> Language:
        return self._language

    @language.setter
    def language(self, value: Language) -> None:
        if value not in ("en", "tr"):
            value = DEFAULT_LANGUAGE
        self._language = value

    def get(self, key: str, **kwargs: str) -> str:
        """
        Get a translated message by key.
        
        Args:
            key: The message key
            **kwargs: Format arguments for the message
            
        Returns:
            The translated message, or the key itself if not found
        """
        msg_dict = MESSAGES.get(key)
        if not msg_dict:
            return key
        
        msg = msg_dict.get(self._language) or msg_dict.get(DEFAULT_LANGUAGE) or key
        
        if kwargs:
            try:
                msg = msg.format(**kwargs)
            except KeyError:
                pass
        
        return msg

    def __call__(self, key: str, **kwargs: str) -> str:
        """Shorthand for get()."""
        return self.get(key, **kwargs)


# Global translator instance
_translator = Translator()


def set_language(language: Language) -> None:
    """Set the global language."""
    _translator.language = language


def get_language() -> Language:
    """Get the current global language."""
    return _translator.language


def t(key: str, **kwargs: str) -> str:
    """
    Translate a message key to the current language.
    
    This is the main function to use for translations throughout the app.
    """
    return _translator.get(key, **kwargs)
