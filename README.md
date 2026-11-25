# Root hiding, Play Integrity, and Vector Xposed on Pixel 9 (Android 17 Canary)

[Русская версия](README.ru.md)

This repository documents a working root-hiding and Xposed setup tested on a Google Pixel 9 (`tokay`) running Android 17 Canary (`ZP11.261016.008`, API 37, security patch `2026-11-05`) with ReSukiSU `v4.2.0-rc3`.

It covers two goals: keeping payment and banking apps working without root alerts, and running the Vector Xposed framework on Android 17 Canary without causing `system_server` crash loops.

## Disclaimer and privacy notes

Modifying boot images, unlocking the bootloader, and flashing Canary builds carry a risk of data loss or bootloops. Back up your data before making changes.

Do not share your personal `/data/adb/tricky_store/keybox.xml` file. This repository contains zero keyboxes, zero third-party binaries, and zero personal app data. Banking apps update their detection regularly, and running an app without a launch error does not guarantee card tokenization or NFC terminal payments on every setup, so verify payments manually on your own device.

## Tested environment

- Device: Google Pixel 9 (`tokay`)
- OS: Android 17 Canary (`ZP11.261016.008`, `SDK 37`)
- Root manager: ReSukiSU `v4.2.0-rc3` (`ksud 35171`)
- Zygisk implementation: Zygisk Next `1.5.3` (`880`, `linker: builtin`, `enforce_denylist: disabled`)
- Root hiding: Nohello `v0.0.7` (`53`) and HMA-OSS Zygisk `oss-177`
- Keystore and Play Integrity: Tricky Store OSS `v3.1.0` (`172`) and Play Integrity Fork `v19`
- Xposed framework (optional): Vector `v2.2 canary-3119` with the `libcore_bundle.so` patch in `scripts/patch_vector_a17.py`

## Modules to avoid on Android 17 (SDK 37)

Older stacks that work on Android 15 or 16 cause crashes or fail attestation on Android 17 Canary.

| Module | Issue observed on Android 17 Canary | Replacement |
| :--- | :--- | :--- |
| NeoZygisk `v2.4` | `solist` errors and `system_server` instability | [Zygisk Next](https://github.com/Dr-TSNG/ZygiskNext) `1.5.3+` |
| Closed Tricky Store `v1.4.1` | Fails to intercept EC key attestation cleanly on SDK 37 | [Tricky Store OSS](https://github.com/beakthoven/TrickyStoreOSS) `v3.1.0+` |
| Integrity Box | Extra `/data/adb/service.d` scripts and `Box-Brain` bloat | [Play Integrity Fork](https://github.com/osm0sis/PlayIntegrityFork) `v19+` |
| Pay Security Bypass `v1.0.4` | Crashes inside Mir Pay with `AssertionError` (`AndroidVMTools` max SDK is 36) | Remove or disable; native hiding works without it |
| Vector `v2.2 (3080)` | Crash-loops `system_server` on Android 17 Canary | [Vector](https://github.com/JingMatrix/Vector) `canary-3119+` patched for `libcore_bundle.so` |

## Step 1: Back up your existing setup

Before replacing modules, back up `/data/adb` from an elevated ADB shell on your PC.

```sh
adb shell "su -c 'mkdir -p /data/adb/backup && cp -a /data/adb/modules /data/adb/tricky_store /data/adb/lspd /data/adb/backup/'"
```

Remember the bootloop escape hatch in KernelSU / ReSukiSU: holding Volume Down during boot activates Safe Mode and disables all modules. Over ADB, you can disable a single module with `/data/adb/ksud module disable <module_id>`.

## Step 2: Configure ReSukiSU kernel settings

Nohello handles mount hiding in Zygisk space and conflicts with kernel-level auto-unmount. Disable `kernel_umount` in ReSukiSU settings or over ADB, and keep `selinux_hide` enabled:

```sh
adb shell "su -c '/data/adb/ksud feature set kernel_umount 0 && /data/adb/ksud feature set selinux_hide 1 && /data/adb/ksud feature save'"
```

Verify the saved state with `/data/adb/ksud feature list`. Keep `su_compat`, `selinux_hide`, `sulog`, and `adb_root` enabled, and confirm `kernel_umount` shows `[DISABLED]`.

## Step 3: Install the core hiding and integrity modules

Download the official ZIP releases from the authors' GitHub repositories and install them in ReSukiSU (do not reboot between installs; reboot once after all modules are queued):

1. [Zygisk Next](https://github.com/Dr-TSNG/ZygiskNext) (`1.5.3` or newer). Leave `Enforce DenyList` disabled in Zygisk Next WebUI so Nohello and Zygisk modules run cleanly.
2. [Nohello](https://github.com/MhmRdd/NoHello) (`v0.0.7` or newer). When paired with Zygisk Next `>= 521`, Nohello automatically creates `/data/adb/nohello/no_clr_ptracemsg` and `/data/adb/nohello/no_dirtyro_ar`.
3. [HMA-OSS](https://github.com/frknkrc44/HMA-OSS) (`oss-177` or newer): install the `HMA-OSS-ZYGISK-*.zip` module and also install the companion manager APK.
4. [Tricky Store OSS](https://github.com/beakthoven/TrickyStoreOSS) (`v3.1.0` or newer, built for SDK 37).
5. [Play Integrity Fork](https://github.com/osm0sis/PlayIntegrityFork) (`v19` or newer).

Reboot the phone after queuing these five modules.

## Step 4: Configure Play Integrity and Tricky Store OSS

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

## Step 5: Configure HMA-OSS

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

## Step 6: Fix cached errors in Mir Pay and banking apps

If you previously launched Mir Pay without full hiding, it caches the root failure inside `/data/data/ru.nspk.mirpay` and keeps showing error `0111000003` even after you fix the modules.

Back up the app data if needed, clear it once, and relaunch:

```sh
adb shell "su -c 'pm clear ru.nspk.mirpay'"
```

Launch Mir Pay, grant location permission when prompted, and verify it reaches the "Add card" home screen instead of `0111000003`. Do not enable `Pay Security Bypass v1.0.4` on Android 17. Test your other banking apps as well.

## Step 7: Optional Vector (Xposed) setup on Android 17 Canary

### Why Vector fails on Android 17 Canary

In Android 17 Canary (`ZP11.261016.008`), `/system/lib64/libbinder.so` is a symlink to `/system/lib64/libcore_bundle.so`. Vector `canary-3119` asks the dynamic linker via `dl_iterate_phdr` for `libbinder.so`, gets real paths (`libcore_bundle.so`), fails with `Could not find any mappings for libbinder.so`, sets caller ID to `0`, and rejects all bridge calls from `VectorDaemon` (`Vector reached system_server but its bridge never answered`).

### Check whether your ROM needs the patch

Run this on your device first:

```sh
adb shell "readlink -f /system/lib64/libbinder.so"
```

- If the output is `/system/lib64/libbinder.so`, install stock [Vector](https://github.com/JingMatrix/Vector) `canary-3119` directly.
- If the output is `/system/lib64/libcore_bundle.so`, patch the official release ZIP before flashing.

### Patch and install Vector

Download `Vector-v2.2-3119-Release.zip` from [JingMatrix/Vector Releases](https://github.com/JingMatrix/Vector/releases), run the script on your PC, and install the output ZIP:

```sh
python scripts/patch_vector_a17.py Vector-v2.2-3119-Release.zip -o Vector-v2.2-3119-a17-patched.zip
```

You can also run with `--dry-run` first to inspect the exact offset and SHA-256 checksums without creating a file. The script patches only the 12-byte library lookup string (`"libbinder.so"` to `"re_bundle.so"`) inside `lib/arm64-v8a/libzygisk.so` and updates `lib/arm64-v8a/libzygisk.so.sha256` inside the ZIP so `customize.sh` passes checksum verification.

Install `Vector-v2.2-3119-a17-patched.zip` in ReSukiSU and reboot. Open Vector Manager via the system notification, ReSukiSU module Action button, or dialing `*#*#832867#*#*`, and assign each Xposed module only the apps it needs in Scope. Keep all Xposed module APKs hidden inside your HMA-OSS `root_hide` template.

Note on updates: do not flash newer unpatched Vector ZIPs over your patched build until upstream `JingMatrix/Vector` adds support for `libcore_bundle.so`. Always check a new release with `--dry-run` first.

## Verification commands

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
