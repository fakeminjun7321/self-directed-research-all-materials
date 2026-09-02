mol delete all
set here [file dirname [info script]]
display projection Orthographic
display backgroundgradient off
color Display Background black
axes location Off
mol new [file join $here "01_all_five_50ps_animation.pdb"] type pdb waitfor all
set molid [molinfo top]
set nframes [molinfo $molid get numframes]
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
animate style Loop
animate speed 1.0
animate goto 0

set frame_number 0
proc force_play_frames {} {
    global frame_number nframes
    animate goto $frame_number
    display update ui
    incr frame_number
    if {$frame_number >= $nframes} {
        set frame_number 0
    }
    after 80 force_play_frames
}

after 1000 force_play_frames
puts "Loaded five 50 ps trajectories with $nframes sampled frames."
vwait forever
