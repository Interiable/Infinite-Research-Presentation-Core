#!/bin/bash
export PATH="/usr/local/cuda/bin:/home/hgeon/miniconda3/bin:/home/hgeon/miniconda3/condabin:$PATH"
export CONDA_PREFIX="/home/hgeon/miniconda3"
export CONDA_DEFAULT_ENV="base"
/home/hgeon/miniconda3/bin/python test_deep_research_node.py
