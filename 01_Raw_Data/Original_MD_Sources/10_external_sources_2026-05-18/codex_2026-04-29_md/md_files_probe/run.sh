#!/bin/bash

#PBS -l nodes=1:ppn=8
#PBS -q long
#PBS -N test


#source /home/schoe/util/gromacs/bin/GMXRC
#source /home/schoe/util/intel/parallel_studio_xe_2015/bin/psxevars.sh

cd $PBS_O_WORKDIR


# Compute the number of processors
NPROCS=`wc -l < $PBS_NODEFILE`
echo This job has allocated $NPROCS nodes

export OMP_NUM_THREADS=4


#####################################################################

# minimization
#gmx grompp -f run0.mdp -c config.pdb -p field.top -o run0.tpr -maxwarn 5
#gmx mdrun -v -ntmpi $OMP_NUM_THREADS -deffnm run0 -pin on


# berendsen presure coupling
gmx grompp -f run1.mdp -c run0.gro -p field.top -o run1.tpr -maxwarn 5
gmx mdrun -v -ntmpi $OMP_NUM_THREADS -deffnm run1 -pin on


# P-R pressure coupling 
gmx grompp -f run2.mdp -c run1.gro -r run1.gro -t run1.cpt -p field.top -o run2.tpr -maxwarn 5
gmx mdrun -v -ntmpi $OMP_NUM_THREADS -deffnm run2 -pin on

# NPT  100ns
gmx grompp -f run3.mdp -c run2.gro -r run2.gro -t run2.cpt -p field.top -o run3.tpr -maxwarn #5
gmx mdrun -v -ntmpi $OMP_NUM_THREADS -deffnm run3 -pin on


