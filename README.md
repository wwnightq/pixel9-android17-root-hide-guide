# Pixel 9 on Android 17 Canary: root hiding, Strong Integrity, and Vector

[English](#english) | [Русский](#русский) | [Standalone Russian file (README.ru.md)](README.ru.md)

Working notes, config templates, and two ELF patchers from setting up a Google Pixel 9 (`tokay`) on Android 17 Canary (`ZP11.261016.008`, API 37, security patch `2026-11-05`) with ReSukiSU `v4.2.0-rc3`. With this setup, Google Play returns `MEETS_BASIC_INTEGRITY`, `MEETS_DEVICE_INTEGRITY`, and `MEETS_STRONG_INTEGRITY`, Mir Pay and banking apps open without root alerts, and Vector (Xposed) runs without `system_server` crash loops.

Рабочие заметки, шаблоны конфигов и два патчера под Google Pixel 9 (`tokay`) на Android 17 Canary (`ZP11.261016.008`, API 37, патч `2026-11-05`) с ReSukiSU `v4.2.0-rc3`. В этой связке Google Play отдаёт `BASIC`, `DEVICE` и `STRONG`, Mir Pay и банки открываются без жалоб на root, а Vector (Xposed) работает без падений `system_server`.

## English

[Перейти к русской версии на этой странице](#русский)

This repo only contains the patcher scripts and example configs. Grab the module ZIPs from their upstream GitHub releases, and never upload your `/data/adb/tricky_store/keybox.xml` anywhere.

### Tested stack

| Part | Version used |
| :--- | :--- |
| Device | Google Pixel 9 (`tokay`) |
| OS | Android 17 Canary (`ZP11.261016.008`, SDK 37, patch `2026-11-05`) |
| Root | ReSukiSU `v4.2.0-rc3` (`ksud 35171`) |
| Zygisk | Zygisk Next `1.5.3` (`880`, `linker: builtin`, DenyList off) |
| Root hiding | Nohello `v0.0.7` (`53`), HMA-OSS Zygisk `oss-177` |
| Integrity | Tricky Store OSS `v3.1.0` (`172`, patched), Play Integrity Fork `v19` |
| Xposed (optional) | Vector `v2.2 canary-3119` (patched) |

### What broke on Android 17 Canary

Modules that worked fine on Android 15 or 16 crashed or failed attestation on SDK 37:

| Module | What went wrong | Used instead |
| :--- | :--- | :--- |
| NeoZygisk `v2.4` | `solist` errors and `system_server` instability | [Zygisk Next](https://github.com/Dr-TSNG/ZygiskNext) `1.5.3+` |
| Closed Tricky Store `v1.4.1` | Fails EC key attestation on SDK 37 | [Tricky Store OSS](https://github.com/beakthoven/TrickyStoreOSS) `v3.1.0+` (patched) |
| Integrity Box | Extra `/data/adb/service.d` scripts and `Box-Brain` clutter | [Play Integrity Fork](https://github.com/osm0sis/PlayIntegrityFork) `v19+` |
| Pay Security Bypass `v1.0.4` | Crashes Mir Pay with `AssertionError` (`AndroidVMTools` caps at SDK 36) | Removed (Mir Pay runs without it) |
| Vector `v2.2 (3080)` | `system_server` crash loop | [Vector](https://github.com/JingMatrix/Vector) `canary-3119+` (patched) |

### The `libbinder.so` symlink issue on Android 17

Check your ROM before flashing anything:

```sh
adb shell "readlink -f /system/lib64/libbinder.so"
```

If it prints `/system/lib64/libbinder.so`, you can flash stock Tricky Store OSS and stock Vector as-is.

On Android 17 Canary (`ZP11.261016.008`), it prints `/system/lib64/libcore_bundle.so`. Because `dl_iterate_phdr` returns real file paths, two modules fail the exact same lookup:

1. `Tricky Store OSS v3.1.0` injects `libTrickyStoreOSS.so` into `keystore2`, then its PLTI loader fails with `Failed to find libbinder.so via dl_iterate_phdr` and `Binder interception initialization failed`. The `TrickyStoreOSS` daemon exits right after boot. The nasty part: `/data/adb/tricky_store/tee_status` still reads `teeBroken=false`, and `libTrickyStoreOSS.so` stays mapped inside `keystore2`, so a quick check looks healthy while attestation is completely dead.
2. `Vector canary-3119` hits the same check inside `libzygisk.so`, logs `Could not find any mappings for libbinder.so`, leaves caller ID at `0`, and rejects IPC calls (`Vector reached system_server but its bridge never answered`).

Both scripts in `scripts/` replace the single standalone 12-byte string `"libbinder.so"` inside `.rodata` with `"re_bundle.so"` (also 12 bytes, matching only `libcore_bundle.so` among Android 17 bundles). Both scripts refuse to scan outside `.rodata` and assert that `.dynstr` (`DT_NEEDED`) stays byte-for-byte identical.

Upstream `beakthoven/TrickyStoreOSS` already merged `libcore_bundle.so` support on `main` after the `v3.1.0` tag. Run `--dry-run` on newer releases of Tricky Store OSS or Vector first; if a release already references `libcore_bundle.so`, the script will tell you no patch is needed.

### Backup and recovery

Copy `/data/adb` before changing modules:

```sh
adb shell "su -c 'mkdir -p /data/adb/backup && cp -a /data/adb/modules /data/adb/tricky_store /data/adb/lspd /data/adb/backup/'"
```

If a module bootloops the phone, hold Volume Down during boot to trigger KernelSU / ReSukiSU Safe Mode (disables all modules). When ADB comes up, you can disable one module at a time with `/data/adb/ksud module disable <module_id>`.

### ReSukiSU flags and App Profiles

Nohello handles mount hiding in Zygisk space and clashes with kernel auto-unmount. Turn `kernel_umount` off and keep `selinux_hide` on:

```sh
adb shell "su -c '/data/adb/ksud feature set kernel_umount 0 && /data/adb/ksud feature set selinux_hide 1 && /data/adb/ksud feature save'"
```

Check `/data/adb/ksud feature list`. Keep `su_compat`, `selinux_hide`, `sulog`, and `adb_root` enabled; `kernel_umount` should show `[DISABLED]`.

Watch out for ReSukiSU App Profiles too. Do not give banking, payment, or messaging apps a custom non-root profile with `umount` turned off. That leaves a `umount_modules=0` record in `/data/adb/ksu/.allowlist` and breaks hiding for that package. Leave apps you hide root from on the default unrooted profile.

### Core modules

If `readlink -f /system/lib64/libbinder.so` returned `/system/lib64/libcore_bundle.so`, patch the official `Tricky-Store-OSS-v3.1.0` ZIP on your PC first:

```sh
python scripts/patch_trickystore_a17.py Tricky-Store-OSS-v3.1.0-172-41383f5-Release.zip -o Tricky-Store-OSS-v3.1.0-a17-patched.zip
```

If stock `v3.1.0` is already installed on the phone, the same script also patches a standalone `libTrickyStoreOSS.so` pulled from `/data/adb/modules/tricky_store/` (keep a backup before pushing it back).

Queue all five modules in ReSukiSU and reboot once:

1. [Zygisk Next](https://github.com/Dr-TSNG/ZygiskNext) (`1.5.3` or newer). Leave `Enforce DenyList` off in Zygisk Next WebUI so Nohello, HMA-OSS, and Vector keep running.
2. [Nohello](https://github.com/MhmRdd/NoHello) (`v0.0.7` or newer). With Zygisk Next `>= 521`, it creates `/data/adb/nohello/no_clr_ptracemsg` and `/data/adb/nohello/no_dirtyro_ar` automatically.
3. [HMA-OSS](https://github.com/frknkrc44/HMA-OSS) (`oss-177` or newer): flash `HMA-OSS-ZYGISK-*.zip` and install the manager APK.
4. [Tricky Store OSS](https://github.com/beakthoven/TrickyStoreOSS) (`v3.1.0` patched with `scripts/patch_trickystore_a17.py`, or a newer build with `libcore_bundle.so` support).
5. [Play Integrity Fork](https://github.com/osm0sis/PlayIntegrityFork) (`v19` or newer).

### Play Integrity and Tricky Store OSS configs

Put your own valid, unrevoked keybox at `/data/adb/tricky_store/keybox.xml`. Check certificate expiry dates with `openssl` first; an expired or revoked keybox fails Strong Integrity even when every module works.

Copy the files from `templates/`:

- `templates/security_patch.txt` -> `/data/adb/tricky_store/security_patch.txt`. Match the date to `getprop ro.build.version.security_patch`.
- `templates/target.txt` -> `/data/adb/tricky_store/target.txt`. Add your banking, payment, or messaging packages with a trailing `!` (for example `ru.nspk.mirpay!` or `com.whatsapp!`). Only list apps that actually check attestation.
- `templates/custom.pif.prop` -> `/data/adb/modules/playintegrityfix/custom.pif.prop`. Keep `spoofProvider=0` when Tricky Store OSS has a working keybox, otherwise PIF overrides hardware attestation.

Run the Play Integrity Fork Action button (or reboot).

### HMA-OSS

Doing this in the manager app is faster than editing JSON by hand:

1. Open HMA-OSS and check that the system service shows loaded in Mode 1.
2. Open Template Manage and create a blacklist template named `root_hide`.
3. Put your root managers (`com.resukisu.resukisu`, plus `com.topjohnwu.magisk` if still installed), `org.frknkrc44.hma_oss`, terminal/hosts tools, and any Xposed module APKs into `root_hide`.
4. Open App Manage, select `ru.nspk.mirpay`, `com.android.vending`, `com.google.android.gms`, `com.google.android.apps.walletnfcrel`, and your bank or messaging apps. Turn on Hiding, pick Blacklist, turn on Exclude System Apps, and apply `root_hide`.

If you edit `templates/hma-config.example.json` and push it straight to `/data/misc/hide_my_applist_bwpjugplvntusdea/config.json`, fix owner and permissions or `system_server` will ignore it:

```sh
adb shell "su -c 'chown system:system /data/misc/hide_my_applist_bwpjugplvntusdea/config.json && chmod 0600 /data/misc/hide_my_applist_bwpjugplvntusdea/config.json'"
```

### Mir Pay, banks, and WhatsApp

If Mir Pay ran once before hiding was set up, it saves error `0111000003` inside `/data/data/ru.nspk.mirpay` and keeps throwing it even after everything is fixed. Clear its data once:

```sh
adb shell "su -c 'pm clear ru.nspk.mirpay'"
```

Open Mir Pay, grant location when prompted, and check that it reaches the "Add card" screen. Do not install `Pay Security Bypass v1.0.4` on Android 17. Banks change anti-fraud checks whenever they want, and passing app launch does not prove a specific card will tokenize or pay at an NFC terminal, so test payments yourself.

For WhatsApp (or similar apps that pair Play Integrity with server-side risk checks): confirm Strong Integrity passes first, put `com.whatsapp!` in `target.txt`, and hide root packages in HMA-OSS. If you already triggered multiple failed login attempts while attestation was broken or over public proxies, WhatsApp's servers can still hold a temporary block even after the phone passes Strong Integrity.

### Vector (Xposed), optional

Download `Vector-v2.2-3119-Release.zip` from [JingMatrix/Vector Releases](https://github.com/JingMatrix/Vector/releases). If `readlink -f /system/lib64/libbinder.so` pointed to `libcore_bundle.so`, patch the ZIP before flashing:

```sh
python scripts/patch_vector_a17.py Vector-v2.2-3119-Release.zip -o Vector-v2.2-3119-a17-patched.zip
```

The script patches `lib/arm64-v8a/libzygisk.so` in `.rodata` and updates `lib/arm64-v8a/libzygisk.so.sha256` inside the ZIP so `customize.sh` passes its checksum check. Flash the output ZIP in ReSukiSU and reboot.

Open Vector Manager from the notification, the module Action button in ReSukiSU, or by dialing `*#*#832867#*#*`. Give each Xposed module only the apps it needs in Scope, and add every Xposed module APK to `root_hide` in HMA-OSS. Test any future Vector release with `--dry-run` before flashing over the patched version.

### Verifying that everything actually runs

After rebooting, run these checks over ADB:

```sh
adb shell "su -c 'ps -A | grep -i tricky'"
adb shell "su -c 'logcat -d TrickyStoreOSS:W *:S'"
adb shell "su -c 'cat /data/adb/tricky_store/tee_status'"
adb shell "su -c '/data/adb/modules/zygisksu/bin/zygiskd status'"
adb shell "su -c '/data/adb/ksud module list'"
adb shell "su -c '/data/adb/modules/zygisk_vector/cli status'"
```

What you want to see:

- `ps -A | grep -i tricky` returns a running `TrickyStoreOSS` process. Empty output means the daemon crashed on boot.
- `logcat -d TrickyStoreOSS:W *:S` prints nothing (no `Failed to find libbinder.so` and no `CannotAttestIds`).
- `tee_status` prints `teeBroken=false`.
- `zygiskd status` prints `inject_state:1`, `modules_with_issue:0`, and `enforce_denylist:0`.
- `ksud module list` shows positive unmount counts in Nohello and `[System service loaded]` in HMA-OSS Zygisk.
- `vector/cli status` prints `Framework Version: 2.2` (`3119`), and `/data/adb/lspd/log/verbose_*.log` has `Successfully injected Vector IPC binder for applications.` with no `system_server` restarts.

Finish with the built-in Play Integrity check: open Google Play Store -> Settings -> About -> tap the Play Store version 7 times -> General -> Developer options -> Check Integrity. With a working keybox and patched Tricky Store OSS, you get:

```text
Labels: [MEETS_BASIC_INTEGRITY, MEETS_DEVICE_INTEGRITY, MEETS_STRONG_INTEGRITY]
```

## Русский

[Jump to English version on this page](#english)

В репозитории лежат только скрипты и шаблоны конфигов. Сами модули берите с официальных страниц авторов на GitHub, а свой `/data/adb/tricky_store/keybox.xml` никуда не выкладывайте.

### На чём проверялось

| Компонент | Версия |
| :--- | :--- |
| Устройство | Google Pixel 9 (`tokay`) |
| Прошивка | Android 17 Canary (`ZP11.261016.008`, SDK 37, патч `2026-11-05`) |
| Root | ReSukiSU `v4.2.0-rc3` (`ksud 35171`) |
| Zygisk | Zygisk Next `1.5.3` (`880`, `linker: builtin`, DenyList выключен) |
| Скрытие | Nohello `v0.0.7` (`53`), HMA-OSS Zygisk `oss-177` |
| Аттестация | Tricky Store OSS `v3.1.0` (`172`, с патчем), Play Integrity Fork `v19` |
| Xposed (по желанию) | Vector `v2.2 canary-3119` (с патчем) |

### Что сломалось на Android 17 Canary

Модули, которые нормально жили на Android 15 и 16, на SDK 37 отвалились:

| Модуль | Что пошло не так | Что поставил взамен |
| :--- | :--- | :--- |
| NeoZygisk `v2.4` | Ошибки `solist` и нестабильный `system_server` | [Zygisk Next](https://github.com/Dr-TSNG/ZygiskNext) `1.5.3+` |
| Закрытый Tricky Store `v1.4.1` | Ломает EC-аттестацию ключей на SDK 37 | [Tricky Store OSS](https://github.com/beakthoven/TrickyStoreOSS) `v3.1.0+` (с патчем) |
| Integrity Box | Тащит лишние скрипты в `/data/adb/service.d` и `Box-Brain` | [Play Integrity Fork](https://github.com/osm0sis/PlayIntegrityFork) `v19+` |
| Pay Security Bypass `v1.0.4` | Крашит Mir Pay с `AssertionError` (`AndroidVMTools` знает максимум SDK 36) | Удалил, Mir Pay работает без него |
| Vector `v2.2 (3080)` | Загоняет `system_server` в цикл перезагрузок | [Vector](https://github.com/JingMatrix/Vector) `canary-3119+` (с патчем) |

### Симлинк `libbinder.so` в Android 17 (почему падают Tricky Store OSS и Vector)

Сначала проверьте свою прошивку:

```sh
adb shell "readlink -f /system/lib64/libbinder.so"
```

Если команда вывела `/system/lib64/libbinder.so`, обычные сборки Tricky Store OSS и Vector встанут без патчей.

На Android 17 Canary (`ZP11.261016.008`) выводится `/system/lib64/libcore_bundle.so`. Линкер в `dl_iterate_phdr` отдаёт реальный путь к бандлу вместо `libbinder.so`, и на этом спотыкаются сразу два модуля:

1. `Tricky Store OSS v3.1.0` загружает `libTrickyStoreOSS.so` в `keystore2`, после чего загрузчик PLTI валится с `Failed to find libbinder.so via dl_iterate_phdr` и `Binder interception initialization failed`. Демон `TrickyStoreOSS` падает с кодом 1 сразу при старте. Подвох в том, что `/data/adb/tricky_store/tee_status` при этом продолжает показывать `teeBroken=false`, а `libTrickyStoreOSS.so` видна в `/proc/$(pidof keystore2)/maps`. Поверхностная проверка выглядит зелёной, хотя перехват аттестации полностью мёртв.
2. `Vector canary-3119` ловит ту же ошибку в `libzygisk.so` (`Could not find any mappings for libbinder.so`), оставляет ID вызывающего равным `0`, и мост в `system_server` сбрасывает вызовы (`Vector reached system_server but its bridge never answered`).

Оба скрипта в папке `scripts/` находят единственную отдельную 12-байтовую строку `"libbinder.so"` внутри `.rodata` и меняют её на `"re_bundle.so"` (те же 12 байт, совпадает только с `libcore_bundle.so` среди бандлов Android 17). Секцию `.dynstr` (`DT_NEEDED`) скрипты не трогают и проверяют, что она не изменилась ни на байт.

В ветке `main` репозитория `beakthoven/TrickyStoreOSS` поддержку `libcore_bundle.so` уже добавили, просто после тега `v3.1.0` новый релиз ещё не выходил. На свежих сборках Tricky Store OSS и Vector сначала прогоняйте `--dry-run`: если библиотека уже знает про `libcore_bundle.so`, скрипт сам остановится и напишет, что патч не нужен.

### Резервная копия и выход из бутлупа

Перед заменой модулей скопируйте `/data/adb`:

```sh
adb shell "su -c 'mkdir -p /data/adb/backup && cp -a /data/adb/modules /data/adb/tricky_store /data/adb/lspd /data/adb/backup/'"
```

Если после установки телефон уйдёт в бутлуп, зажмите кнопку уменьшения громкости на старте. KernelSU / ReSukiSU загрузится в безопасном режиме с отключёнными модулями. Если ADB уже подхватился, проблемный модуль можно выключить точечно: `/data/adb/ksud module disable <id_модуля>`.

### Настройка ReSukiSU и ловушка `.allowlist`

Nohello сам прячет маунты в Zygisk и конфликтует с ядерным `kernel_umount`. Выключите `kernel_umount`, а `selinux_hide` оставьте включённым:

```sh
adb shell "su -c '/data/adb/ksud feature set kernel_umount 0 && /data/adb/ksud feature set selinux_hide 1 && /data/adb/ksud feature save'"
```

Проверьте `/data/adb/ksud feature list`: включены `su_compat`, `selinux_hide`, `sulog` и `adb_root`, напротив `kernel_umount` стоит `[DISABLED]`.

Отдельный нюанс с профилями приложений (App Profiles) в ReSukiSU: не создавайте для банков, платёжек или мессенджеров кастомный профиль без root с выключенным `umount`. Это добавляет запись `umount_modules=0` в `/data/adb/ksu/.allowlist` и ломает размонтирование для этого пакета. Приложения, от которых прячете root, должны оставаться на стандартном профиле без прав root.

### Основные модули

Если `readlink -f /system/lib64/libbinder.so` показал `/system/lib64/libcore_bundle.so`, сначала пропатчите официальный архив `Tricky-Store-OSS-v3.1.0` на ПК:

```sh
python scripts/patch_trickystore_a17.py Tricky-Store-OSS-v3.1.0-172-41383f5-Release.zip -o Tricky-Store-OSS-v3.1.0-a17-patched.zip
```

Если стоковый `v3.1.0` уже стоит на телефоне, этому же скрипту можно скормить вытянутый `/data/adb/modules/tricky_store/libTrickyStoreOSS.so` (только сначала сохраните оригинал).

Установите все пять модулей в ReSukiSU подряд и перезагрузите телефон один раз:

1. [Zygisk Next](https://github.com/Dr-TSNG/ZygiskNext) (`1.5.3` или новее). `Enforce DenyList` в WebUI должен быть выключен, иначе отвалятся Nohello, HMA-OSS и Vector.
2. [Nohello](https://github.com/MhmRdd/NoHello) (`v0.0.7` или новее). С Zygisk Next `>= 521` сам создаёт `/data/adb/nohello/no_clr_ptracemsg` и `/data/adb/nohello/no_dirtyro_ar`.
3. [HMA-OSS](https://github.com/frknkrc44/HMA-OSS) (`oss-177` или новее): прошейте `HMA-OSS-ZYGISK-*.zip` и поставьте APK менеджера.
4. [Tricky Store OSS](https://github.com/beakthoven/TrickyStoreOSS) (пропатченный `v3.1.0` или более новый релиз с поддержкой `libcore_bundle.so`).
5. [Play Integrity Fork](https://github.com/osm0sis/PlayIntegrityFork) (`v19` или новее).

### Конфиги Tricky Store OSS и Play Integrity Fork

Положите свой действующий, не отозванный ключ в `/data/adb/tricky_store/keybox.xml`. Срок действия сертификатов лучше проверить через `openssl` сразу, чтобы не искать поломку в модулях из-за мёртвого ключа.

Скопируйте шаблоны из `templates/`:

- `templates/security_patch.txt` -> `/data/adb/tricky_store/security_patch.txt`. Дата должна совпадать с `getprop ro.build.version.security_patch`.
- `templates/target.txt` -> `/data/adb/tricky_store/target.txt`. Допишите в конец нужные банки, платёжки или мессенджеры с `!` на конце (например `ru.nspk.mirpay!` или `com.whatsapp!`). Весь список установленных программ туда пихать не нужно.
- `templates/custom.pif.prop` -> `/data/adb/modules/playintegrityfix/custom.pif.prop`. При рабочем `keybox.xml` оставьте `spoofProvider=0`, чтобы PIF не перебивал аппаратную аттестацию.

Нажмите Action у Play Integrity Fork (или перезагрузитесь).

### HMA-OSS

Проще настроить прямо в приложении на телефоне:

1. Откройте HMA-OSS и убедитесь, что системный сервис загружен в режиме 1 (`Mode 1`).
2. В Template Manage создайте шаблон чёрного списка с именем `root_hide`.
3. Добавьте в `root_hide` root-менеджеры (`com.resukisu.resukisu`, а также `com.topjohnwu.magisk`, если остался), сам `org.frknkrc44.hma_oss`, терминал, блокировщики хостов и все APK Xposed-модулей.
4. В App Manage выберите `ru.nspk.mirpay`, `com.android.vending`, `com.google.android.gms`, `com.google.android.apps.walletnfcrel`, ваши банки и нужные мессенджеры. Включите скрытие, выберите `Blacklist`, включите `Exclude System Apps` и примените шаблон `root_hide`.

Если подсовывать отредактированный `templates/hma-config.example.json` напрямую в `/data/misc/hide_my_applist_bwpjugplvntusdea/config.json`, поправьте владельца и права, иначе `system_server` конфиг не прочитает:

```sh
adb shell "su -c 'chown system:system /data/misc/hide_my_applist_bwpjugplvntusdea/config.json && chmod 0600 /data/misc/hide_my_applist_bwpjugplvntusdea/config.json'"
```

### Mir Pay, банки и WhatsApp

Если Mir Pay уже открывался до настройки скрытия, он запоминает ошибку `0111000003` в `/data/data/ru.nspk.mirpay` и продолжает её показывать даже после починки модулей. Сбросьте данные приложения один раз:

```sh
adb shell "su -c 'pm clear ru.nspk.mirpay'"
```

Запустите Mir Pay, выдайте доступ к геолокации и проверьте, что открылся экран добавления карты. `Pay Security Bypass v1.0.4` на Android 17 не ставьте. Антифрод в банках обновляется без предупреждения, а сам вход в приложение ещё не гарантирует токенизацию карты и оплату по NFC на терминале, так что проверяйте оплату на своём телефоне.

По WhatsApp и похожим приложениям со связкой Play Integrity и серверных проверок: сначала убедитесь, что проходит `STRONG`, добавьте `com.whatsapp!` в `target.txt` и скройте root-приложения в HMA-OSS. Если до этого было много неудачных попыток входа со сломанной аттестацией или через публичные прокси, серверы WhatsApp могут временно держать блокировку уже на своей стороне даже при зелёном Play Integrity.

### Vector (Xposed), по желанию

Скачайте `Vector-v2.2-3119-Release.zip` со страницы [JingMatrix/Vector Releases](https://github.com/JingMatrix/Vector/releases). Если `readlink -f /system/lib64/libbinder.so` ведёт на `libcore_bundle.so`, пропатчите архив до установки:

```sh
python scripts/patch_vector_a17.py Vector-v2.2-3119-Release.zip -o Vector-v2.2-3119-a17-patched.zip
```

Скрипт меняет строку в `.rodata` внутри `lib/arm64-v8a/libzygisk.so` и пересчитывает `lib/arm64-v8a/libzygisk.so.sha256` в архиве, чтобы установщик `customize.sh` принял хэш. Прошейте полученный ZIP в ReSukiSU и перезагрузитесь.

Менеджер Vector открывается из уведомления, через кнопку Action в ReSukiSU или кодом `*#*#832867#*#*` в звонилке. В Scope каждого Xposed-модуля отмечайте только те приложения, которым он реально нужен, а APK самих модулей добавляйте в `root_hide` внутри HMA-OSS. Перед обновлением на более свежие сборки Vector прогоняйте новый ZIP через `--dry-run`.

### Как проверить, что всё реально работает

После перезагрузки прогоните по ADB:

```sh
adb shell "su -c 'ps -A | grep -i tricky'"
adb shell "su -c 'logcat -d TrickyStoreOSS:W *:S'"
adb shell "su -c 'cat /data/adb/tricky_store/tee_status'"
adb shell "su -c '/data/adb/modules/zygisksu/bin/zygiskd status'"
adb shell "su -c '/data/adb/ksud module list'"
adb shell "su -c '/data/adb/modules/zygisk_vector/cli status'"
```

Что должно быть в выводе:

- `ps -A | grep -i tricky` показывает живой процесс `TrickyStoreOSS`. Пустой вывод означает, что демон упал при загрузке.
- `logcat -d TrickyStoreOSS:W *:S` пустой (нет ни `Failed to find libbinder.so`, ни `CannotAttestIds`).
- `tee_status` выводит `teeBroken=false`.
- `zygiskd status` показывает `inject_state:1`, `modules_with_issue:0` и `enforce_denylist:0`.
- В `ksud module list` у Nohello растёт счётчик размонтирований, а у HMA-OSS Zygisk написано `[System service loaded]`.
- `vector/cli status` выводит `Framework Version: 2.2` (`3119`), в `/data/adb/lspd/log/verbose_*.log` есть `Successfully injected Vector IPC binder for applications.`, а `system_server` не перезапускается.

В конце проверьте реальный ответ Google Play Integrity: Google Play -> Настройки -> О приложении -> 7 раз нажать на версию Play Store -> Общие -> Для разработчиков -> Проверка целостности. С живым `keybox.xml` и пропатченным Tricky Store OSS придёт:

```text
Labels: [MEETS_BASIC_INTEGRITY, MEETS_DEVICE_INTEGRITY, MEETS_STRONG_INTEGRITY]
```
