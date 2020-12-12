#!/usr/bin/env bash
# Docker entrypoint that pip-installs a (presumably mounted) directory before calling an existing entrypoint script

set -ex

# Work-around for https://github.com/docker/for-linux/issues/433#issuecomment-743780143
ls -la /root &>/dev/null

/bin/bash
