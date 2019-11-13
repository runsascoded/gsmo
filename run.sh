#!/usr/bin/env bash

set -ex

if [ $# -eq 0 ]; then
  echo "Usage: $0 <absolute module path>" >&2
  exit 1
fi

module="$1"
shift

# canonicalize module path
module="$(cd "$module" && pwd)"

dir="$(dirname "${BASH_SOURCE[0]}")"
cd "$dir"

img_name=cron
img="$img_name:latest"
docker build -t "$img_name" .

docker run -v "$module:/src" "$@" "$img"
