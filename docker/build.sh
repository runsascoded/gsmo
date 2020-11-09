#!/usr/bin/env bash

cd "$(dirname "${BASH_SOURCE[0]}")" && cd ..
python -m gsmo.docker.build "$@"
