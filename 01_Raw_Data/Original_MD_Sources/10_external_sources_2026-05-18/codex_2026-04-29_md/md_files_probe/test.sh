#!/bin/bash
#### Requesting job resources
### PBS -l select=[nodes]:ncpus=[cpus]:ngpus=[gpus]:mpiprocs=[mpiprocs]
#PBS -l select=1:ncpus=20:ngpus=2:mpiprocs=20

#### Setting email recipient list
###PBS -M schoe@localhost

#### mail option(Specifying email notification)
### a send mail when job is aborted by batch system
### b send mail when job begins execution
### e send mail when job ends execution
### n do not send mail
#PBS -m abe

#### Specifying queue and/or server
#PBS -q P100q

#### Marking a job as re-runnable or not
#PBS -r n

#### Exporting environment variables
#PBS -V

#### Specifying a job name
### PBS -N [jobname]
#PBS -N test_1_newf2



source /home/schoe/util/gromacs/bin/GMXRC
#source /home/schoe/util/intel/parallel_studio_xe_2015/bin/psxevars.sh

cd $PBS_O_WORKDIR

# Print some othe r environment information
echo Running on host `hostname`
echo Time is `date`
echo Directory is `pwd`
echo This jobs runs on the following processors:
NODES=`cat $PBS_NODEFILE`
echo $NODES

# Compute the number of processors
NPROCS=`wc -l < $PBS_NODEFILE`
echo This job has allocated $NPROCS nodes

export OMP_NUM_THREADS=1


#####################################################################

# minimization
#gmx grompp -f run0.mdp -c config.pdb -p field.top -o run0.tpr -maxwarn 5
#gmx mdrun -v -ntmpi $OMP_NUM_THREADS -deffnm run0 -pin on


# berendsen presure coupling
#gmx grompp -f run1.mdp -c run0.gro -p field.top -o run1.tpr -maxwarn 5
#gmx mdrun -v -ntmpi $OMP_NUM_THREADS -deffnm run1 -pin on


# P-R pressure coupling 
#gmx grompp -f run2.mdp -c run1.gro -r run1.gro -t run1.cpt -p field.top -o run2.tpr -maxwarn 5
#gmx mdrun -v -ntmpi $OMP_NUM_THREADS -deffnm run2 -pin on

# NPT  100ns
gmx grompp -f run3.mdp -c run2.gro -r run2.gro -t run2.cpt -p field.top -o run3.tpr -maxwarn 5
gmx mdrun -v -ntmpi $OMP_NUM_THREADS -deffnm run3 -pin on


