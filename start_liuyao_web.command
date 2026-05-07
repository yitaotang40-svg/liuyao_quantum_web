#!/bin/zsh
cd "$(dirname "$0")"
/opt/anaconda3/envs/qiskit/bin/python app.py --host 127.0.0.1 --port 8765
