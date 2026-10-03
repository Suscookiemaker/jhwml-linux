#!/usr/bin/env python3
"""JHWML - Linux Installer (Fixed)

Installs the JHWML mod loader into the Linux Happy Wheels 1.99.2 installation.
Uses in-place ASAR patching to preserve unpacked node_modules and Steam APIs.

Usage:
  python3 linux_install.py                    # Auto-detect game folder
  python3 linux_install.py /path/to/game     # Patch specific folder
  python3 linux_install.py --help             # Show options
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import struct
import sys
import tempfile
import textwrap

ROOT = pathlib.Path(__file__).resolve().parents[1]
CORE_DIR = ROOT / "core"
VERSION = "0.2.2"


def looks_like_game(path: pathlib.Path) -> bool:
    """Check if the path looks like a Linux Happy Wheels installation."""
    if not path or not path.exists():
        return False
    # Linux native port has start.bash and a game/ subdirectory.
    root_ok = (path / "start.bash").is_file() and (path / "game").is_dir()
    # app.asar is in resources/ (could be at root or under game/).
    resources_ok = (
        (path / "resources" / "app.asar").is_file()
        or (path / "game" / "resources" / "app.asar").is_file()
    )
    return root_ok and resources_ok


def find_game_root() -> pathlib.Path | None:
    """Locate the Linux Happy Wheels Steam folder."""
    home = pathlib.Path.home()
    
    # Standard Steam paths on Linux.
    steam_roots = [
        home / ".steam" / "steam" / "steamapps" / "common",
        home / ".local" / "share" / "Steam" / "steamapps" / "common",
        home / "snap" / "steam" / "common" / ".steam" / "steam" / "steamapps" / "common",
        pathlib.Path("/mnt/games/Steam/steamapps/common"),
        pathlib.Path("/var/lib/steam/steamapps/common"),
        pathlib.Path("/opt/steam/steamapps/common"),
    ]
    
    seen: set[str] = set()
    for root in steam_roots:
        if root.exists():
            # Look for folders named exactly "Happy Wheels".
            for candidate in sorted(root.glob("Happy Wheels")):
                key = str(candidate.resolve())
                if key not in seen and looks_like_game(candidate):
                    seen.add(key)
                    return candidate
            # Also try partial matches.
            for candidate in sorted(root.glob("*Happy*Wheels*")):
                key = str(candidate.resolve())
                if key not in seen and looks_like_game(candidate):
                    seen.add(key)
                    return candidate
    return None


def resolve_app_asar(game_root: pathlib.Path) -> pathlib.Path:
    """Find the app.asar path within the game folder."""
    candidates = (
        game_root / "resources" / "app.asar",
        game_root / "game" / "resources" / "app.asar",
        game_root / "game" / "app.asar",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"Could not find app.asar under {game_root}")


def unpack_asar(blob: bytes) -> dict[str, bytes]:
    """Unpack an Electron ASAR archive (packed files only)."""
    size = struct.unpack_from("<I", blob, 4)[0]
    length = struct.unpack_from("<I", blob, 12)[0]
    header = json.loads(blob[16 : 16 + length])
    result: dict[str, bytes] = {}

    def walk(files, prefix=""):
        for name, item in files.items():
            path = prefix + name
            if "files" in item:
                walk(item["files"], path + "/")
            elif not item.get("unpacked"):
                start = 8 + size + int(item["offset"])
                result[path] = blob[start : start + item["size"]]

    walk(header["files"])
    return result


def pack_asar(files: dict[str, bytes]) -> bytes:
    """Repack files into an Electron ASAR archive."""
    import hashlib
    
    tree = {"files": {}}
    body = bytearray()
    for name, content in sorted(files.items()):
        directory = tree["files"]
        parts = name.split("/")
        for part in parts[:-1]:
            directory = directory.setdefault(part, {"files": {}})[ "files"]
        block = 4194304
        directory[parts[-1]] = {
            "size": len(content),
            "offset": str(len(body)),
            "integrity": {
                "algorithm": "SHA256",
                "hash": hashlib.sha256(content).hexdigest(),
                "blockSize": block,
                "blocks": [
                    hashlib.sha256(content[i : i + block]).hexdigest()
                    for i in range(0, len(content), block)
                ],
            },
        }
        body.extend(content)
    header = json.dumps(tree, separators=(",", ":")).encode()
    padding = (-len(header)) % 4
    pickle = struct.pack("<II", 4 + len(header) + padding, len(header)) + header + b"\0" * padding
    return struct.pack("<II", 4, len(pickle)) + pickle + bytes(body)


def patch_asar_inplace(app_asar: pathlib.Path) -> None:
    """Patch app.asar in-place by replacing packed JS files.
    
    This preserves unpacked node_modules and ASAR structure integrity.
    """
    print(f"  Loading {app_asar.name}...")
    payload = app_asar.read_bytes()
    files = unpack_asar(payload)
    
    if "electron/out/main.js" not in files:
        raise ValueError(
            f"{app_asar} does not look like a Happy Wheels app.asar.\n"
            "Please verify the game folder is the Linux Happy Wheels installation."
        )
    
    main_path = "electron/out/main.js"
    preload_path = "electron/out/preload.js"
    
    print(f"  Patching {main_path}...")
    main = files[main_path].decode("utf-8", errors="replace")
    preload = files[preload_path].decode("utf-8", errors="replace")
    
    # Inject the mod loader require into main.js if not present.
    if 'require("./hw-mod-loader.js")' not in main and "require('./hw-mod-loader.js')" not in main:
        main = main + '\nrequire("./hw-mod-loader.js");\n'
    
    # Inject boot script reference.
    if '<script src="./js/hw-mod-boot.js">' not in main:
        before = '<script src="./js/dependencies.js">'
        if before in main:
            main = main.replace(before, '<script src="./js/hw-mod-boot.js"><\\/script>' + before)
    
    # Inject mod-runtime preload into preload.js if not present.
    if "mod-runtime/preload.cjs" not in preload:
        preload = (
            "(() => {\n"
            "  try {\n"
            "    require(require('path').join(process.resourcesPath, 'mod-runtime', 'preload.cjs'));\n"
            "  } catch (e) {}\n"
            "})();\n" + preload
        )
    
    files[main_path] = main.encode("utf-8")
    files[preload_path] = preload.encode("utf-8")
    
    # Add the loader and SDK files.
    print(f"  Adding mod loader and SDK...")
    loader_file = CORE_DIR / "mod-loader-main.cjs"
    sdk_file = CORE_DIR / "hw-mod-sdk.js"
    
    if not loader_file.exists():
        raise FileNotFoundError(f"Missing {loader_file}. Is the repo complete?")
    if not sdk_file.exists():
        raise FileNotFoundError(f"Missing {sdk_file}. Is the repo complete?")
    
    files["electron/out/hw-mod-loader.js"] = loader_file.read_bytes()
    files["electron/out/hw-mod-sdk.js"] = sdk_file.read_bytes()
    files["electron/out/hw-mod-boot.js"] = b"window.HW_MOD_CATALOG=[];\n"
    
    # Add minimal runtime files.
    files["mod-runtime/preload.cjs"] = b"void 0;\n"
    files["mod-runtime/mods.json"] = b"[]\n"
    
    print(f"  Repacking ASAR (preserving unpacked modules)...")
    patched = pack_asar(files)
    app_asar.write_bytes(patched)
    print(f"  ✓ Patched.")


def install_linux(game_root: pathlib.Path | None = None, force: bool = False) -> pathlib.Path:
    """Main Linux installation workflow."""
    if game_root is None:
        print("Searching for Happy Wheels...")
        game_root = find_game_root()
    
    if game_root is None:
        raise FileNotFoundError(
            "Could not locate the Happy Wheels Linux installation.\n\n"
            "Expected to find it in one of:\n"
            "  ~/.steam/steam/steamapps/common/Happy Wheels\n"
            "  ~/.local/share/Steam/steamapps/common/Happy Wheels\n\n"
            "Alternatively, pass the path as an argument:\n"
            f"  python3 {pathlib.Path(__file__).name} /path/to/Happy/Wheels"
        )
    
    print(f"Found Happy Wheels at: {game_root}")
    
    if not looks_like_game(game_root):
        raise ValueError(
            f"{game_root} does not look like the Linux Happy Wheels install.\n"
            "Expected to find start.bash and a game/ subdirectory."
        )
    
    app_asar = resolve_app_asar(game_root)
    backup = app_asar.with_suffix(app_asar.suffix + ".backup")
    
    if backup.exists() and not force:
        print(
            f"\n⚠ Backup already exists: {backup.relative_to(game_root)}\n"
            f"  (App is already patched or install failed previously.)\n"
            f"\nOptions:\n"
            f"  1. Use --force to overwrite the backup and reinstall.\n"
            f"  2. Restore from backup: cp {backup} {app_asar}\n"
            f"  3. Run Steam 'Verify Integrity' and retry.\n"
        )
        return game_root
    
    print(f"\nBacking up app.asar...")
    shutil.copy2(app_asar, backup)
    print(f"  ✓ Saved to: {backup.relative_to(game_root)}")
    
    print(f"\nPatching app.asar...")
    patch_asar_inplace(app_asar)
    
    print(f"\nSetting up mods directory...")
    mods_dir = game_root / "mods"
    mods_dir.mkdir(parents=True, exist_ok=True)
    (mods_dir / "README.txt").write_text(
        "Drop a mod folder here.\n"
        "Each mod needs a mod.json file.\n"
        "Restart Happy Wheels to load new mods.\n\n"
        "Docs: https://mathewregier.github.io/jhwml/\n",
        encoding="utf-8",
    )
    print(f"  ✓ Mods folder ready at: {mods_dir.relative_to(game_root)}")
    
    print(f"\nSetting up mod runtime...")
    runtime_dir = game_root / "resources" / "mod-runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    (runtime_dir / "preload.cjs").write_text("void 0;\n", encoding="utf-8")
    (runtime_dir / "mods.json").write_text("[]\n", encoding="utf-8")
    print(f"  ✓ Runtime files installed.")
    
    return game_root


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="JHWML Linux Installer",
        description="Install the JHWML mod loader into Linux Happy Wheels 1.99.2",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
            Examples:
              %(prog)s
                Auto-detect the game folder and install.
              %(prog)s /home/user/.steam/steam/steamapps/common/Happy\ Wheels
                Patch a specific installation.
              %(prog)s --force
                Reinstall, overwriting any existing backup.
        """),
    )
    parser.add_argument(
        "path",
        nargs="?",
        type=pathlib.Path,
        help="Path to the Happy Wheels installation (auto-detected if omitted)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing backup and reinstall",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {VERSION}",
    )
    
    args = parser.parse_args()
    
    try:
        game_root = args.path.resolve() if args.path else find_game_root()
        installed = install_linux(game_root, force=args.force)
        
        print(f"\n" + "=" * 60)
        print(f"Installation complete!")
        print(f"\nGame folder: {installed}")
        print(f"Mods folder: {installed / 'mods'}")
        print(f"\nNext steps:")
        print(f"  1. Launch Happy Wheels from Steam (or run start.bash)")
        print(f"  2. Drop a mod folder into the 'mods' directory")
        print(f"  3. Restart the game to load it")
        print(f"\nHelp: https://mathewregier.github.io/jhwml/")
        print(f"Discord: https://discord.gg/XcZePBgDBJ")
        print(f"=" * 60)
        return 0
    
    except KeyboardInterrupt:
        print(f"\n✗ Cancelled by user.")
        return 130
    except Exception as exc:
        print(f"\n✗ Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
