#!/usr/bin/env python3
"""
Патчер архивов Vector (LSPosed fork) для сборок Android 17 Canary,
где /system/lib64/libbinder.so является симлинком на /system/lib64/libcore_bundle.so.

Скрипт находит единственную standalone-строку "libbinder.so" (12 байт) строго внутри
секции .rodata библиотеки libzygisk.so, заменяет её на "re_bundle.so" (ровно 12 байт)
и обновляет соответствующий файл .sha256 внутри архива, чтобы customize.sh
успешно прошёл проверку целостности при установке через KernelSU/ReSukiSU/Magisk.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import struct
import sys
import tempfile
import zipfile
from pathlib import Path

OLD_BYTES = b"\x00libbinder.so\x00"
UPSTREAM_FIX_MARKER = b"\x00libcore_bundle.so\x00"
# "re_bundle.so" имеет длину ровно 12 байт (как и "libbinder.so") и уникально
# совпадает только с /system/lib64/libcore_bundle.so среди бандлов Android 17.
DEFAULT_TARGET_SUBSTR = "re_bundle.so"
SUPPORTED_ABIS = ("arm64-v8a", "armeabi-v7a", "x86", "x86_64")


def find_section_bounds(elf_data: bytes, section_name: bytes) -> tuple[int, int] | None:
    """Возвращает (offset, offset + size) указанной ELF-секции или None."""
    data_len = len(elf_data)
    if data_len < 64 or elf_data[:4] != b"\x7fELF":
        return None

    ei_class = elf_data[4]
    ei_data = elf_data[5]
    if ei_data != 1:
        # Поддерживается только little-endian ELF (arm64-v8a / armeabi-v7a / x86 / x86_64).
        return None

    if ei_class == 2:
        # ELF64
        e_shoff = struct.unpack_from("<Q", elf_data, 40)[0]
        e_shentsize, e_shnum, e_shstrndx = struct.unpack_from("<HHH", elf_data, 58)
        sh_fmt = "<IIQQQQ"
        sh_min_size = 40
    elif ei_class == 1:
        # ELF32
        e_shoff = struct.unpack_from("<I", elf_data, 32)[0]
        e_shentsize, e_shnum, e_shstrndx = struct.unpack_from("<HHH", elf_data, 46)
        sh_fmt = "<IIIIII"
        sh_min_size = 24
    else:
        return None

    if e_shoff == 0 or e_shnum == 0 or e_shentsize < sh_min_size or e_shstrndx >= e_shnum:
        return None

    str_hdr_off = e_shoff + e_shstrndx * e_shentsize
    if str_hdr_off + e_shentsize > data_len:
        return None
    str_sec_off, str_sec_size = struct.unpack_from(sh_fmt, elf_data, str_hdr_off)[4:6]
    if str_sec_off + str_sec_size > data_len:
        return None

    for i in range(e_shnum):
        sec_off = e_shoff + i * e_shentsize
        if sec_off + e_shentsize > data_len:
            break
        sh_name, _sh_type, _sh_flags, _sh_addr, sh_offset, sh_size = struct.unpack_from(
            sh_fmt, elf_data, sec_off
        )
        name_start = str_sec_off + sh_name
        if name_start >= str_sec_off + str_sec_size:
            continue
        name_end = elf_data.find(b"\x00", name_start, str_sec_off + str_sec_size)
        if name_end > name_start and elf_data[name_start:name_end] == section_name:
            if sh_offset + sh_size > data_len:
                return None
            return (sh_offset, sh_offset + sh_size)

    return None


def patch_elf_bytes(elf_data: bytes, target_substr: str) -> tuple[bytes, int, str]:
    """
    Проверяет и патчит libzygisk.so строго в секции .rodata.
    Возвращает кортеж (новые_байты, смещение_строки, sha256).
    """
    try:
        target_bytes = target_substr.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ValueError("Target library substring must be plain ASCII.") from exc

    if len(target_bytes) != 12:
        raise ValueError("Target library substring must be exactly 12 ASCII bytes.")

    if elf_data[:4] != b"\x7fELF":
        raise ValueError("Input file is not a valid ELF binary.")

    rodata = find_section_bounds(elf_data, b".rodata")
    if rodata is None:
        raise ValueError(
            "ELF .rodata section was not found; refusing unsafe full-file scan."
        )
    search_start, search_end = rodata

    dynstr = find_section_bounds(elf_data, b".dynstr")
    dynstr_before = elf_data[dynstr[0] : dynstr[1]] if dynstr else None

    replacement = b"\x00" + target_bytes + b"\x00"

    matches: list[int] = []
    pos = search_start
    while True:
        idx = elf_data.find(OLD_BYTES, pos, search_end)
        if idx < 0:
            break
        matches.append(idx)
        pos = idx + 1

    if len(matches) == 0:
        already = elf_data.find(replacement, search_start, search_end)
        if already >= 0:
            raise ValueError(
                f"Binary is already patched ({target_substr!r} found at {hex(already + 1)})."
            )
        upstream = elf_data.find(UPSTREAM_FIX_MARKER, search_start, search_end)
        if upstream >= 0:
            raise ValueError(
                "Binary already references 'libcore_bundle.so' in .rodata; "
                "this release does not need patching."
            )
        raise ValueError("Standalone 'libbinder.so' string was not found in .rodata.")

    if len(matches) > 1:
        hex_list = ", ".join(hex(m + 1) for m in matches)
        raise ValueError(
            f"Found {len(matches)} standalone 'libbinder.so' strings in .rodata ({hex_list}); "
            "refusing to patch without manual inspection."
        )

    str_offset = matches[0] + 1
    patched = bytearray(elf_data)
    patched[matches[0] : matches[0] + len(OLD_BYTES)] = replacement
    new_bytes = bytes(patched)

    if dynstr is not None and new_bytes[dynstr[0] : dynstr[1]] != dynstr_before:
        raise RuntimeError("Internal safety check failed: .dynstr section changed.")

    digest = hashlib.sha256(new_bytes).hexdigest()
    return new_bytes, str_offset, digest


def patch_zip(
    input_zip: Path,
    output_zip: Path,
    abis: list[str],
    target_substr: str,
    dry_run: bool,
) -> None:
    """Читает архив модуля Vector, патчит указанные ABI и обновляет файлы .sha256."""
    if not input_zip.is_file():
        raise FileNotFoundError(f"Input archive not found: {input_zip}")

    output_zip.parent.mkdir(parents=True, exist_ok=True)
    tmp_path: Path | None = None

    with zipfile.ZipFile(input_zip, "r") as zin:
        entries = zin.infolist()
        name_set = {info.filename for info in entries}

        replacements: dict[str, bytes] = {}
        for abi in abis:
            so_path = f"lib/{abi}/libzygisk.so"
            sha_path = f"lib/{abi}/libzygisk.so.sha256"
            if so_path not in name_set:
                print(f"[skip] {so_path} is absent from archive")
                continue

            orig_data = zin.read(so_path)
            orig_sha = hashlib.sha256(orig_data).hexdigest()
            new_data, offset, new_sha = patch_elf_bytes(orig_data, target_substr)

            print(
                f"[ok]   {so_path}: patched .rodata at {hex(offset)} "
                f"('libbinder.so' -> '{target_substr}')"
            )
            print(f"       orig sha256:    {orig_sha}")
            print(f"       patched sha256: {new_sha}")

            replacements[so_path] = new_data
            if sha_path in name_set:
                replacements[sha_path] = f"{new_sha}\n".encode("ascii")

        if not replacements:
            raise RuntimeError("No target libzygisk.so entries were patched.")

        if dry_run:
            print("[dry-run] No output file written.")
            return

        with tempfile.NamedTemporaryFile(
            delete=False, dir=str(output_zip.parent), suffix=".tmp.zip"
        ) as tmp_file:
            tmp_path = Path(tmp_file.name)

        try:
            with zipfile.ZipFile(tmp_path, "w") as zout:
                for info in entries:
                    new_info = zipfile.ZipInfo(
                        filename=info.filename, date_time=info.date_time
                    )
                    new_info.compress_type = info.compress_type
                    new_info.external_attr = info.external_attr
                    new_info.create_system = info.create_system
                    payload = replacements.get(info.filename, zin.read(info.filename))
                    zout.writestr(new_info, payload)
        except Exception:
            if tmp_path is not None and tmp_path.exists():
                tmp_path.unlink()
            raise

    # Перемещение выполняется после закрытия zin, чтобы на Windows работал и перезаписывающий -o.
    try:
        shutil.move(str(tmp_path), str(output_zip))
    except Exception:
        if tmp_path is not None and tmp_path.exists():
            tmp_path.unlink()
        raise

    print(f"[done] Wrote patched module zip: {output_zip}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Patch Vector Zygisk module zip for Android 17 Canary libcore_bundle.so symlink."
    )
    parser.add_argument("input_zip", type=Path, help="Path to Vector-v2.2-*-Release.zip")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output patched zip path (default: <stem>-a17-patched.zip)",
    )
    parser.add_argument(
        "--abi",
        nargs="+",
        default=["arm64-v8a"],
        choices=list(SUPPORTED_ABIS),
        help="ABI libraries to patch inside the zip (default: arm64-v8a)",
    )
    parser.add_argument(
        "--target",
        default=DEFAULT_TARGET_SUBSTR,
        help="12-byte ASCII replacement substring (default: re_bundle.so)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Check offsets and SHA-256 digests without writing output file",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_zip = args.output
    if output_zip is None:
        output_zip = args.input_zip.with_name(f"{args.input_zip.stem}-a17-patched.zip")

    try:
        patch_zip(
            input_zip=args.input_zip,
            output_zip=output_zip,
            abis=args.abi,
            target_substr=args.target,
            dry_run=args.dry_run,
        )
    except Exception as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
