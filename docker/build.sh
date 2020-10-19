#!/usr/bin/env bash

cd "$(dirname "${BASH_SOURCE[0]}")" || exit 1
docker build "$@" -t "runsascoded/gsmo" -f "Dockerfile" .
if git diff --quiet --exit-code HEAD; then
  sha="$(git log -n1 --format=%h)"
  docker tag "runsascoded/gsmo" "runsascoded/gsmo:$sha"
else
  echo "Detected uncommitted changes; skipping Git SHA tag"
fi
