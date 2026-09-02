mol delete all
set here [file dirname [info script]]
display projection Orthographic
display backgroundgradient off
color Display Background black
axes location Off
mol new [file join $here "02_all_five_initial_structure.pdb"] type pdb waitfor all
mol delrep 0 top
mol representation VDW 0.45 16
mol color Element
mol selection all
mol addrep top
rotate x by -18
rotate y by 12
scale by 0.55
draw color white
draw text {-92.0 56.0 0.0} "L1P1" size 2.8 thickness 3
draw text {-12.0 56.0 0.0} "L1P2" size 2.8 thickness 3
draw text {68.0 56.0 0.0} "L2P1" size 2.8 thickness 3
draw text {-52.0 -18.0 0.0} "L3P1" size 2.8 thickness 3
draw text {28.0 -18.0 0.0} "L1P3" size 2.8 thickness 3
vwait forever
