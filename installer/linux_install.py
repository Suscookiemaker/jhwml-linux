#!/usr/bin/env python3
"""JHWML - Linux Installer (Fixed)

Installs the JHWML mod loader into the Linux Happy Wheels 1.99.2 installation.
Uses the ASAR extraction/packing flow so unpacked node_modules and Steam runtime
binaries are preserved correctly.

Usage:
  python3 linux_install.py                    # Auto-detect game folder
  python3 linux_install.py /path/to/game     # Patch specific folder
  python3 linux_install.py --help             # Show options
"""
from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import textwrap

ROOT = pathlib.Path(__file__).resolve().parents[1]
CORE_DIR = ROOT / "core"
VERSION = "0.2.2"


def ensure_asar_cli() -> None:
    """Require the `asar` CLI, which preserves unpacked native modules."""
    if shutil.which("asar") is None:
        raise RuntimeError(
            "The `asar` CLI is required to patch the Linux ASAR safely.\n"
            "Install it with: npm install -g asar"
        )


def looks_like_game(path: pathlib.Path) -> bool:
    """Check if the path looks like a Linux Happy Wheels installation."""
    if not path or not path.exists():
        return False
    root_ok = (path / "start.bash").is_file() and (path / "game").is_dir()
    resources_ok = (
        (path / "resources" / "app.asar").is_file()
        or (path / "game" / "resources" / "app.asar").is_file()
    )
    return root_ok and resources_ok


def find_game_root() -> pathlib.Path | None:
    """Locate the Linux Happy Wheels Steam folder."""
    home = pathlib.Path.home()
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
            for candidate in sorted(root.glob("Happy Wheels")):
                key = str(candidate.resolve())
                if key not in seen and looks_like_game(candidate):
                    seen.add(key)
                    return candidate
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


def extract_asar(app_asar: pathlib.Path, out_dir: pathlib.Path) -> None:
    subprocess.run(["asar", "extract", str(app_asar), str(out_dir)], check=True)


def pack_asar(src_dir: pathlib.Path, output_path: pathlib.Path) -> None:
    subprocess.run(["asar", "pack", str(src_dir), str(output_path)], check=True)


def patch_asar_inplace(app_asar: pathlib.Path) -> None:
    """Patch app.asar while preserving unpacked node_modules and native libraries."""
    ensure_asar_cli()

    print(f"  Loading {app_asar.name}...")
    with tempfile.TemporaryDirectory(prefix="jhwml-asar-") as temp_dir:
        temp_root = pathlib.Path(temp_dir)
        unpack_dir = temp_root / "app"
        extract_asar(app_asar, unpack_dir)

        main_js = unpack_dir / "electron" / "out" / "main.js"
        preload_js = unpack_dir / "electron" / "out" / "preload.js"
        if not main_js.is_file() or not preload_js.is_file():
            raise ValueError(
                f"{app_asar} does not look like a Happy Wheels app.asar.\n"
                "Please verify the game folder is the Linux Happy Wheels installation."
            )

        main = main_js.read_text(encoding="utf-8", errors="replace")
        preload = preload_js.read_text(encoding="utf-8", errors="replace")

        if 'require("./hw-mod-loader.js")' not in main and "require('./hw-mod-loader.js')" not in main:
            main = main + '\nrequire("./hw-mod-loader.js");\n'

        if '<script src="./js/hw-mod-boot.js">' not in main:
            before = '<script src="./js/dependencies.js">'
            if before in main:
                main = main.replace(before, '<script src="./js/hw-mod-boot.js"><\\/script>' + before)

        if "mod-runtime/preload.cjs" not in preload:
            preload = (
                "(() => {\n"
                "  try {\n"
                "    require(require('path').join(process.resourcesPath, 'mod-runtime', 'preload.cjs'));\n"
                "  } catch (e) {}\n"
                "})();\n" + preload
            )

        main_js.write_text(main, encoding="utf-8")
        preload_js.write_text(preload, encoding="utf-8")

        loader_file = CORE_DIR / "mod-loader-main.cjs"
        sdk_file = CORE_DIR / "hw-mod-sdk.js"
        if not loader_file.exists():
            raise FileNotFoundError(f"Missing {loader_file}. Is the repo complete?")
        if not sdk_file.exists():
            raise FileNotFoundError(f"Missing {sdk_file}. Is the repo complete?")

        (unpack_dir / "electron" / "out" / "hw-mod-loader.js").write_bytes(loader_file.read_bytes())
        (unpack_dir / "electron" / "out" / "hw-mod-sdk.js").write_bytes(sdk_file.read_bytes())
        (unpack_dir / "electron" / "out" / "hw-mod-boot.js").write_bytes(b"window.HW_MOD_CATALOG=[];\n")

        runtime_dir = unpack_dir / "mod-runtime"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        (runtime_dir / "preload.cjs").write_bytes(b"void 0;\n")
        (runtime_dir / "mods.json").write_bytes(b"[]\n")

        # Use the Node ASAR packer so unpacked native modules remain untouched.
        repacked = temp_root / "patched.asar"
        pack_asar(unpack_dir, repacked)

        # Move the patched archive over the original.
        temp_backup = app_asar.with_suffix(app_asar.suffix + ".tmp")
        shutil.copy2(str(repacked), str(temp_backup))
        temp_backup.replace(app_asar)


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
    parser.add_argument("path", nargs="?", type=pathlib.Path, help="Path to the Happy Wheels installation")
    parser.add_argument("--force", action="store_true", help="Overwrite existing backup and reinstall")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")

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
