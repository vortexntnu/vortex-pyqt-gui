#!/bin/bash
SSH_HOST="${1}"
SSH_KEY="${2:-/home/luna/.ssh/id_rsa}"

ssh -i "$SSH_KEY" \
    -p 22 \
    -o StrictHostKeyChecking=no \
    -o BatchMode=yes \
    -o ServerAliveInterval=5 \
    -o ServerAliveCountMax=3 \
    "$SSH_HOST" \
    "tail -f /dev/null"
