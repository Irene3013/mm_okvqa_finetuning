#!/bin/bash

#SBATCH --job-name=ofa_okvqa                   # Name of the process
#SBATCH --cpus-per-task=2                      # Number of CPU cores (2 is reasonable)
#SBATCH --gres=gpu:2                           # Number of GPUs (usually light processes only need 1)
#SBATCH --mem=8G                               # RAM memory needed (8-16GB is reasonable for our servers, sometimes you'll need more)
#SBATCH --output=.slurm/OFA_prompt.log
#SBATCH --error=.slurm/OFA_prompt.err

source /gscratch/users/asalaberria009/env/p39-cu115/bin/activate

export TRANSFORMERS_CACHE="/gaueko0/transformers_cache/"

srun python mm_okvqa_finetuning.py --model "OFA-Sys/OFA-base" --target_model ofa --location_encoding none \
   --lr 2e-5 --batch_size 16 --max_steps 20000 --accumulate_grad_batches 2 \
   --run_name ofa_base_okvqa --train --evaluate --source vinvl \
   --root /gaueko0/users/ietxarri010/ofa_okvqa_finetuning/okvqa