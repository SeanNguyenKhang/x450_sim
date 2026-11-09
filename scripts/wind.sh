#!/usr/bin/env bash
# Change the mean wind of the running rice world (gusts are added by WindEffects).
#   bash scripts/wind.sh SPEED [FROM_DEG]
#   SPEED    mean wind speed [m/s] (0 = calm)
#   FROM_DEG direction the wind comes FROM, like a weather report:
#            0 = from North, 90 = from East, 180 = from South, 270 = from West
# Example:  bash scripts/wind.sh 5 90     # 5 m/s easterly wind (blows toward West)
set -euo pipefail

SPEED="${1:?usage: bash scripts/wind.sh SPEED [FROM_DEG]}"
FROM="${2:-0}"
WORLD="${PX4_GZ_WORLD:-rice}"

# Gazebo world is ENU (x = East, y = North); the wind blows toward FROM + 180 deg.
read -r VX VY < <(python3 -c "import math,sys; s,f=float(sys.argv[1]),math.radians(float(sys.argv[2])); print(f'{-s*math.sin(f):.3f} {-s*math.cos(f):.3f}')" "$SPEED" "$FROM")

gz topic -t "/world/$WORLD/wind" -m gz.msgs.Wind \
  -p "linear_velocity: {x: $VX, y: $VY, z: 0}, enable_wind: true"
echo "Wind: $SPEED m/s from $FROM deg  ->  ENU velocity (x=$VX, y=$VY) m/s"
