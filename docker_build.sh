#!/usr/bin/env bash

docker build "$@" -t "runsascoded/gsmo" -f "Dockerfile" "docker"
if git diff --quiet --exit-code HEAD; then
  sha="$(git log -n1 --format=%h)"
  docker tag "runsascoded/gsmo" "runsascoded/gsmo:$sha"
fi
