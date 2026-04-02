#!/bin/bash
NAME=$1
CMD=$2

echo "[$NAME] Running: $CMD"
bash -c "$CMD"

