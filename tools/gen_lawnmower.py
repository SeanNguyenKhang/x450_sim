#!/usr/bin/env python3
"""
Generate a lawn-mower (boustrophedon) survey mission as a QGroundControl .plan.

Mission: TAKEOFF to ALT -> DO_CHANGE_SPEED -> N-S survey lines -> RTL.
Lines run North-South over the rice plot (tools/field_site.py) and are spaced
along East-West. The start corner is the one nearest to home.

Line spacing:  --spacing S (m)  or  --overlap P (side overlap, 0..1).
  Camera footprint across track = 2 * ALT * tan(HFOV / 2)
  spacing = footprint * (1 - overlap)
  Lines are centred on the plot; n = ceil((plot - footprint) / spacing) + 1,
  so the outer image edges always reach the plot edges.

Usage (QGC: Plan -> Open... -> the .plan file -> Upload -> Fly: Start Mission):
  python3 tools/gen_lawnmower.py                           # 6 m, 1.5 m/s, 30 %
  python3 tools/gen_lawnmower.py --alt 8 --speed 2 --overlap 0.5
"""
import argparse
import json
import math
from pathlib import Path

from field_site import HOME_LAT, HOME_LON, PLOT_CENTER, PLOT_SIZE, enu_to_latlon

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


def survey_lines(alt, spacing):
    """Return list of ((x0,y0),(x1,y1)) N-S lines in ENU, serpentine order."""
    footprint = 2 * alt * math.tan(CAM_HFOV / 2)
    n = max(1, math.ceil(max(PLOT_SIZE - footprint, 0) / spacing) + 1)
    cx, cy = PLOT_CENTER
    half = PLOT_SIZE / 2
    xs = [cx + (i - (n - 1) / 2) * spacing for i in range(n)]
    ys, yn = cy - half, cy + half

    # pick start corner nearest to home (0, 0)
    best = None
    for west_first in (True, False):
        for south_first in (True, False):
            order = xs if west_first else xs[::-1]
            y0 = ys if south_first else yn
            d = math.hypot(order[0], y0)
            if best is None or d < best[0]:
                best = (d, order, south_first)
    _, order, south_first = best

    lines = []
    for i, x in enumerate(order):
        up = (i % 2 == 0) == south_first   # True: fly south -> north
        lines.append(((x, ys), (x, yn)) if up else ((x, yn), (x, ys)))
    return lines, footprint


def item(seq, cmd, frame, params):
    return {"type": "SimpleItem", "autoContinue": True, "command": cmd,
            "doJumpId": seq, "frame": frame, "params": params}


def main():
    a = parse_args()
    footprint = 2 * a.alt * math.tan(CAM_HFOV / 2)
    spacing = a.spacing if a.spacing else footprint * (1 - a.overlap)
    lines, _ = survey_lines(a.alt, spacing)

    items = [item(1, NAV_TAKEOFF, FRAME_GLOBAL_REL_ALT,
                  [0, 0, 0, None, HOME_LAT, HOME_LON, a.alt]),
             item(2, DO_CHANGE_SPEED, FRAME_MISSION, [1, a.speed, -1, 0, 0, 0, 0])]
    wps = [pt for ln in lines for pt in ln]
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

    length = sum(math.dist(p, q) for p, q in zip([(0, 0)] + wps, wps + [(0, 0)]))
    side = 1 - spacing / footprint
    print(f"{out}")
    print(f"  alt {a.alt:g} m, speed {a.speed:g} m/s, footprint {footprint:.1f} m across track")
    print(f"  {len(lines)} lines N-S, spacing {spacing:.2f} m (side overlap {side * 100:.0f} %)")
    print(f"  line x (ENU): " + ", ".join(f"{ln[0][0]:.1f}" for ln in lines))
    print(f"  path ~{length:.0f} m incl. transit, ~{length / a.speed / 60:.1f} min at {a.speed:g} m/s")


if __name__ == "__main__":
    main()
