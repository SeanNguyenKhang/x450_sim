#!/usr/bin/env python3
"""
Generate models/rice_plot: a 3D direct-seeded rice plot (~17 days after sowing)
for the X450 survey world.

Output (everything inside models/rice_plot is overwritten, do not edit by hand):
  model.config, model.sdf     Gazebo model, included by worlds/rice.sdf
  meshes/d<C>_v<V>.stl        tile meshes: density class C, random variant V
  ground_truth.csv            real plant count of every tile (world ENU + lat/lon)

How it works
  - The plot (default 50 x 50 m) is split into square tiles (default 2 x 2 m).
  - A smooth random density map (plants/m^2) is drawn over the tiles and
    quantised into a few density classes.
  - For each class a few tile meshes are generated (random plant positions);
    each tile in the field uses one of them, rotated by 0/90/180/270 deg,
    so the field does not look repeated.
  - One plant = 3..4 leaves; one leaf = one thin triangle, written with both
    windings so it is visible from both sides. Visual only: no collision,
    no shadows (keeps physics and rendering cheap).

Only needs python3 + numpy. Same --seed => same field.
Usage:  python3 tools/gen_rice_field.py            (defaults)
        python3 tools/gen_rice_field.py --help     (all options)
"""
import argparse
import math
import shutil
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
HOME_LAT, HOME_LON = 10.578723, 106.416590  # world origin (worlds/rice.sdf)


def parse_args():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", type=Path, default=REPO / "models" / "rice_plot")
    p.add_argument("--seed", type=int, default=17)
    p.add_argument("--size", type=float, default=50.0, help="plot side [m]")
    p.add_argument("--tile", type=float, default=2.0, help="tile side [m]")
    p.add_argument("--center", type=float, nargs=2, default=[-6.0, 2.5],
                   metavar=("X", "Y"), help="plot centre in world ENU [m]")
    p.add_argument("--z", type=float, default=0.02, help="ground height [m]")
    p.add_argument("--density-min", type=float, default=80.0, help="plants/m^2")
    p.add_argument("--density-max", type=float, default=320.0, help="plants/m^2")
    p.add_argument("--classes", type=int, default=5, help="density classes")
    p.add_argument("--variants", type=int, default=3, help="meshes per class")
    p.add_argument("--height", type=float, default=0.22, help="mean plant height [m]")
    p.add_argument("--leaf-width", type=float, default=0.008, help="leaf base width [m]")
    return p.parse_args()


# ---------------------------------------------------------------- geometry
def make_tile(rng, n_plants, tile, height, leaf_w):
    """Return (T,3,3) triangles of one tile centred at (0,0), ground at z=0."""
    half = tile / 2.0
    tris = []
    for _ in range(n_plants):
        base = np.array([rng.uniform(-half, half), rng.uniform(-half, half), 0.0])
        h = max(0.08, rng.normal(height, 0.15 * height))
        n_leaves = rng.integers(3, 5)          # 3 or 4
        az0 = rng.uniform(0, 2 * math.pi)
        for k in range(n_leaves):
            # rice leaves are distichous: alternate on two opposite sides
            az = az0 + k * math.pi + rng.normal(0, 0.35)
            elev = rng.uniform(math.radians(45), math.radians(80))
            length = h * rng.uniform(0.6, 1.0)
            tip = base + length * np.array([math.cos(elev) * math.cos(az),
                                            math.cos(elev) * math.sin(az),
                                            math.sin(elev)])
            side = 0.5 * leaf_w * np.array([-math.sin(az), math.cos(az), 0.0])
            tris.append((base + side, base - side, tip))
    t = np.array(tris, dtype=np.float32)
    # keep everything inside the tile so rotated tiles never overlap much
    t[:, :, :2] = np.clip(t[:, :, :2], -half, half)
    return t


def write_stl(path, tris):
    """Binary STL, every triangle twice (front + back face)."""
    both = np.concatenate([tris, tris[:, ::-1, :]])
    n = np.cross(both[:, 1] - both[:, 0], both[:, 2] - both[:, 0])
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    rec = np.zeros(len(both), dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)),
                                     ("a", "<u2")])
    rec["n"], rec["v"] = n, both
    with open(path, "wb") as f:
        f.write(b"x450_sim rice tile".ljust(80, b" "))
        f.write(np.uint32(len(both)).tobytes())
        f.write(rec.tobytes())
    return len(both)


# ---------------------------------------------------------------- density map
def density_map(rng, n, dmin, dmax):
    """Smooth random field on an n x n tile grid, scaled to [dmin, dmax]."""
    g = np.zeros((n, n))
    yy, xx = np.mgrid[0:n, 0:n]
    for _ in range(10):  # sum of random Gaussian bumps (dense and sparse patches)
        cx, cy = rng.uniform(0, n, 2)
        s = rng.uniform(n / 10, n / 4)
        g += rng.uniform(-1, 1) * np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * s * s))
    g = (g - g.min()) / max(np.ptp(g), 1e-9)
    return dmin + g * (dmax - dmin)


# ---------------------------------------------------------------- main
def main():
    a = parse_args()
    rng = np.random.default_rng(a.seed)
    n = int(round(a.size / a.tile))
    area = a.tile * a.tile
    levels = np.linspace(a.density_min, a.density_max, a.classes)

    out = a.out.resolve()
    if out.name != "rice_plot":   # safety: never wipe an unexpected folder
        raise SystemExit(f"refusing to overwrite {out} (folder must be named rice_plot)")
    if out.exists():
        shutil.rmtree(out)
    (out / "meshes").mkdir(parents=True)

    # 1. tile meshes
    counts = {}      # (class, variant) -> plants
    tile_tris = {}   # (class, variant) -> triangles
    for c, d in enumerate(levels):
        for v in range(a.variants):
            n_pl = int(round(d * area * rng.uniform(0.95, 1.05)))
            tris = make_tile(rng, n_pl, a.tile, a.height, a.leaf_width)
            tile_tris[(c, v)] = write_stl(out / "meshes" / f"d{c}_v{v}.stl", tris)
            counts[(c, v)] = n_pl
    total_tris = 0

    # 2. place tiles
    dens = density_map(rng, n, a.density_min, a.density_max)
    cls = np.abs(dens[..., None] - levels).argmin(axis=-1)
    m_per_deg_lat = 111320.0
    m_per_deg_lon = 111320.0 * math.cos(math.radians(HOME_LAT))

    visuals, rows = [], []
    for iy in range(n):
        for ix in range(n):
            c = int(cls[iy, ix])
            v = int(rng.integers(a.variants))
            yaw = int(rng.integers(4)) * math.pi / 2
            lx = -a.size / 2 + (ix + 0.5) * a.tile        # model frame
            ly = -a.size / 2 + (iy + 0.5) * a.tile
            wx, wy = a.center[0] + lx, a.center[1] + ly    # world ENU
            total_tris += tile_tris[(c, v)]
            visuals.append(f"""      <visual name="t_{ix:02d}_{iy:02d}">
        <pose>{lx:.3f} {ly:.3f} 0 0 0 {yaw:.4f}</pose>
        <cast_shadows>false</cast_shadows>
        <geometry><mesh><uri>model://rice_plot/meshes/d{c}_v{v}.stl</uri></mesh></geometry>
        <material>
          <ambient>0.30 0.45 0.12 1</ambient>
          <diffuse>0.42 0.62 0.18 1</diffuse>
          <specular>0.05 0.05 0.05 1</specular>
        </material>
      </visual>""")
            p = counts[(c, v)]
            rows.append(f"{ix},{iy},{wx:.3f},{wy:.3f},"
                        f"{HOME_LAT + wy / m_per_deg_lat:.8f},"
                        f"{HOME_LON + wx / m_per_deg_lon:.8f},"
                        f"{c},{v},{p},{p / area:.1f}")

    # 3. ground_truth.csv
    (out / "ground_truth.csv").write_text(
        "tile_ix,tile_iy,x_enu_m,y_enu_m,lat_deg,lon_deg,density_class,variant,"
        "plants,plants_per_m2\n" + "\n".join(rows) + "\n")

    # 4. model.config + model.sdf
    (out / "model.config").write_text(f"""<?xml version="1.0"?>
<model>
  <name>rice_plot</name>
  <version>1.0</version>
  <sdf version="1.9">model.sdf</sdf>
  <description>GENERATED by tools/gen_rice_field.py (seed {a.seed}) - do not edit by hand</description>
</model>
""")
    total_plants = sum(int(r.split(",")[8]) for r in rows)
    (out / "model.sdf").write_text(f"""<?xml version="1.0" encoding="UTF-8"?>
<!--
  GENERATED by tools/gen_rice_field.py - do not edit by hand, re-run the script.
  Direct-seeded rice ~17 days after sowing, {a.size:g} x {a.size:g} m, tiles {a.tile:g} m.
  Centre (world ENU): x = {a.center[0]:g}, y = {a.center[1]:g}   seed = {a.seed}
  Density {a.density_min:g}..{a.density_max:g} plants/m2, {a.classes} classes x {a.variants} variants
  Plants: {total_plants}   triangles: {total_tris}
  Ground truth per tile: model://rice_plot/ground_truth.csv
-->
<sdf version="1.9">
  <model name="rice_plot">
    <static>true</static>
    <pose>{a.center[0]:.3f} {a.center[1]:.3f} {a.z:.3f} 0 0 0</pose>
    <link name="link">
      <visual name="soil">
        <cast_shadows>false</cast_shadows>
        <geometry><plane><normal>0 0 1</normal><size>{a.size:g} {a.size:g}</size></plane></geometry>
        <material>
          <ambient>0.22 0.18 0.13 1</ambient>
          <diffuse>0.30 0.25 0.18 1</diffuse>
          <specular>0.10 0.10 0.10 1</specular>
        </material>
      </visual>
{chr(10).join(visuals)}
    </link>
  </model>
</sdf>
""")

    print(f"rice_plot -> {out}")
    print(f"  {n}x{n} tiles, {len(counts)} meshes, {total_plants} plants, "
          f"{total_tris / 1e6:.2f} M triangles")
    print(f"  mean density {total_plants / a.size ** 2:.0f} plants/m2")


if __name__ == "__main__":
    main()
