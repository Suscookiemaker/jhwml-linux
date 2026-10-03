# JHWML
Linux launcher and mod framework for Steam **Happy Wheels 1.99.2**.

Created by Jimbob · [Join Discord](https://discord.gg/XcZePBgDBJ)

This repository does **not** include Happy Wheels, `Happy Wheels.exe`, or `app.asar`. You need a legal Steam copy of the game.

**Docs:** [https://mathewregier.github.io/jhwml/](https://mathewregier.github.io/jhwml/)

Other developers: start at [Your first mod](docs/first-mod.md), then [Make a mod](docs/make-a-mod.md). The stable in-game API is [`window.HWMod`](docs/api.md).

## Requirements

- Linux
- [Python 3](https://www.python.org/downloads/) with **Add python.exe to PATH** (to run from source or build the EXE)
- A legal Steam copy of Happy Wheels 1.99.2
- Close Happy Wheels before installing

## Run from source

```powershell
python installer\app.py
```

Or patch a known Steam folder:

```powershell
python tools\setup.py "C:\Program Files (x86)\Steam\steamapps\common\Happy Wheels"
```

## Build the EXE

```powershell
powershell -ExecutionPolicy Bypass -File installer\build.ps1
```

That writes `dist\JHWML - Mod Launcher.exe`. It does not ship the game.

A Steam update or **Verify integrity of game files** can remove the loader. Run the launcher again after that.

## Self-updates

Shipped EXEs check:

`https://raw.githubusercontent.com/MathewRegier/jhwml/main/mod-store/launcher.json`

The zip URL in that file should be a **GitHub Release** on this repo (`jhwml/releases`).

To ship a new EXE:

1. Bump `tools/launcher_version.py`
2. `powershell -ExecutionPolicy Bypass -File installer\build.ps1`
3. `python tools\publish_launcher.py`
4. Commit `mod-store/launcher.json` on this repo
5. `gh release create vX.Y.Z mod-store\zips\JHWML-Mod-Launcher-X.Y.Z.zip --title "JHWML X.Y.Z"`

## Layout

| Path | What it is |
| --- | --- |
| `installer/` | Launcher window and EXE build |
| `core/` | Loader injected into the game, plus `hw-mod-sdk.js` |
| `tools/packager.py` | Patches the Steam game in place |
| `docs/` | GitHub Pages developer docs |
| `examples/first-hw-mod/` | Step-by-step SDK tutorial (ride card HUD) |
| `examples/hello-hw-mod/` | Tiny overlay if you already know the layout |

## Help

[Join Discord](https://discord.gg/XcZePBgDBJ)
