mol delete all
set here [file dirname [info script]]
display projection Orthographic
display backgroundgradient off
color Display Background black
axes location Off
mol new [file join $here "03_P2_series_50ps_animation.pdb"] type pdb waitfor all
mol delrep 0 top
mol representation VDW 0.45 16
mol color Element
mol selection all
mol addrep top
rotate x by -18
rotate y by 12
scale by 0.45
draw color white
draw text {-112.0 32.0 0.0} "L1P2" size 3.2 thickness 3
draw text {-12.0 32.0 0.0} "L2P2" size 3.2 thickness 3
draw text {88.0 32.0 0.0} "L3P2" size 3.2 thickness 3
animate style Loop
animate speed 0.35
animate goto 0
animate forward
puts "Loaded P2-series 50 ps trajectory (101 frames per system)."
vwait forever
