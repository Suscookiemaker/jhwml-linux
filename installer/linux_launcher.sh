#!/usr/bin/env bash
# JHWML - Linux Game Launcher
#
# Wrapper script to launch Happy Wheels with the mod loader.
# Place this in the Happy Wheels root folder for convenient launching.
#
# Usage:
#   ./linux_launcher.sh           # Launch the game
#   ./linux_launcher.sh --help    # Show game options

set -euo pipefail

GAME_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GAME_BIN="${GAME_ROOT}/game/happy-wheels-bin"
START_BASH="${GAME_ROOT}/start.bash"

if [[ ! -f "${GAME_BIN}" ]] && [[ ! -f "${START_BASH}" ]]; then
    echo "Error: Could not find the Happy Wheels executable." >&2
    echo "This script must be in the Happy Wheels root folder." >&2
    exit 1
fi

# Use the official start.bash if available, otherwise launch the binary directly.
if [[ -f "${START_BASH}" ]]; then
    exec "${START_BASH}" "$@"
else
    # Fallback: launch the binary with X11 platform.
    export LC_ALL=C
    unset LD_PRELOAD
    exec "${GAME_BIN}" --ozone-platform=x11 "$@"
fi
