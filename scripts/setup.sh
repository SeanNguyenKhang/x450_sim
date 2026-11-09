#!/usr/bin/env bash
# Link this out-of-tree X450 simulation package into a PX4-Autopilot checkout.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PX4="${PX4_DIR:-$HOME/PX4-Autopilot}"
GZ="$PX4/Tools/simulation/gz"
AF="$PX4/ROMFS/px4fmu_common/init.d-posix/airframes"

[[ -d "$GZ/models" ]] || { echo "PX4 not found at $PX4 (set PX4_DIR)"; exit 1; }

link() { ln -sfn "$1" "$2"; echo "  $(basename "$2") -> $1"; }

# Generated rice plot (git-ignored). REGEN=1 bash scripts/setup.sh forces a rebuild.
if [[ ! -f "$REPO/models/rice_plot/model.sdf" || "${REGEN:-0}" == "1" ]]; then
  echo "Generating models/rice_plot:"
  python3 "$REPO/tools/gen_rice_field.py"
fi

echo "Models:"
for m in "$REPO"/models/*/; do
  n=$(basename "$m"); link "$REPO/models/$n" "$GZ/models/$n"
done

echo "Worlds:"
for w in "$REPO"/worlds/*.sdf; do
  link "$w" "$GZ/worlds/$(basename "$w")"
done

echo "Airframes:"
for a in "$REPO"/airframes/*; do
  n=$(basename "$a"); link "$a" "$AF/$n"
  if ! grep -qx "[[:space:]]*$n" "$AF/CMakeLists.txt"; then
    sed -i "/^[[:space:]]*4001_gz_x500$/a\\\t$n" "$AF/CMakeLists.txt"
    echo "  + added $n to CMakeLists.txt"
  fi
done
echo "Done."