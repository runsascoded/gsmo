#!/usr/bin/env bash
# Docker entrypoint that sets correct permissions on /var/run/docker.sock before delegating to original entrypoint;
# see https://github.com/docker/for-mac/issues/4755

chgrp docker /var/run/docker.sock
chmod g+w /var/run/docker.sock
"$@"
