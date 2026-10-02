# Aşama 2 — Kurulum ve güncelleme betikleri (B01, B10, B11, B12, B13) — uygulama planı

> **Uygulayıcı için:** ZORUNLU ALT-BECERİ: `superpowers:executing-plans`. Adımlar `- [ ]` kutularıyla izlenir.

**Hedef:** Güncelleme yarıda kalıp geri yükleme de başarısız olduğunda kurtarma kaydı kaybolmasın ve başlatıcılar yarım paketle açılmasın. Elle yapılan motor güncellemesinin hatası gizlenmesin. macOS kurulumu yeni kurulan Python'u seçsin. Windows güncelleyicisi onay sorsun, `Run.bat` çıkış kodunu aktarsın.

**Mimari:** Betikler kendi yapısında kalır, yalnızca hatalı dallar düzeltilir. Kurtarma kaydının (journal) ilk satırı yedek klasörüdür (eski biçimle uyumlu). Sonraki `+<öğe>` satırları güncellemenin *yeni eklediği* öğelerdir; geri alma bunları kaldırır. Geri yükleme tamamen başarılı olmadıkça journal ve yedek silinmez.

**Spec:** `degerlendirme-raporlari/2026-10-02/master-prompt.md` §2 B11, §3 B10/B11/B12/B13, §1 B01. Yol haritası: `docs/superpowers/plans/2026-10-02-review-roadmap.md`.

## Genel kısıtlar
- `run.sh` güncelleme **denetlemez** (kullanıcı kararı, 30 Eylül). Journal varsa uygulamayı açmaz; kullanıcıya `bash update.sh` komutunu ve yedeğin yerini söyler. `update.sh`'yi kendisi çağırmaz.
- `Run.bat` otomatik güncelleme sırasında değiştirilmez (`update.ps1` `$ReplaceItems` listesinde yok), bu kural korunur.
- `runtime.lock`'a dokunulmaz. Kullanıcı verisi (config, archives, downloads, logs, runtime, .venv) güncellemede değişmez.
- Windows testleri gerçek Windows PowerShell 5.1 ve `cmd.exe` ile çalışır: Windows'ta doğrudan, WSL'de interop üzerinden (`powershell.exe`, `cmd.exe`, Windows `%TEMP%` altında geçici klasör). İkisi de yoksa testler atlanır. CI'da Windows işinde `YTDLP_REQUIRE_WINDOWS_SCRIPTS=1` atlamayı hataya çevirir.
- Commit sonu: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` + `Claude-Session` satırı. Push yok.
- Doğrulama: pytest, ruff check, ruff format --check (Markdown dahil), mypy, check_version, `bash -n run.sh install.sh update.sh`.

## Gözden geçirme odağı
1. **Eski biçim journal** (tek satır, sonda satır sonu yok; 0.4.0'ın yazdığı) → yeni kurtarma kodu ilk satırı yedek yolu olarak okumalı. Testi Görev 1'de.
2. **Kurtarmanın ikinci denemesi**, birincisinin yarıda geri koyduğu öğeleri kaybetmemeli: geri konan öğe yedekten çıkmış olur, ikinci deneme yalnızca kalanları taşır. Testi Görev 1'de.
3. **Güncellemenin yeni eklediği dosya** (eski kurulumda olmayan `README.md`) geri almada silinmeli; kullanıcının kendi dosyaları silinmemeli. Testi Görev 1 ve Görev 4'te.
4. **`Run.bat` argümanında boşluk/tırnak** (`audit --archive "a b.txt"`) → `%*` aynen geçmeli; `pause` yalnızca argümansız çalıştırmada olmalı. Testi Görev 5'te.
5. **Elle `update.ps1` çalıştırması, girdi kapalıyken** (stdin EOF) → onay "Hayır" sayılmalı, paket değişmemeli. Testi Görev 4'te.

---

### Görev 1: `update.sh` geri alma ve kurtarma (B01) + `run.sh` koruması
**Dosyalar:** `update.sh`, `run.sh`; testler `tests/test_update_sh.py` (`TestRollback`), `tests/test_launchers.py` (`TestRunSh`).

Testler:
- `test_a_failed_restore_keeps_the_journal_and_the_backup`: Sahte `mv` (PATH'in başına konan bir sarmalayıcı) yalnızca `.update-backup-*/ytdlp_app` kaynağını taşırken hata verir. Ek olarak `YTDLP_UPDATE_FAULT_AT=update.sh` verilir. Beklenen: dönüş kodu ≠ 0, `.update-in-progress` duruyor, ilk satırı var olan bir yedek klasörü ve içinde eski `ytdlp_app` var.
- `test_the_next_run_finishes_a_restore_that_failed`: Yukarıdakinden sonra sahte `mv` olmadan `stdin="n\nn\n"` ile ikinci çalıştırma. Beklenen: marker `old`, sürüm `v0.3.1`, `leftovers() == []`, kullanıcı verisi aynı.
- `test_a_file_the_update_added_is_removed_by_the_rollback`: Paketin `README.md` ve `LICENSE` dosyaları var, eski kurulumda ikisi de yok. `YTDLP_UPDATE_FAULT_AT=LICENSE` ile `README.md` artık kurulumda olmamalı.
- `test_an_old_style_journal_is_still_recovered`: Journal yalnızca yedek yolunu taşıyor, sonda satır sonu yok. Bu kayıt kurtarılmalı (mevcut "killed half way" testi bu biçimi zaten kullanıyorsa ayrı test gerekmez; kontrol et).
- `run.sh`: `test_a_half_restored_update_stops_the_launch` → `.update-in-progress` varken Python çağrılmaz; dönüş kodu 1; çıktıda `bash update.sh` ve yedek yolu geçer; `update.sh` çağrılmaz.

Uygulama:
- `apply_update`: journal `printf '%s\n' "$backup"` olarak yazılır. Takasta `[[ -e "$item" || -L "$item" ]]` yanlışsa, yeni öğe yerine konmadan **önce** `printf '+%s\n' "$item" >> "$JOURNAL"` eklenir. `app_version.txt` için de aynısı yapılır.
- `journal_backup()`: `head -n 1 "$JOURNAL"`. `journal_added()`: `sed -n 's/^+//p' "$JOURNAL"`.
- `restore_from_backup "$backup"`: önce journal'daki eklenen öğeler silinir (`rm -rf "$SCRIPT_DIR/$name"`; adlar `REPLACE_*` listesinde ya da `app_version.txt` olmalı, aksi hâlde atlanır), sonra yedekteki öğeler geri taşınır. Herhangi bir adım başarısızsa 1 döner.
- `abort_update`: geri yükleme başarısızsa journal ve yedek **kalır**, staging silinir, kullanıcıya "Run update.sh again to finish restoring; the old files are in $backup" denir. Başarılıysa eskisi gibi temizlenir.
- `recover_interrupted`: ilk satırdan yedek okunur. Geri yükleme başarılıysa journal, yedek ve staging silinir. Başarısızsa journal kalır ve 1 döner (mevcut davranış).
- `run.sh`: `exec`'ten önce journal kontrol edilir: `if [[ -f .update-in-progress ]]; then` hata mesajı + yedek yolu + `bash update.sh` önerisi, `exit 1`.

### Görev 2: Motor güncellemesinin sonucu (B10)
**Dosyalar:** `update.sh` (`update_ytdlp`, `main`), `ytdlp_app/portable.py` (`ensure_ytdlp`); testler `tests/test_update_sh.py` (yeni `TestYtDlpUpdate`), `tests/test_portable.py`.

Testler:
- update.sh, `.venv/bin/pip` 7 ile çıkan sahte: çıktıda `yt-dlp updated successfully!` yok, `yt-dlp could not be updated` var, dönüş kodu 1.
- Sahte pip başarılı: dönüş kodu 0, başarı mesajı var, pip argümanlarında `yt-dlp[default,curl-cffi]` var.
- portable: `force_update=True` ile pip başarısız → `PortableError`. `force_update=False` (haftalık otomatik) ile başarısız → uyarı, istisna yok, state değişmez (mevcut test korunur).

Uygulama:
- `update_ytdlp`: her dalın çıkış kodu kontrol edilir; başarısızsa kırmızı "yt-dlp could not be updated; the installed version is unchanged." mesajı ve `return 1`. `.venv` dalı `--upgrade "$(ytdlp_requirement)"` kullanır. `ytdlp_requirement()`: `.venv/bin/python -s -c 'from ytdlp_app.portable import YTDLP_REQUIREMENT as r; print(r)'`, başarısızsa `yt-dlp[default,curl-cffi]`. Windows `.venv/Scripts/pip.exe` dalı da aynı gereksinimi kullanır.
- `main`: `update_ytdlp || return 1`, ardından "Done!".
- `ensure_ytdlp`: yükseltme başarısızsa ve `force_update` doğruysa `raise PortableError("yt-dlp could not be updated; the installed version is unchanged")`. Docstring: elle istenen güncelleme hata verir, otomatik olan eski motorla devam eder.

### Görev 3: macOS Python seçimi (B11)
**Dosyalar:** `install.sh` (`check_python` → `find_python`, `macos_install`); test `tests/test_install_macos.py`.

Testler (sahte `uname`=Darwin, `brew`, `python3*`; PATH yalnızca sahte klasör + `/usr/bin:/bin`. Sahte Python'lar `-c` ile sürüm denetimine verilen çıkış kodunu, `-m venv X` ile `X/bin/pip` ve `X/bin/python` sahtelerini üretir):
- PATH'te `python3`=3.9 var. `brew install python@3.12` sonrası `brew --prefix python@3.12` → `<prefix>/bin/python3.12`=3.12. Beklenen: dönüş kodu 0, `.venv` o yorumlayıcıyla oluşturuldu (çağrı kaydı), eski `python3` ile `venv` çağrılmadı.
- PATH'te `python3.12`=3.12 var, `python3`=3.9: brew çağrılmadan `python3.12` seçilir.
- `python3`=4.0: kabul edilir (eski `minor -ge 11` hatası).
- Brew kurulumu sonrası yorumlayıcı hâlâ uygun değilse: dönüş kodu 1, "Failed to install Python 3.11+".

Uygulama:
- `python_ok <exe>`: `"$1" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'`.
- `find_python`: `python3.13 python3.12 python3.11 python3` sırasıyla ilk uygun olanı `PYTHON_BIN`'e yazar.
- Bulunamazsa: `brew install python@3.12`, ardından `PYTHON_BIN="$(brew --prefix python@3.12)/bin/python3.12"` ve `python_ok` ile kontrol, değilse `die`.
- `.venv` oluşturma `"$PYTHON_BIN" -m venv .venv` ile yapılır.

### Görev 4: Windows test düzeneği + `update.ps1` geri alma (B01) ve onay (B12)
**Dosyalar:** yeni `tests/windows.py` (yardımcı), `update.ps1`, yeni `tests/test_update_ps1.py`, `.github/workflows/ci.yml` (`YTDLP_REQUIRE_WINDOWS_SCRIPTS`).

`tests/windows.py`:
- `powershell()`: Windows'ta `powershell`, WSL'de `shutil.which("powershell.exe")`. `cmd()` aynı biçimde.
- `windows_temp()`: Windows'ta `tempfile.gettempdir()`, WSL'de `cmd.exe /c echo %TEMP%` → `wslpath -u`.
- `win(path)`: Windows'ta `str(path)`, WSL'de `wslpath -w`.
- `requires_windows_scripts`: araçlar yoksa skip. `YTDLP_REQUIRE_WINDOWS_SCRIPTS=1` ise skip yerine hata.
- `scratch` fixture: Windows temp altında benzersiz klasör, test sonunda silinir.

`test_update_ps1.py` (sahte site, `file:///` URL'leri; Windows PowerShell 5.1'in `Invoke-RestMethod`'u `file:` destekler, ilk testte doğrulanır):
- Başarılı güncelleme `-Quiet` ile: yeni marker, sürüm, kullanıcı verisi aynı, artık klasör yok.
- **B12:** elle çalıştırmada (bayraksız) stdin `n` ya da boş → paket değişmez, çıktıda onay sorusu var. `y` → güncellenir.
- `-CheckOnly`: değişiklik yok, "Update available" yazılır.
- **B01:** geri yüklemenin başarısız olması için yedekteki `ytdlp_app` içinde bir dosya açık tutulur (aynı PowerShell oturumunda `[IO.File]::Open(..., FileShare.None)`). Bunun için test hook'u `YTDLP_UPDATE_FAULT_AT` (update.sh ile aynı adla) `update.ps1`'e eklenir: takasta ilgili öğeden sonra hata atar. Geri yükleme hatası ise yedekteki dosyayı kilitleyerek üretilir: testte `update.ps1`'i çağıran sarmalayıcı PowerShell betiği, hook tetiklenmeden önce dosyayı kilitleyemeyeceği için ikinci bir hook kullanılır: `YTDLP_UPDATE_RESTORE_FAULT_AT=<öğe>` → `Restore-FromBackup` o öğeyi taşırken hata atar. Beklenen: journal ve yedek kalır, çıkış ≠ 0. Ardından hook'suz ikinci çalıştırma eski sürümü geri getirir ve journal'ı temizler.
- Eklenen öğe (`README.md` yokken paketle gelen) geri almada silinir.

Uygulama (`update.ps1`):
- Journal: `Set-Content -Value $backup` (satır sonlu). Yeni öğe yerine konmadan önce `Add-Content $Journal "+$item"`. Okuma `Get-Content $Journal | Select-Object -First 1`.
- `Restore-FromBackup($Backup)`: önce journal'daki eklenenler (izinli adlar) silinir, sonra yedektekiler taşınır. Hook `YTDLP_UPDATE_RESTORE_FAULT_AT` → `throw`. Başarı durumu döner.
- `$abort`: geri yükleme başarısızsa journal ve yedek kalır, mesaj verilir.
- Onay: `-Quiet` değilse ve `-CheckOnly` değilse `Read-Host "Download and install update? (y/N)"`; `y`/`Y` dışındaki her şey → "Update skipped." ve `exit 0`. Stdin kapalıysa `Read-Host` boş döner ya da hata atar; ikisi de "Hayır" sayılır (`try/catch`).
- Başlık yorumundaki kullanım satırı güncellenir: "update if a newer release exists (asks first)".

### Görev 5: `Run.bat` çıkış kodu, `pause` ve journal koruması (B13)
**Dosyalar:** `Run.bat`; test `tests/test_run_bat.py`.

Testler (gerçek `cmd.exe`; `YTDLP_NO_AUTO_UPDATE=1`; sahte `install.ps1` `exit 0`; `runtime\python\python.exe` yerine `C:\Windows\System32\where.exe` kopyası (`where.exe -s downloader.py ...` sabit, sıfırdan farklı bir kodla çıkar; beklenen kod, kopya doğrudan çalıştırılarak ölçülür):
- Argümanla (`audit`) → dönüş kodu = sahte Python'un kodu; çıktıda "Press any key" yok.
- Argümansız → dönüş kodu aynı, "Press any key" var (stdin boş, `pause` hemen geçer).
- Argümanda boşluk ve tırnak → kod aynı (yalnızca çökmediğini ve kodun geçtiğini doğrular).
- `.update-in-progress` varken → Python çalışmaz, kod 1, çıktıda yedek yolu ve `update.ps1` önerisi var.

Uygulama:
- Güncelleme denetiminden sonra journal kontrolü: `if exist ".update-in-progress" (` mesaj + `type .update-in-progress` + `pause` + `exit /b 1` `)`.
- Python satırından hemen sonra `set "APP_RC=%ERRORLEVEL%"`.
- `if "%~1"==""` ise "Application closed." + `pause`. Sonra `endlocal & exit /b %APP_RC%`.

### Görev 6: CI, belgeler, kapanış
- `ci.yml` test adımı `env`: `YTDLP_REQUIRE_WINDOWS_SCRIPTS: ${{ matrix.os == 'windows-latest' && '1' || '0' }}`.
- README: Windows güncelleme onayı, `Run.bat` çıkış kodu/pause, yarım güncellemede başlatıcının davranışı, macOS Python seçimi, `bash update.sh`'nin motor güncelleme hatasında 1 dönmesi.
- CHANGELOG `[Unreleased]` → "Fixed — installing and updating"; TASKS aşama 2 işaretlenir; yol haritası durum tablosu.
- İnceleme denemesi `probes.py` `updater_failed_pip` ve `macos.py` tekrar çalıştırılır.
- Tüm kontroller, commit.
