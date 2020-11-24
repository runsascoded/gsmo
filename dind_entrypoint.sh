#!/usr/bin/env bash
# Docker entrypoint that sets correct permissions on /var/run/docker.sock before delegating to original entrypoint;
# see https://github.com/docker/for-mac/issues/4755

set -ex

ls -l /var/run/docker.sock
sudo chgrp docker /var/run/docker.sock
sudo getent group docker
sudo chmod g+w /var/run/docker.sock
ls -l /var/run/docker.sock
"$@"
