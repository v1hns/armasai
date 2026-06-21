"""Remesh the baked Gizmo shoe into a light, clean, browser-friendly STL.

The raw Gizmo "preview" export (assets/objects/shoe/a_single_sneaker_running_shoe.xml)
is a ~1M-face *polygon soup* — a noisy photogrammetry-style reconstruction whose
faces barely share vertices. It renders fine at full res but decimating it directly
gives a lumpy/spiky mess. So we **voxel-remesh** it (resample the surface into a
clean watertight mesh via marching cubes), lightly smooth it, then decimate to a
few thousand faces. The result is a smooth, recognizable shoe that MuJoCo can
instance per agent (one shared `shoe_mesh` asset; only draw calls multiply).

Needs scikit-image (marching cubes) + trimesh + fast_simplification.

    python3 scripts/recon/decimate_shoe.py                 # ~8k faces, smooth
    python3 scripts/recon/decimate_shoe.py --pitch 0.001 --faces 12000
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
GIZMO_XML = ROOT / "assets" / "objects" / "shoe" / "a_single_sneaker_running_shoe.xml"
OUT = ROOT / "webdemo" / "assets" / "scenes" / "arm_links" / "shoe.stl"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--faces", type=int, default=8000, help="target face count")
    ap.add_argument("--pitch", type=float, default=0.0012, help="voxel size (m); smaller = crisper")
    ap.add_argument("--smooth", type=int, default=3, help="Taubin smoothing iterations")
    ap.add_argument("--length", type=float, default=0.25, help="target shoe length (m)")
    ap.add_argument("--src", default=str(GIZMO_XML))
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()

    import fast_simplification
    import mujoco
    import trimesh

    src = Path(args.src)
    if not src.exists():
        print(f"[shoe] no Gizmo bake at {src} — rebake via gizmo_assets.py", file=sys.stderr)
        return 1

    m = mujoco.MjModel.from_xml_path(str(src))
    va, nv = int(m.mesh_vertadr[0]), int(m.mesh_vertnum[0])
    fa, nf = int(m.mesh_faceadr[0]), int(m.mesh_facenum[0])
    verts = np.array(m.mesh_vert[3 * va:3 * (va + nv)], dtype=np.float64).reshape(-1, 3)
    faces = np.array(m.mesh_face[3 * fa:3 * (fa + nf)], dtype=np.int64).reshape(-1, 3)
    print(f"[shoe] source soup: {nv} verts, {nf} faces")

    soup = trimesh.Trimesh(vertices=verts, faces=faces, process=False)
    # Voxel-remesh the soup into a clean watertight surface (direct decimation of
    # the disconnected soup produces lumps/spikes).
    rem = soup.voxelized(pitch=args.pitch).fill().marching_cubes
    print(f"[shoe] voxel remesh (pitch {args.pitch}) -> {len(rem.faces)} faces")
    if args.smooth:
        trimesh.smoothing.filter_taubin(rem, iterations=args.smooth)
    target = max(500, min(args.faces, len(rem.faces)))
    vo, fo = fast_simplification.simplify(rem.vertices, rem.faces, target_count=target)
    mesh = trimesh.Trimesh(vo, fo, process=True)
    print(f"[shoe] decimated to {len(mesh.faces)} faces")

    # Stand the shoe UPRIGHT on its sole. The sole is the dominant flat surface —
    # the direction the most mesh-area shares a normal with — so make that axis
    # vertical and put the flatter (sole) side down. Then point the longest axis
    # forward (+y). Bounding-box extents alone can't tell sole from side here
    # (width ≈ height), which is why the shoe came out lying on its side.
    N, Af = mesh.face_normals, mesh.area_faces
    cov = (Af[:, None, None] * (N[:, :, None] * N[:, None, :])).sum(0)
    eigval, eigvec = np.linalg.eigh(cov)
    sole_axis = eigvec[:, int(np.argmax(eigval))]       # dominant (sole) normal
    mesh.apply_transform(trimesh.geometry.align_vectors(sole_axis, [0, 0, 1]))
    up = (mesh.area_faces * np.clip(mesh.face_normals[:, 2], 0, None)).sum()
    dn = (mesh.area_faces * np.clip(-mesh.face_normals[:, 2], 0, None)).sum()
    if up > dn:                                         # flatter side faces up -> flip sole down
        mesh.apply_transform(trimesh.transformations.rotation_matrix(np.pi, [1, 0, 0]))
    mesh.apply_translation(-mesh.bounds.mean(axis=0))
    if mesh.extents[0] > mesh.extents[1]:              # longest horizontal axis -> forward (y)
        mesh.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [0, 0, 1]))
    mesh.fix_normals()
    mesh.apply_scale(args.length / float(mesh.extents[1]))
    mesh.apply_translation([0, 0, -mesh.bounds[0][2]])  # sole on the floor (min z -> 0)
    bnds = mesh.bounds
    print(f"[shoe] final extents (m): {np.round(mesh.extents, 3).tolist()}  "
          f"z range [{bnds[0][2]:.3f}, {bnds[1][2]:.3f}]")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    mesh.export(out)
    print(f"[shoe] wrote {out.relative_to(ROOT)}  ({out.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
