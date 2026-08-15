#!/bin/sh
set -e
cd /app/backend
mkdir -p media staticfiles
exec "$@"
