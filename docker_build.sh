#!/usr/bin/env bash

docker build "$@" -t "runsascoded/gsmo" -f "Dockerfile" "docker"
sha="$(git log -n1 --format=%h)"
docker tag "runsascoded/gsmo" "runsascoded/gsmo:$sha"
