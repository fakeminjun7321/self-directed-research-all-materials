# Candidate input files

- `topol.top`: actual candidate topology; charges scaled uniformly by 0.75.
- `field_full_charge_REFERENCE_ONLY.top`: raw fftool output with full charges; do not use for this candidate.
- `initial.gro`: Packmol coordinates converted from fftool `config.pdb`.
- `em.mdp`: strict energy-minimization input copied from the handoff baseline.
