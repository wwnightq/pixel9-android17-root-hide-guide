# Pixel 9 на Android 17 Canary: скрытие root, Strong Integrity и Vector

[Главная страница (EN + RU)](README.md)

Рабочие заметки, шаблоны конфигов и два патчера под Google Pixel 9 (`tokay`) на Android 17 Canary (`ZP11.261016.008`, API 37, патч `2026-11-05`) с ReSukiSU `v4.2.0-rc3`. В этой связке Google Play отдаёт `BASIC`, `DEVICE` и `STRONG`, Mir Pay и банки открываются без жалоб на root, а Vector (Xposed) работает без падений `system_server`.

В репозитории лежат только скрипты и шаблоны конфигов. Сами модули берите с официальных страниц авторов на GitHub, а свой `/data/adb/tricky_store/keybox.xml` никуда не выкладывайте.

## На чём проверялось

| Компонент | Версия |
| :--- | :--- |
| Устройство | Google Pixel 9 (`tokay`) |
| Прошивка | Android 17 Canary (`ZP11.261016.008`, SDK 37, патч `2026-11-05`) |
| Root | ReSukiSU `v4.2.0-rc3` (`ksud 35171`) |
| Zygisk | Zygisk Next `1.5.3` (`880`, `linker: builtin`, DenyList выключен) |
| Скрытие | Nohello `v0.0.7` (`53`), HMA-OSS Zygisk `oss-177` |
| Аттестация | Tricky Store OSS `v3.1.0` (`172`, с патчем), Play Integrity Fork `v19` |
| Xposed (по желанию) | Vector `v2.2 canary-3119` (с патчем) |

## Что сломалось на Android 17 Canary

Модули, которые нормально жили на Android 15 и 16, на SDK 37 отвалились:

| Модуль | Что пошло не так | Что поставил взамен |
| :--- | :--- | :--- |
| NeoZygisk `v2.4` | Ошибки `solist` и нестабильный `system_server` | [Zygisk Next](https://github.com/Dr-TSNG/ZygiskNext) `1.5.3+` |
| Закрытый Tricky Store `v1.4.1` | Ломает EC-аттестацию ключей на SDK 37 | [Tricky Store OSS](https://github.com/beakthoven/TrickyStoreOSS) `v3.1.0+` (с патчем) |
| Integrity Box | Тащит лишние скрипты в `/data/adb/service.d` и `Box-Brain` | [Play Integrity Fork](https://github.com/osm0sis/PlayIntegrityFork) `v19+` |
| Pay Security Bypass `v1.0.4` | Крашит Mir Pay с `AssertionError` (`AndroidVMTools` знает максимум SDK 36) | Удалил, Mir Pay работает без него |
| Vector `v2.2 (3080)` | Загоняет `system_server` в цикл перезагрузок | [Vector](https://github.com/JingMatrix/Vector) `canary-3119+` (с патчем) |

## Симлинк `libbinder.so` в Android 17 (почему падают Tricky Store OSS и Vector)

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

## Резервная копия и выход из бутлупа

Перед заменой модулей скопируйте `/data/adb`:

```sh
adb shell "su -c 'mkdir -p /data/adb/backup && cp -a /data/adb/modules /data/adb/tricky_store /data/adb/lspd /data/adb/backup/'"
```

Если после установки телефон уйдёт в бутлуп, зажмите кнопку уменьшения громкости на старте. KernelSU / ReSukiSU загрузится в безопасном режиме с отключёнными модулями. Если ADB уже подхватился, проблемный модуль можно выключить точечно: `/data/adb/ksud module disable <id_модуля>`.

## Настройка ReSukiSU и ловушка `.allowlist`

Nohello сам прячет маунты в Zygisk и конфликтует с ядерным `kernel_umount`. Выключите `kernel_umount`, а `selinux_hide` оставьте включённым:

```sh
adb shell "su -c '/data/adb/ksud feature set kernel_umount 0 && /data/adb/ksud feature set selinux_hide 1 && /data/adb/ksud feature save'"
```

Проверьте `/data/adb/ksud feature list`: включены `su_compat`, `selinux_hide`, `sulog` и `adb_root`, напротив `kernel_umount` стоит `[DISABLED]`.

Отдельный нюанс с профилями приложений (App Profiles) в ReSukiSU: не создавайте для банков, платёжек или мессенджеров кастомный профиль без root с выключенным `umount`. Это добавляет запись `umount_modules=0` в `/data/adb/ksu/.allowlist` и ломает размонтирование для этого пакета. Приложения, от которых прячете root, должны оставаться на стандартном профиле без прав root.

## Основные модули

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

## Конфиги Tricky Store OSS и Play Integrity Fork

Положите свой действующий, не отозванный ключ в `/data/adb/tricky_store/keybox.xml`. Срок действия сертификатов лучше проверить через `openssl` сразу, чтобы не искать поломку в модулях из-за мёртвого ключа.

Скопируйте шаблоны из `templates/`:

- `templates/security_patch.txt` -> `/data/adb/tricky_store/security_patch.txt`. Дата должна совпадать с `getprop ro.build.version.security_patch`.
- `templates/target.txt` -> `/data/adb/tricky_store/target.txt`. Допишите в конец нужные банки, платёжки или мессенджеры с `!` на конце (например `ru.nspk.mirpay!` или `com.whatsapp!`). Весь список установленных программ туда пихать не нужно.
- `templates/custom.pif.prop` -> `/data/adb/modules/playintegrityfix/custom.pif.prop`. При рабочем `keybox.xml` оставьте `spoofProvider=0`, чтобы PIF не перебивал аппаратную аттестацию.

Нажмите Action у Play Integrity Fork (или перезагрузитесь).

## HMA-OSS

Проще настроить прямо в приложении на телефоне:

1. Откройте HMA-OSS и убедитесь, что системный сервис загружен в режиме 1 (`Mode 1`).
2. В Template Manage создайте шаблон чёрного списка с именем `root_hide`.
3. Добавьте в `root_hide` root-менеджеры (`com.resukisu.resukisu`, а также `com.topjohnwu.magisk`, если остался), сам `org.frknkrc44.hma_oss`, терминал, блокировщики хостов и все APK Xposed-модулей.
4. В App Manage выберите `ru.nspk.mirpay`, `com.android.vending`, `com.google.android.gms`, `com.google.android.apps.walletnfcrel`, ваши банки и нужные мессенджеры. Включите скрытие, выберите `Blacklist`, включите `Exclude System Apps` и примените шаблон `root_hide`.

Если подсовывать отредактированный `templates/hma-config.example.json` напрямую в `/data/misc/hide_my_applist_bwpjugplvntusdea/config.json`, поправьте владельца и права, иначе `system_server` конфиг не прочитает:

```sh
adb shell "su -c 'chown system:system /data/misc/hide_my_applist_bwpjugplvntusdea/config.json && chmod 0600 /data/misc/hide_my_applist_bwpjugplvntusdea/config.json'"
```

## Mir Pay, банки и WhatsApp

Если Mir Pay уже открывался до настройки скрытия, он запоминает ошибку `0111000003` в `/data/data/ru.nspk.mirpay` и продолжает её показывать даже после починки модулей. Сбросьте данные приложения один раз:

```sh
adb shell "su -c 'pm clear ru.nspk.mirpay'"
```

Запустите Mir Pay, выдайте доступ к геолокации и проверьте, что открылся экран добавления карты. `Pay Security Bypass v1.0.4` на Android 17 не ставьте. Антифрод в банках обновляется без предупреждения, а сам вход в приложение ещё не гарантирует токенизацию карты и оплату по NFC на терминале, так что проверяйте оплату на своём телефоне.

По WhatsApp и похожим приложениям со связкой Play Integrity и серверных проверок: сначала убедитесь, что проходит `STRONG`, добавьте `com.whatsapp!` в `target.txt` и скройте root-приложения в HMA-OSS. Если до этого было много неудачных попыток входа со сломанной аттестацией или через публичные прокси, серверы WhatsApp могут временно держать блокировку уже на своей стороне даже при зелёном Play Integrity.

## Vector (Xposed), по желанию

Скачайте `Vector-v2.2-3119-Release.zip` со страницы [JingMatrix/Vector Releases](https://github.com/JingMatrix/Vector/releases). Если `readlink -f /system/lib64/libbinder.so` ведёт на `libcore_bundle.so`, пропатчите архив до установки:

```sh
python scripts/patch_vector_a17.py Vector-v2.2-3119-Release.zip -o Vector-v2.2-3119-a17-patched.zip
```

Скрипт меняет строку в `.rodata` внутри `lib/arm64-v8a/libzygisk.so` и пересчитывает `lib/arm64-v8a/libzygisk.so.sha256` в архиве, чтобы установщик `customize.sh` принял хэш. Прошейте полученный ZIP в ReSukiSU и перезагрузитесь.

Менеджер Vector открывается из уведомления, через кнопку Action в ReSukiSU или кодом `*#*#832867#*#*` в звонилке. В Scope каждого Xposed-модуля отмечайте только те приложения, которым он реально нужен, а APK самих модулей добавляйте в `root_hide` внутри HMA-OSS. Перед обновлением на более свежие сборки Vector прогоняйте новый ZIP через `--dry-run`.

## Как проверить, что всё реально работает

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
