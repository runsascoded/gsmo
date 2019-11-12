#!/usr/bin/env bash

set -ex

if [ $# -eq 0 ]; then
  echo "Usage: $0 <absolute module path>" >&2
  exit 1
fi

module="$1"
shift

before_first_slash="${module%%/}"
if [ ! -z "$before_first_slash" ]; then
  module="$PWD/$module"
fi

dir="$(dirname "${BASH_SOURCE[0]}")"
cd "$dir"

img_name=cron
img="$img_name:latest"
docker build -t "$img_name" .

docker run -v "$module:/src" "$@" "$img"
