#!/usr/bin/env bash

set -euo pipefail

sudo mount -t nfs nas.home:/volume1/docker/media /mnt/nfs/media1
sudo mount -t nfs nas.home:/volume2/media /mnt/nfs/media2
sudo mount -t nfs nas.home:/volume3/media3 /mnt/nfs/media3
