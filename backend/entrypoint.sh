#!/bin/sh
set -eu

python -m api.model_seed
exec "$@"
