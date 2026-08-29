#!/bin/sh
set -eu

mkdir -p /data
chown samepage:samepage /data
chmod 0700 /data

exec setpriv --reuid=samepage --regid=samepage --init-groups "$@"
