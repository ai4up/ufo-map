#!/bin/bash

#SBATCH --qos=short
#SBATCH --time=00:10:00
#SBATCH --job-name=test-%A_%a
#SBATCH --partition=standard
#SBATCH --account=eubucco
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --output=test_out-%A_%a.txt
#SBATCH --error=test_err-%A_%a.txt

pwd; hostname; date

module load anaconda
module load osmium

source activate ox112

python -u test-sbb-cluster.py 
