# Run record: pilot_L1P1x2_rho1400_v2

- System: L1P1x2 = Li 50 / Pyr13 50 / FSI 100 (2300 atoms)
- Protocol: v0.2-candidate
- Requested initial density: 1400.000 kg/m³
- Calculated cubic box: 3.085725 nm
- Start: 2026-08-06T23:34:38+09:00
- End: 2026-08-06T23:34:40+09:00
- Technical status: FAILED
- Physics status: NOT_VERIFIED
- Detail: CalledProcessError: Command '['gmx', 'grompp', '-f', 'input/em.mdp', '-c', 'input/initial.gro', '-p', 'input/topol.top', '-o', 'em.tpr', '-po', 'em_out.mdp']' returned non-zero exit status 1.

The requested density is an engineering pilot input, not an approved physical target. Energy minimization does not establish equilibrium or validate transport properties.
