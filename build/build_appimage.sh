#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
mkdir -p dist
docker build -f build/Dockerfile -t proton-picker-setup-build .
container="$(docker create proton-picker-setup-build)"
trap 'docker rm "$container" >/dev/null 2>&1 || true' EXIT
docker cp "$container:/out/." dist/
ls -lh dist
