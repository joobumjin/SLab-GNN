#!/bin/bash

#SBATCH --partition=gpu --gres=gpu:1  --output=optuna_shuffle_data.out
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

# declare -a arr=("TER" "VEGF" "Both")
# declare -a arr=("VEGF" "Both")
# for i in "${arr[@]}"
# do
#     echo "Optuna Searching on $i"
#     python3 grid_search_optuna.py --data /users/bjoo2/data/bjoo2/qbam/data --pred "$i" --log_path /users/bjoo2/code/qbam/qbam_gnn/optuna_logs/
#     # python3 grid_search_optuna.py --data /users/bjoo2/data/bjoo2/qbam/data/combined_data/graphs --pred "$i" --log_path /users/bjoo2/code/qbam/qbam_gnn/optuna_logs
# done

python3 grid_search_optuna.py --data /users/bjoo2/scratch/csam_data/csam15 --pred TER --log_path /users/bjoo2/code/qbam/qbam_gnn/optuna_logs/ --study_name csam_data15
