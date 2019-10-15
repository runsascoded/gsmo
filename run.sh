#!/usr/bin/env bash

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

docker run -v $module:/src cron:latest
