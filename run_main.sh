#!/bin/bash

#SBATCH --partition=gpu --gres=gpu:1
#SBATCH -N 1
#SBATCH -n 4
#SBATCH -t 60:00:00
#SBATCH --mem=100g

# Load a CUDA module
module load cuda
module load miniconda3/23.11.0s
source /gpfs/runtime/opt/miniconda/4.12.0/etc/profile.d/conda.sh

conda activate qbam

# Run program
cd /users/bjoo2/code/qbam/qbam_gnn
# python3 grid_search.py --data /users/bjoo2/data/bjoo2/qbam/data --pred TER --chkpt_path /users/bjoo2/data/bjoo2/qbam/checkpoints --img_path /users/bjoo2/data/bjoo2/qbam/graphs --results_path /users/bjoo2/data/bjoo2/qbam/text_out
python3 grid_search.py --data /users/bjoo2/scratch/csam_data/csam10 --pred TER --chkpt_path /users/bjoo2/scratch/csam_data/checkpoints --img_path /users/bjoo2/scratch/csam_data/graphs --results_path /users/bjoo2/scratch/csam_data/text_out

# declare -a arr=("TER" "VEGF" "Both")
# for i in "${arr[@]}"
# do
#     echo "Grid Searching $i"
#     python3 grid_search.py --data /users/bjoo2/data/bjoo2/qbam/data --pred "$i" --chkpt_path /users/bjoo2/code/qbam/qbam_gnn/checkpoints --img_path /users/bjoo2/code/qbam/qbam_gnn/graphs --results_path /users/bjoo2/code/qbam/qbam_gnn/text_out
# done