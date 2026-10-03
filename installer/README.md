# JHWML - Mod Launcher (Linux)

Installs the JHWML mod loader into the Linux Happy Wheels 1.99.2 installation.

## Installation

Run the installer script from the project root:

```bash
python3 installer/linux_install.py
```

The script will:
1. Auto-detect your Happy Wheels folder (or accept a path)
2. Back up the original `app.asar`
3. Patch it with the mod loader
4. Create a `mods/` directory
5. Set up runtime files

## Manual installation

If you prefer to specify the game folder:

```bash
python3 installer/linux_install.py /home/user/.steam/steam/steamapps/common/Happy\ Wheels
```

Or pass `--force` to reinstall even if a backup exists:

```bash
python3 installer/linux_install.py --force
```

## Launching the game

1. **From Steam:** Just launch Happy Wheels normally.
2. **From the launcher script:** Copy `installer/linux_launcher.sh` to your game folder and run it:
   ```bash
   cp installer/linux_launcher.sh ~/.steam/steam/steamapps/common/Happy\ Wheels/
   chmod +x ~/.steam/steam/steamapps/common/Happy\ Wheels/linux_launcher.sh
   ./linux_launcher.sh
   ```
3. **From the command line:**
   ```bash
   cd ~/.steam/steam/steamapps/common/Happy\ Wheels/
   ./start.bash
   ```

## Installing mods

After patching:

1. Create a folder for your mod in `Happy Wheels/mods/`
2. Add a `mod.json` file and your mod code
3. Restart Happy Wheels to load it

Example structure:
```
Happy Wheels/mods/
├── my-awesome-mod/
│   ├── mod.json
│   ├── main.js
│   ├── web/
│   │   └── index.html
│   └── assets/
│       └── image.png
```

For detailed mod development docs, see: https://mathewregier.github.io/jhwml/

## Uninstalling / Restoring

The installer automatically backs up your original `app.asar` to `app.asar.backup`.

To restore the unmodded version:

```bash
cd ~/.steam/steam/steamapps/common/Happy\ Wheels/resources/
rm app.asar
mv app.asar.backup app.asar
```

Or let Steam verify the game files:

```
Steam > Library > Happy Wheels > Properties > Local Files > Verify integrity
```

Then reinstall the loader when ready.

## Troubleshooting

**"Could not find app.asar"**
- Make sure Happy Wheels is installed to the standard Steam folder
- Try specifying the path manually

**"Backup already exists"**
- The game was already patched, or an install failed
- Use `--force` to reinstall
- Or restore from backup first (see Uninstalling above)

**Mods not loading**
- Restart the game after adding/updating a mod
- Check that your `mod.json` is valid JSON
- Verify the mod folder is in `Happy Wheels/mods/`

**Game won't start**
- The ASAR may be corrupted
- Restore from `app.asar.backup` or verify game files
- Reinstall the loader

## Help

- **Mod development:** https://mathewregier.github.io/jhwml/
- **Discord:** https://discord.gg/XcZePBgDBJ
- **GitHub:** https://github.com/Suscookiemaker/jhwml-linux
