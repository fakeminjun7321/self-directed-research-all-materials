# Render the actual L1P1x2 independent-replica R1 NPT 1 ns trajectory.
# The sampled multi-model PDB and output-frame directory are passed by env vars.

python
import os
from pymol import cmd

cmd.load(os.environ["MD_TRAJECTORY_PDB"], "r1_npt")
python end

remove elem H
hide everything, all
show sticks, resn c3c or resn fsi
show spheres, resn Li
show cell, r1_npt

set_color pyr13_color, [0.18, 0.72, 1.00]
set_color fsi_color, [1.00, 0.46, 0.12]
set_color lithium_color, [0.95, 0.25, 0.85]
color pyr13_color, resn c3c
color fsi_color, resn fsi
color lithium_color, resn Li

set stick_radius, 0.10
set sphere_scale, 0.68, resn Li
set cell_color, white
set orthoscopic, on
set depth_cue, on
set fog_start, 0.55
set antialias, 2
set ray_opaque_background, on
bg_color black

frame 1
orient all
turn x, -12
turn y, 18
zoom all, 2

python
import os
from pymol import cmd

out_dir = os.environ["MD_FRAME_DIR"]
os.makedirs(out_dir, exist_ok=True)

for state in range(1, 52):
    cmd.frame(state)
    cmd.png(
        os.path.join(out_dir, f"frame_{state:04d}.png"),
        width=960,
        height=540,
        dpi=120,
        ray=1,
        quiet=1,
    )
python end

quit
