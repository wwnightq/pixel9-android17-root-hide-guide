# Pixel 9 (Android 17 Canary): root hiding, Play Integrity, and Vector Xposed / Скрытие root, Play Integrity и Vector

[English version](#english-version) | [Русская версия](#русская-версия) | [Отдельный файл README.ru.md](README.ru.md)

English: Working root-hiding, Play Integrity, and Vector Xposed setup tested on Google Pixel 9 (`tokay`) running Android 17 Canary (`ZP11.261016.008`, API 37, security patch `2026-11-05`) with ReSukiSU `v4.2.0-rc3`. Contains zero keyboxes, zero third-party binaries, and zero personal app data.

По-русски: Проверенная настройка скрытия root, Play Integrity и Xposed-фреймворка Vector для Google Pixel 9 (`tokay`) на Android 17 Canary (`ZP11.261016.008`, API 37, патч безопасности `2026-11-05`) с ReSukiSU `v4.2.0-rc3`. Без `keybox.xml`, сторонних бинарных архивов и личных данных.

---

## English version

[Читать на русском на этой странице](#русская-версия)

This guide covers two goals: keeping payment and banking apps working without root alerts, and running the Vector Xposed framework on Android 17 Canary without causing `system_server` crash loops.

### Disclaimer and privacy notes

Modifying boot images, unlocking the bootloader, and flashing Canary builds carry a risk of data loss or bootloops. Back up your data before making changes.

Do not share your personal `/data/adb/tricky_store/keybox.xml` file. This repository contains zero keyboxes, zero third-party binaries, and zero personal app data. Banking apps update their detection regularly, and running an app without a launch error does not guarantee card tokenization or NFC terminal payments on every setup, so verify payments manually on your own device.

### Tested environment

- Device: Google Pixel 9 (`tokay`)
- OS: Android 17 Canary (`ZP11.261016.008`, `SDK 37`)
- Root manager: ReSukiSU `v4.2.0-rc3` (`ksud 35171`)
- Zygisk implementation: Zygisk Next `1.5.3` (`880`, `linker: builtin`, `enforce_denylist: disabled`)
- Root hiding: Nohello `v0.0.7` (`53`) and HMA-OSS Zygisk `oss-177`
- Keystore and Play Integrity: Tricky Store OSS `v3.1.0` (`172`) and Play Integrity Fork `v19`
- Xposed framework (optional): Vector `v2.2 canary-3119` with the `libcore_bundle.so` patch in `scripts/patch_vector_a17.py`

### Modules to avoid on Android 17 (SDK 37)

Older stacks that work on Android 15 or 16 cause crashes or fail attestation on Android 17 Canary.

| Module | Issue observed on Android 17 Canary | Replacement |
| :--- | :--- | :--- |
| NeoZygisk `v2.4` | `solist` errors and `system_server` instability | [Zygisk Next](https://github.com/Dr-TSNG/ZygiskNext) `1.5.3+` |
| Closed Tricky Store `v1.4.1` | Fails to intercept EC key attestation cleanly on SDK 37 | [Tricky Store OSS](https://github.com/beakthoven/TrickyStoreOSS) `v3.1.0+` |
| Integrity Box | Extra `/data/adb/service.d` scripts and `Box-Brain` bloat | [Play Integrity Fork](https://github.com/osm0sis/PlayIntegrityFork) `v19+` |
| Pay Security Bypass `v1.0.4` | Crashes inside Mir Pay with `AssertionError` (`AndroidVMTools` max SDK is 36) | Remove or disable; native hiding works without it |
| Vector `v2.2 (3080)` | Crash-loops `system_server` on Android 17 Canary | [Vector](https://github.com/JingMatrix/Vector) `canary-3119+` patched for `libcore_bundle.so` |

### Step 1: Back up your existing setup

Before replacing modules, back up `/data/adb` from an elevated ADB shell on your PC.

```sh
adb shell "su -c 'mkdir -p /data/adb/backup && cp -a /data/adb/modules /data/adb/tricky_store /data/adb/lspd /data/adb/backup/'"
```

Remember the bootloop escape hatch in KernelSU / ReSukiSU: holding Volume Down during boot activates Safe Mode and disables all modules. Over ADB, you can disable a single module with `/data/adb/ksud module disable <module_id>`.

### Step 2: Configure ReSukiSU kernel settings

Nohello handles mount hiding in Zygisk space and conflicts with kernel-level auto-unmount. Disable `kernel_umount` in ReSukiSU settings or over ADB, and keep `selinux_hide` enabled:

```sh
adb shell "su -c '/data/adb/ksud feature set kernel_umount 0 && /data/adb/ksud feature set selinux_hide 1 && /data/adb/ksud feature save'"
```

Verify the saved state with `/data/adb/ksud feature list`. Keep `su_compat`, `selinux_hide`, `sulog`, and `adb_root` enabled, and confirm `kernel_umount` shows `[DISABLED]`.

### Step 3: Install the core hiding and integrity modules

Download the official ZIP releases from the authors' GitHub repositories and install them in ReSukiSU (do not reboot between installs; reboot once after all modules are queued):

1. [Zygisk Next](https://github.com/Dr-TSNG/ZygiskNext) (`1.5.3` or newer). Leave `Enforce DenyList` disabled in Zygisk Next WebUI so Nohello and Zygisk modules run cleanly.
2. [Nohello](https://github.com/MhmRdd/NoHello) (`v0.0.7` or newer). When paired with Zygisk Next `>= 521`, Nohello automatically creates `/data/adb/nohello/no_clr_ptracemsg` and `/data/adb/nohello/no_dirtyro_ar`.
3. [HMA-OSS](https://github.com/frknkrc44/HMA-OSS) (`oss-177` or newer): install the `HMA-OSS-ZYGISK-*.zip` module and also install the companion manager APK.
4. [Tricky Store OSS](https://github.com/beakthoven/TrickyStoreOSS) (`v3.1.0` or newer, built for SDK 37).
5. [Play Integrity Fork](https://github.com/osm0sis/PlayIntegrityFork) (`v19` or newer).

Reboot the phone after queuing these five modules.

### Step 4: Configure Play Integrity and Tricky Store OSS

Place your own valid, unrevoked keybox file at `/data/adb/tricky_store/keybox.xml`. Check its certificate expiration dates with `openssl` before relying on it, because expired or Google-revoked keyboxes fail Strong Integrity checks.

Copy the template files from `templates/` in this repository:

- Copy `templates/security_patch.txt` to `/data/adb/tricky_store/security_patch.txt` and make sure the date matches your current OS security patch level (`getprop ro.build.version.security_patch`).
- Copy `templates/target.txt` to `/data/adb/tricky_store/target.txt` and add the package names of your banking and payment apps with a trailing `!` (for example, `ru.nspk.mirpay!`). Keep the list focused on apps that need attestation spoofing.
- Copy `templates/custom.pif.prop` to `/data/adb/modules/playintegrityfix/custom.pif.prop`. For Pixel 9 Android 17 Canary with a working Tricky Store keybox, set `spoofProvider=0` so Play Integrity Fork does not override hardware attestation. (If you use a device without a valid keybox and only want Device integrity on fallback paths, adjust `custom.pif.prop` per Play Integrity Fork's upstream instructions.)

Run the Play Integrity Fork action or reboot, then confirm Tricky Store OSS is healthy:

```sh
adb shell "su -c 'cat /data/adb/tricky_store/tee_status && grep -i tricky /proc/\$(pidof keystore2)/maps'"
```

You should see `teeBroken=false` and `libTrickyStoreOSS.so` mapped inside `keystore2`.

### Step 5: Configure HMA-OSS

You can set this up either in the HMA-OSS Android app or by pushing the JSON config.

Using the HMA-OSS app UI:

1. Open HMA-OSS and check that the module status shows the system service loaded in Mode 1.
2. Go to Template Manage and create a blacklist template named `root_hide`.
3. Add your root managers, HMA-OSS itself, terminal/hosts tools, and any Xposed module APKs to `root_hide` (`com.resukisu.resukisu`, `org.frknkrc44.hma_oss`, `me.itejo443.bindhosts`, `com.termux`, and any leftover `com.topjohnwu.magisk` if installed).
4. Go to App Manage, select your payment, banking, and Google Play apps (`ru.nspk.mirpay`, `com.android.vending`, `com.google.android.gms`, `com.google.android.apps.walletnfcrel`, and your local bank apps), enable Hiding, set Work Mode to Blacklist, enable Exclude System Apps, and apply `root_hide`.

Using the template file instead:

If you adapt `templates/hma-config.example.json` to `/data/misc/hide_my_applist_bwpjugplvntusdea/config.json`, fix file ownership and permissions so `system_server` can read it:

```sh
adb shell "su -c 'chown system:system /data/misc/hide_my_applist_bwpjugplvntusdea/config.json && chmod 0600 /data/misc/hide_my_applist_bwpjugplvntusdea/config.json'"
```

### Step 6: Fix cached errors in Mir Pay and banking apps

If you previously launched Mir Pay without full hiding, it caches the root failure inside `/data/data/ru.nspk.mirpay` and keeps showing error `0111000003` even after you fix the modules.

Back up the app data if needed, clear it once, and relaunch:

```sh
adb shell "su -c 'pm clear ru.nspk.mirpay'"
```

Launch Mir Pay, grant location permission when prompted, and verify it reaches the "Add card" home screen instead of `0111000003`. Do not enable `Pay Security Bypass v1.0.4` on Android 17. Test your other banking apps as well.

### Step 7: Optional Vector (Xposed) setup on Android 17 Canary

#### Why Vector fails on Android 17 Canary

In Android 17 Canary (`ZP11.261016.008`), `/system/lib64/libbinder.so` is a symlink to `/system/lib64/libcore_bundle.so`. Vector `canary-3119` asks the dynamic linker via `dl_iterate_phdr` for `libbinder.so`, gets real paths (`libcore_bundle.so`), fails with `Could not find any mappings for libbinder.so`, sets caller ID to `0`, and rejects all bridge calls from `VectorDaemon` (`Vector reached system_server but its bridge never answered`).

#### Check whether your ROM needs the patch

Run this on your device first:

```sh
adb shell "readlink -f /system/lib64/libbinder.so"
```

- If the output is `/system/lib64/libbinder.so`, install stock [Vector](https://github.com/JingMatrix/Vector) `canary-3119` directly.
- If the output is `/system/lib64/libcore_bundle.so`, patch the official release ZIP before flashing.

#### Patch and install Vector

Download `Vector-v2.2-3119-Release.zip` from [JingMatrix/Vector Releases](https://github.com/JingMatrix/Vector/releases), run the script on your PC, and install the output ZIP:

```sh
python scripts/patch_vector_a17.py Vector-v2.2-3119-Release.zip -o Vector-v2.2-3119-a17-patched.zip
```

You can also run with `--dry-run` first to inspect the exact offset and SHA-256 checksums without creating a file. The script patches only the 12-byte library lookup string (`"libbinder.so"` to `"re_bundle.so"`) inside `lib/arm64-v8a/libzygisk.so` and updates `lib/arm64-v8a/libzygisk.so.sha256` inside the ZIP so `customize.sh` passes checksum verification.

Install `Vector-v2.2-3119-a17-patched.zip` in ReSukiSU and reboot. Open Vector Manager via the system notification, ReSukiSU module Action button, or dialing `*#*#832867#*#*`, and assign each Xposed module only the apps it needs in Scope. Keep all Xposed module APKs hidden inside your HMA-OSS `root_hide` template.

Note on updates: do not flash newer unpatched Vector ZIPs over your patched build until upstream `JingMatrix/Vector` adds support for `libcore_bundle.so`. Always check a new release with `--dry-run` first.

### Verification commands

After rebooting, run these checks via ADB to verify every layer:

```sh
adb shell "su -c '/data/adb/modules/zygisksu/bin/zygiskd status'"
adb shell "su -c '/data/adb/ksud module list'"
adb shell "su -c '/data/adb/ksud feature list'"
adb shell "su -c 'cat /data/adb/tricky_store/tee_status'"
adb shell "su -c '/data/adb/modules/zygisk_vector/cli status'"
```

Expected signals:

- `zygiskd status` reports `inject_state:1`, `modules_with_issue:0`, and `enforce_denylist:0`.
- `Nohello` description shows positive unmount counts.
- `HMA-OSS Zygisk` description shows `[System service loaded]`, and `/data/misc/hide_my_applist_bwpjugplvntusdea/filter_count.json` increments for Play Services, Play Store, and your hidden banks.
- `tee_status` shows `teeBroken=false`.
- `vector-cli status` shows `Framework Version: 2.2`, `Version Code: 3119`, and `/data/adb/lspd/log/verbose_*.log` logs `Successfully injected Vector IPC binder for applications.` without `system_server` restarts.

---

## Русская версия

[Read in English on this page](#english-version)

Задача состоит из двух частей: сделать так, чтобы банковские приложения и Mir Pay запускались без жалоб на root, и запустить Vector на Android 17 Canary без циклического падения `system_server`.

### Важное предупреждение и безопасность

Разблокировка загрузчика, модификация загрузочных образов, установка root-модулей и использование Canary-сборок ОС всегда несут риск потери данных или циклической перезагрузки. Перед началом работы обязательно сделайте резервную копию важных данных.

Никогда не выкладывайте в сеть свой файл `/data/adb/tricky_store/keybox.xml`. В этом репозитории нет чужих ключей, скомпилированных бинарных файлов сторонних модулей и личных данных. Проверки антифрода в банках постоянно обновляются, а успешный запуск приложения еще не гарантирует привязку конкретной карты и прохождение NFC-оплаты на терминале, поэтому проверяйте оплату вручную на своем устройстве.

### Проверенное окружение

- Устройство: Google Pixel 9 (`tokay`)
- Система: Android 17 Canary (`ZP11.261016.008`, `SDK 37`)
- Root-менеджер: ReSukiSU `v4.2.0-rc3` (`ksud 35171`)
- Реализация Zygisk: Zygisk Next `1.5.3` (`880`, `linker: builtin`, `enforce_denylist: disabled`)
- Скрытие root и списка приложений: Nohello `v0.0.7` (`53`) и HMA-OSS Zygisk `oss-177`
- Keystore и Play Integrity: Tricky Store OSS `v3.1.0` (`172`) и Play Integrity Fork `v19`
- Xposed-фреймворк (по желанию): Vector `v2.2 canary-3119` с патчем для `libcore_bundle.so` из `scripts/patch_vector_a17.py`

### Какие модули не подходят для Android 17 (SDK 37)

Привычные связки с Android 15 и 16 на Android 17 Canary вызывают сбои или не проходят проверки.

| Модуль | Проблема на Android 17 Canary | Что ставить взамен |
| :--- | :--- | :--- |
| NeoZygisk `v2.4` | Ошибки `solist` и нестабильность `system_server` | [Zygisk Next](https://github.com/Dr-TSNG/ZygiskNext) `1.5.3+` |
| Закрытый Tricky Store `v1.4.1` | На SDK 37 некорректно перехватывает EC-аттестацию ключей | [Tricky Store OSS](https://github.com/beakthoven/TrickyStoreOSS) `v3.1.0+` |
| Integrity Box | Лишние фоновые скрипты в `/data/adb/service.d` и `Box-Brain` | [Play Integrity Fork](https://github.com/osm0sis/PlayIntegrityFork) `v19+` |
| Pay Security Bypass `v1.0.4` | Крашится внутри Mir Pay с `AssertionError` (`AndroidVMTools` поддерживает максимум SDK 36) | Удалить или отключить; нативное скрытие работает без него |
| Vector `v2.2 (3080)` | Вызывает цикл перезапусков `system_server` на Android 17 Canary | [Vector](https://github.com/JingMatrix/Vector) `canary-3119+` с патчем под `libcore_bundle.so` |

### Шаг 1. Сделайте резервную копию

Перед удалением или заменой модулей сохраните текущие конфигурации на устройстве через ADB:

```sh
adb shell "su -c 'mkdir -p /data/adb/backup && cp -a /data/adb/modules /data/adb/tricky_store /data/adb/lspd /data/adb/backup/'"
```

Запомните способ аварийного отката в KernelSU / ReSukiSU: если во время загрузки удерживать клавишу уменьшения громкости, система загрузится в безопасном режиме с отключенными модулями. Если ADB уже доступен, отдельный модуль можно отключить командой `/data/adb/ksud module disable <id_модуля>`.

### Шаг 2. Настройте функции ядра в ReSukiSU

Модуль Nohello сам размонтирует следы модулей внутри процессов, поэтому встроенное ядерное размонтирование `kernel_umount` нужно отключить во избежание конфликтов, а `selinux_hide` оставить включенным:

```sh
adb shell "su -c '/data/adb/ksud feature set kernel_umount 0 && /data/adb/ksud feature set selinux_hide 1 && /data/adb/ksud feature save'"
```

Проверьте результат командой `/data/adb/ksud feature list`. Включенными остаются `su_compat`, `selinux_hide`, `sulog` и `adb_root`, а напротив `kernel_umount` должно быть `[DISABLED]`.

### Шаг 3. Установите базовые модули скрытия и аттестации

Скачайте официальные ZIP-архивы со страниц разработчиков на GitHub и установите их через ReSukiSU. Перезагружать телефон после каждого модуля не нужно, достаточно одной перезагрузки в конце списка:

1. [Zygisk Next](https://github.com/Dr-TSNG/ZygiskNext) (`1.5.3` или новее). В WebUI модуля `Enforce DenyList` должен быть выключен, иначе перестанут работать модули вроде Vector и HMA-OSS.
2. [Nohello](https://github.com/MhmRdd/NoHello) (`v0.0.7` или новее). В паре с Zygisk Next `>= 521` модуль автоматически создает нужные флаги `/data/adb/nohello/no_clr_ptracemsg` и `/data/adb/nohello/no_dirtyro_ar`.
3. [HMA-OSS](https://github.com/frknkrc44/HMA-OSS) (`oss-177` или новее): установите модуль `HMA-OSS-ZYGISK-*.zip` и отдельно приложение-менеджер (APK).
4. [Tricky Store OSS](https://github.com/beakthoven/TrickyStoreOSS) (`v3.1.0` или новее, с поддержкой SDK 37).
5. [Play Integrity Fork](https://github.com/osm0sis/PlayIntegrityFork) (`v19` или новее).

После установки всех пяти модулей перезагрузите смартфон.

### Шаг 4. Настройте Play Integrity и Tricky Store OSS

Положите ваш действующий, не отозванный ключ в `/data/adb/tricky_store/keybox.xml`. Заранее проверьте срок действия сертификатов внутри `keybox.xml` через `openssl`, так как просроченные или отозванные Google ключи не пройдут Strong Integrity.

Скопируйте шаблоны из папки `templates/` этого репозитория:

- Скопируйте `templates/security_patch.txt` в `/data/adb/tricky_store/security_patch.txt` и при необходимости обновите дату так, чтобы она совпадала с вашим системным патчем безопасности (`getprop ro.build.version.security_patch`).
- Скопируйте `templates/target.txt` в `/data/adb/tricky_store/target.txt` и добавьте в конец имена пакетов ваших банковских и платежных приложений с символом `!` на конце (например, `ru.nspk.mirpay!`). Держите в списке только те приложения, которым действительно нужна подмена аттестации.
- Скопируйте `templates/custom.pif.prop` в `/data/adb/modules/playintegrityfix/custom.pif.prop`. Для связки Pixel 9 на Android 17 Canary с рабочим `keybox.xml` в Tricky Store OSS оставьте `spoofProvider=0`, чтобы PIF не ломал аппаратную аттестацию.

Выполните Action у Play Integrity Fork (или перезагрузите телефон), затем проверьте работу Tricky Store OSS:

```sh
adb shell "su -c 'cat /data/adb/tricky_store/tee_status && grep -i tricky /proc/\$(pidof keystore2)/maps'"
```

В выводе должно быть `teeBroken=false`, а в картах памяти `keystore2` должна присутствовать библиотека `libTrickyStoreOSS.so`.

### Шаг 5. Настройте HMA-OSS

Настроить фильтрацию проще всего через интерфейс приложения HMA-OSS на телефоне.

Через приложение:

1. Откройте HMA-OSS и убедитесь, что системный сервис загружен в режиме 1 (`Mode 1`).
2. Перейдите в управление шаблонами (Template Manage) и создайте шаблон черного списка с именем `root_hide`.
3. Добавьте в `root_hide` root-менеджеры (`com.resukisu.resukisu`, а также `com.topjohnwu.magisk`, если остался APK), сам `org.frknkrc44.hma_oss`, терминал, блокировщики хостов и все установленные APK Xposed-модулей.
4. Перейдите в управление приложениями (App Manage), выберите платежные приложения, банки и сервисы Google (`ru.nspk.mirpay`, `com.android.vending`, `com.google.android.gms`, `com.google.android.apps.walletnfcrel` и ваши банки), включите скрытие, выберите режим черного списка (`Blacklist`), включите исключение системных приложений (`Exclude System Apps`) и примените шаблон `root_hide`.

Если вы используете шаблон `templates/hma-config.example.json` напрямую в `/data/misc/hide_my_applist_bwpjugplvntusdea/config.json`, обязательно назначьте владельца `system:system` и права `0600`, иначе `system_server` не загрузит конфиг:

```sh
adb shell "su -c 'chown system:system /data/misc/hide_my_applist_bwpjugplvntusdea/config.json && chmod 0600 /data/misc/hide_my_applist_bwpjugplvntusdea/config.json'"
```

### Шаг 6. Сбросьте кэш ошибки в Mir Pay и проверьте банки

Если Mir Pay уже запускался до настройки скрытия, он сохраняет ошибку `0111000003` в локальных данных `/data/data/ru.nspk.mirpay` и продолжает показывать её даже после починки модулей.

После настройки всех шагов выше очистите данные Mir Pay (при необходимости предварительно скопировав старую папку):

```sh
adb shell "su -c 'pm clear ru.nspk.mirpay'"
```

Откройте Mir Pay, выдайте запрошенное разрешение на геолокацию и проверьте переход на главный экран добавления карты без ошибки `0111000003`. Модуль `Pay Security Bypass v1.0.4` на Android 17 включать не нужно. После этого запустите и проверьте ваши банковские приложения.

### Шаг 7. Установка Vector (Xposed) на Android 17 Canary (по желанию)

#### Почему Vector не работает без патча

В прошивке Android 17 Canary (`ZP11.261016.008`) файл `/system/lib64/libbinder.so` стал симлинком на `/system/lib64/libcore_bundle.so`. Модуль `Vector canary-3119` запрашивает загруженные библиотеки у линкера через `dl_iterate_phdr`, получает реальные пути (`libcore_bundle.so`), не находит строку `"libbinder.so"` и выдает ошибку `Could not find any mappings for libbinder.so`. В результате функция `BinderCaller::GetId()` всегда возвращает `0`, и хук `IPCBridge` в `system_server` отклоняет все подключения от `VectorDaemon` с ошибкой `Vector reached system_server but its bridge never answered`.

#### Проверка, нужен ли патч именно вашей прошивке

Выполните на телефоне команду:

```sh
adb shell "readlink -f /system/lib64/libbinder.so"
```

- Если вернулось `/system/lib64/libbinder.so`, можно сразу ставить обычный [Vector](https://github.com/JingMatrix/Vector) `canary-3119`.
- Если вернулось `/system/lib64/libcore_bundle.so`, архив перед установкой нужно пропатчить.

#### Патчинг и установка Vector

Скачайте официальный `Vector-v2.2-3119-Release.zip` со страницы [JingMatrix/Vector Releases](https://github.com/JingMatrix/Vector/releases), запустите скрипт на ПК и установите полученный архив:

```sh
python scripts/patch_vector_a17.py Vector-v2.2-3119-Release.zip -o Vector-v2.2-3119-a17-patched.zip
```

При желании сначала запустите скрипт с флагом `--dry-run`, чтобы проверить найденное смещение и хэши без создания файла. Скрипт меняет ровно 12 байт имени библиотеки (`"libbinder.so"` на `"re_bundle.so"`) в `lib/arm64-v8a/libzygisk.so` и обновляет `lib/arm64-v8a/libzygisk.so.sha256` внутри ZIP, чтобы установщик `customize.sh` прошел проверку контрольной суммы.

Установите `Vector-v2.2-3119-a17-patched.zip` в ReSukiSU и перезагрузите смартфон. Интерфейс Vector открывается через системное уведомление, кнопку Action модуля в ReSukiSU или код `*#*#832867#*#*` в звонилке. В настройках области (Scope) каждого Xposed-модуля отметьте только нужные приложения (лаунчер, плеер и т.п.), а сами APK Xposed-модулей обязательно добавьте в шаблон `root_hide` внутри HMA-OSS.

Важно про обновления: не устанавливайте новые релизы Vector поверх пропатченной версии, пока разработчики `JingMatrix/Vector` не добавят поддержку `libcore_bundle.so` в исходный код. Перед обновлением всегда проверяйте новый ZIP через `--dry-run`.

### Финальная проверка

После перезагрузки выполните команды проверки:

```sh
adb shell "su -c '/data/adb/modules/zygisksu/bin/zygiskd status'"
adb shell "su -c '/data/adb/ksud module list'"
adb shell "su -c '/data/adb/ksud feature list'"
adb shell "su -c 'cat /data/adb/tricky_store/tee_status'"
adb shell "su -c '/data/adb/modules/zygisk_vector/cli status'"
```

На что смотреть в выводе:

- `zygiskd status` показывает `inject_state:1`, `modules_with_issue:0` и `enforce_denylist:0`.
- В описании модуля `Nohello` растет счетчик размонтирований.
- В описании `HMA-OSS Zygisk` указано `[System service loaded]`, а в `/data/misc/hide_my_applist_bwpjugplvntusdea/filter_count.json` видны отфильтрованные запросы для Google Play, GMS и банков.
- `tee_status` содержит `teeBroken=false`.
- `vector-cli status` выводит версию `2.2` (`3119`), а в `/data/adb/lspd/log/verbose_*.log` есть строка `Successfully injected Vector IPC binder for applications.` без перезапусков `system_server`.
