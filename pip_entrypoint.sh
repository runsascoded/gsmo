#!/usr/bin/env bash
# Docker entrypoint that pip-installs a (presumably mounted) directory before calling an existing entrypoint script

set -ex

n="$1"; shift
while [ $n -gt 0 ]; do
  dep="$1"; shift
  sudo pip install -e "$dep"
  n=$(($n-1))
done

"$@"
