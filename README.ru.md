# Скрытие root, Play Integrity и работа Vector (Xposed) на Pixel 9 (Android 17 Canary)

[Главная страница (EN + RU)](README.md)

В этом руководстве собрана проверенная конфигурация для скрытия root, прохождения аттестации и стабильной работы Xposed-фреймворка Vector на Google Pixel 9 (`tokay`) с Android 17 Canary (`ZP11.261016.008`, API 37, патч безопасности `2026-11-05`) и ReSukiSU `v4.2.0-rc3`.

Задача состоит из двух частей: сделать так, чтобы банковские приложения и Mir Pay запускались без жалоб на root, и запустить Vector на Android 17 Canary без циклического падения `system_server`.

## Важное предупреждение и безопасность

Разблокировка загрузчика, модификация загрузочных образов, установка root-модулей и использование Canary-сборок ОС всегда несут риск потери данных или циклической перезагрузки. Перед началом работы обязательно сделайте резервную копию важных данных.

Никогда не выкладывайте в сеть свой файл `/data/adb/tricky_store/keybox.xml`. В этом репозитории нет чужих ключей, скомпилированных бинарных файлов сторонних модулей и личных данных. Проверки антифрода в банках постоянно обновляются, а успешный запуск приложения еще не гарантирует привязку конкретной карты и прохождение NFC-оплаты на терминале, поэтому проверяйте оплату вручную на своем устройстве.

## Проверенное окружение

- Устройство: Google Pixel 9 (`tokay`)
- Система: Android 17 Canary (`ZP11.261016.008`, `SDK 37`)
- Root-менеджер: ReSukiSU `v4.2.0-rc3` (`ksud 35171`)
- Реализация Zygisk: Zygisk Next `1.5.3` (`880`, `linker: builtin`, `enforce_denylist: disabled`)
- Скрытие root и списка приложений: Nohello `v0.0.7` (`53`) и HMA-OSS Zygisk `oss-177`
- Keystore и Play Integrity: Tricky Store OSS `v3.1.0` (`172`) и Play Integrity Fork `v19`
- Xposed-фреймворк (по желанию): Vector `v2.2 canary-3119` с патчем для `libcore_bundle.so` из `scripts/patch_vector_a17.py`

## Какие модули не подходят для Android 17 (SDK 37)

Привычные связки с Android 15 и 16 на Android 17 Canary вызывают сбои или не проходят проверки.

| Модуль | Проблема на Android 17 Canary | Что ставить взамен |
| :--- | :--- | :--- |
| NeoZygisk `v2.4` | Ошибки `solist` и нестабильность `system_server` | [Zygisk Next](https://github.com/Dr-TSNG/ZygiskNext) `1.5.3+` |
| Закрытый Tricky Store `v1.4.1` | На SDK 37 некорректно перехватывает EC-аттестацию ключей | [Tricky Store OSS](https://github.com/beakthoven/TrickyStoreOSS) `v3.1.0+` |
| Integrity Box | Лишние фоновые скрипты в `/data/adb/service.d` и `Box-Brain` | [Play Integrity Fork](https://github.com/osm0sis/PlayIntegrityFork) `v19+` |
| Pay Security Bypass `v1.0.4` | Крашится внутри Mir Pay с `AssertionError` (`AndroidVMTools` поддерживает максимум SDK 36) | Удалить или отключить; нативное скрытие работает без него |
| Vector `v2.2 (3080)` | Вызывает цикл перезапусков `system_server` на Android 17 Canary | [Vector](https://github.com/JingMatrix/Vector) `canary-3119+` с патчем под `libcore_bundle.so` |

## Шаг 1. Сделайте резервную копию

Перед удалением или заменой модулей сохраните текущие конфигурации на устройстве через ADB:

```sh
adb shell "su -c 'mkdir -p /data/adb/backup && cp -a /data/adb/modules /data/adb/tricky_store /data/adb/lspd /data/adb/backup/'"
```

Запомните способ аварийного отката в KernelSU / ReSukiSU: если во время загрузки удерживать клавишу уменьшения громкости, система загрузится в безопасном режиме с отключенными модулями. Если ADB уже доступен, отдельный модуль можно отключить командой `/data/adb/ksud module disable <id_модуля>`.

## Шаг 2. Настройте функции ядра в ReSukiSU

Модуль Nohello сам размонтирует следы модулей внутри процессов, поэтому встроенное ядерное размонтирование `kernel_umount` нужно отключить во избежание конфликтов, а `selinux_hide` оставить включенным:

```sh
adb shell "su -c '/data/adb/ksud feature set kernel_umount 0 && /data/adb/ksud feature set selinux_hide 1 && /data/adb/ksud feature save'"
```

Проверьте результат командой `/data/adb/ksud feature list`. Включенными остаются `su_compat`, `selinux_hide`, `sulog` и `adb_root`, а напротив `kernel_umount` должно быть `[DISABLED]`.

## Шаг 3. Установите базовые модули скрытия и аттестации

Скачайте официальные ZIP-архивы со страниц разработчиков на GitHub и установите их через ReSukiSU. Перезагружать телефон после каждого модуля не нужно, достаточно одной перезагрузки в конце списка:

1. [Zygisk Next](https://github.com/Dr-TSNG/ZygiskNext) (`1.5.3` или новее). В WebUI модуля `Enforce DenyList` должен быть выключен, иначе перестанут работать модули вроде Vector и HMA-OSS.
2. [Nohello](https://github.com/MhmRdd/NoHello) (`v0.0.7` или новее). В паре с Zygisk Next `>= 521` модуль автоматически создает нужные флаги `/data/adb/nohello/no_clr_ptracemsg` и `/data/adb/nohello/no_dirtyro_ar`.
3. [HMA-OSS](https://github.com/frknkrc44/HMA-OSS) (`oss-177` или новее): установите модуль `HMA-OSS-ZYGISK-*.zip` и отдельно приложение-менеджер (APK).
4. [Tricky Store OSS](https://github.com/beakthoven/TrickyStoreOSS) (`v3.1.0` или новее, с поддержкой SDK 37).
5. [Play Integrity Fork](https://github.com/osm0sis/PlayIntegrityFork) (`v19` или новее).

После установки всех пяти модулей перезагрузите смартфон.

## Шаг 4. Настройте Play Integrity и Tricky Store OSS

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

## Шаг 5. Настройте HMA-OSS

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

## Шаг 6. Сбросьте кэш ошибки в Mir Pay и проверьте банки

Если Mir Pay уже запускался до настройки скрытия, он сохраняет ошибку `0111000003` в локальных данных `/data/data/ru.nspk.mirpay` и продолжает показывать её даже после починки модулей.

После настройки всех шагов выше очистите данные Mir Pay (при необходимости предварительно скопировав старую папку):

```sh
adb shell "su -c 'pm clear ru.nspk.mirpay'"
```

Откройте Mir Pay, выдайте запрошенное разрешение на геолокацию и проверьте переход на главный экран добавления карты без ошибки `0111000003`. Модуль `Pay Security Bypass v1.0.4` на Android 17 включать не нужно. После этого запустите и проверьте ваши банковские приложения.

## Шаг 7. Установка Vector (Xposed) на Android 17 Canary (по желанию)

### Почему Vector не работает без патча

В прошивке Android 17 Canary (`ZP11.261016.008`) файл `/system/lib64/libbinder.so` стал симлинком на `/system/lib64/libcore_bundle.so`. Модуль `Vector canary-3119` запрашивает загруженные библиотеки у линкера через `dl_iterate_phdr`, получает реальные пути (`libcore_bundle.so`), не находит строку `"libbinder.so"` и выдает ошибку `Could not find any mappings for libbinder.so`. В результате функция `BinderCaller::GetId()` всегда возвращает `0`, и хук `IPCBridge` в `system_server` отклоняет все подключения от `VectorDaemon` с ошибкой `Vector reached system_server but its bridge never answered`.

### Проверка, нужен ли патч именно вашей прошивке

Выполните на телефоне команду:

```sh
adb shell "readlink -f /system/lib64/libbinder.so"
```

- Если вернулось `/system/lib64/libbinder.so`, можно сразу ставить обычный [Vector](https://github.com/JingMatrix/Vector) `canary-3119`.
- Если вернулось `/system/lib64/libcore_bundle.so`, архив перед установкой нужно пропатчить.

### Патчинг и установка Vector

Скачайте официальный `Vector-v2.2-3119-Release.zip` со страницы [JingMatrix/Vector Releases](https://github.com/JingMatrix/Vector/releases), запустите скрипт на ПК и установите полученный архив:

```sh
python scripts/patch_vector_a17.py Vector-v2.2-3119-Release.zip -o Vector-v2.2-3119-a17-patched.zip
```

При желании сначала запустите скрипт с флагом `--dry-run`, чтобы проверить найденное смещение и хэши без создания файла. Скрипт меняет ровно 12 байт имени библиотеки (`"libbinder.so"` на `"re_bundle.so"`) в `lib/arm64-v8a/libzygisk.so` и обновляет `lib/arm64-v8a/libzygisk.so.sha256` внутри ZIP, чтобы установщик `customize.sh` прошел проверку контрольной суммы.

Установите `Vector-v2.2-3119-a17-patched.zip` в ReSukiSU и перезагрузите смартфон. Интерфейс Vector открывается через системное уведомление, кнопку Action модуля в ReSukiSU или код `*#*#832867#*#*` в звонилке. В настройках области (Scope) каждого Xposed-модуля отметьте только нужные приложения (лаунчер, плеер и т.п.), а сами APK Xposed-модулей обязательно добавьте в шаблон `root_hide` внутри HMA-OSS.

Важно про обновления: не устанавливайте новые релизы Vector поверх пропатченной версии, пока разработчики `JingMatrix/Vector` не добавят поддержку `libcore_bundle.so` в исходный код. Перед обновлением всегда проверяйте новый ZIP через `--dry-run`.

## Финальная проверка

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
