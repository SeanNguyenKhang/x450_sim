#!/usr/bin/env python3
"""
Generate a lawn-mower (boustrophedon) survey mission as a QGroundControl .plan.

Pattern (see tools/field_site.py for the survey frame):
  TAKEOFF at home (SE paddy corner) to ALT -> DO_CHANGE_SPEED
  line 1: straight along the East (right) bank, from home to
          START_MARGIN + LINE_LENGTH metres
  turn left by SPACING, line 2 back down, turn left, line 3 up, ...
  every line surveys LINE_LENGTH metres starting START_MARGIN inside the
  South bank; lines stay within SURVEY_WIDTH to the left of the East bank
  -> RTL (return altitude = RTL_RETURN_ALT in airframes/4050_gz_x450, 6 m)

Line spacing:  --spacing S (m)  or  --overlap P (side overlap, 0..1)
  camera footprint across track = 2 * ALT * tan(HFOV / 2)
  spacing = footprint * (1 - overlap)

Usage (QGC: Plan -> Open... -> the .plan file -> Upload -> Fly: Start Mission):
  python3 tools/gen_lawnmower.py                           # 6 m, 1.5 m/s, 30 %
  python3 tools/gen_lawnmower.py --alt 8 --speed 2 --overlap 0.5
"""
import argparse
import json
import math
from pathlib import Path

from field_site import (BANK_BEARING_DEG, HOME_LAT, HOME_LON, LINE_LENGTH, START_MARGIN,
                        SURVEY_WIDTH, enu_to_latlon, south_bank_v, survey_to_enu)

REPO = Path(__file__).resolve().parent.parent
CAM_HFOV = 1.855  # rad, models/caddx_cam (image width is across track)

# MAVLink commands / frames
NAV_WAYPOINT, NAV_RTL, NAV_TAKEOFF, DO_CHANGE_SPEED = 16, 20, 22, 178
FRAME_GLOBAL_REL_ALT, FRAME_MISSION = 3, 2


def parse_args():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--alt", type=float, default=6.0, help="altitude AGL [m]")
    p.add_argument("--speed", type=float, default=1.5, help="survey ground speed [m/s]")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--overlap", type=float, default=0.3, help="side overlap 0..1")
    g.add_argument("--spacing", type=float, help="line spacing [m] (overrides --overlap)")
    p.add_argument("--out", type=Path, help="output .plan (default: missions/<name>.plan)")
    return p.parse_args()


def survey_waypoints(spacing):
    """Waypoints (world ENU) after takeoff at home, in flight order."""
    n = int(math.floor(SURVEY_WIDTH / spacing + 1e-9)) + 1
    wps = []
    for k in range(n):
        u = -k * spacing
        v0 = south_bank_v(u) + START_MARGIN
        bottom, top = survey_to_enu(u, v0), survey_to_enu(u, v0 + LINE_LENGTH)
        if k == 0:
            wps.append(top)                 # line 1 starts at home itself
        elif k % 2:
            wps += [top, bottom]            # turn left at the top, fly down
        else:
            wps += [bottom, top]            # turn left at the bottom, fly up
    return wps, n


def item(seq, cmd, frame, params):
    return {"type": "SimpleItem", "autoContinue": True, "command": cmd,
            "doJumpId": seq, "frame": frame, "params": params}


def main():
    a = parse_args()
    footprint = 2 * a.alt * math.tan(CAM_HFOV / 2)
    spacing = a.spacing if a.spacing else footprint * (1 - a.overlap)
    wps, n = survey_waypoints(spacing)

    items = [item(1, NAV_TAKEOFF, FRAME_GLOBAL_REL_ALT,
                  [0, 0, 0, None, HOME_LAT, HOME_LON, a.alt]),
             item(2, DO_CHANGE_SPEED, FRAME_MISSION, [1, a.speed, -1, 0, 0, 0, 0])]
    for x, y in wps:
        lat, lon = enu_to_latlon(x, y)
        items.append(item(len(items) + 1, NAV_WAYPOINT, FRAME_GLOBAL_REL_ALT,
                          [0, 0, 0, None, round(lat, 8), round(lon, 8), a.alt]))
    items.append(item(len(items) + 1, NAV_RTL, FRAME_MISSION, [0] * 7))
    for it in items:   # QGC also wants these on altitude items
        if it["frame"] == FRAME_GLOBAL_REL_ALT:
            it.update({"Altitude": a.alt, "AltitudeMode": 1, "AMSLAltAboveTerrain": None})

    plan = {
        "fileType": "Plan", "version": 1, "groundStation": "QGroundControl",
        "geoFence": {"circles": [], "polygons": [], "version": 2},
        "rallyPoints": {"points": [], "version": 2},
        "mission": {"version": 2, "firmwareType": 12, "vehicleType": 2,
                    "cruiseSpeed": 15, "hoverSpeed": a.speed,
                    "globalPlanAltitudeMode": 1,
                    "plannedHomePosition": [HOME_LAT, HOME_LON, 6],
                    "items": items},
    }

    name = f"lawnmower_a{a.alt:g}_v{a.speed:g}_s{spacing:.1f}"
    out = a.out or REPO / "missions" / f"{name}.plan"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(plan, indent=2) + "\n")

    path = [(0.0, 0.0)] + wps + [(0.0, 0.0)]
    length = sum(math.dist(p, q) for p, q in zip(path, path[1:]))
    print(f"{out}")
    print(f"  alt {a.alt:g} m, speed {a.speed:g} m/s, footprint {footprint:.1f} m across track")
    print(f"  {n} lines along bearing {BANK_BEARING_DEG:g} deg, spacing {spacing:.2f} m "
          f"(side overlap {(1 - spacing / footprint) * 100:.0f} %), {LINE_LENGTH:g} m each")
    print("  waypoints ENU: " + "  ".join(f"({x:.1f},{y:.1f})" for x, y in wps))
    print(f"  path ~{length:.0f} m incl. return, ~{length / a.speed / 60:.1f} min at {a.speed:g} m/s")


if __name__ == "__main__":
    main()
