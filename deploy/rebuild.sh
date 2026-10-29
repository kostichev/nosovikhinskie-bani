#!/usr/bin/env bash
# Пересборка сайта на сервере из данных админки. Вызывается админкой и после обновлений кода.
set -euo pipefail
DIR=/var/www/nosbani
DATA=/var/lib/nosbani/site.json
mkdir -p /var/lib/nosbani
exec 9>/var/lib/nosbani/build.lock; flock -w 120 9
[ -f "$DATA" ] || cp "$DIR/build/data/site.json" "$DATA"
python3 -B "$DIR/deploy/patch-data.py" "$DATA" "$DIR/build/data/patches.json" || true
set -a; [ -f /etc/nosbani/site.env ] && . /etc/nosbani/site.env; set +a
TMP=$(mktemp -d /var/lib/nosbani/build.XXXXXX)
trap 'rm -rf "$TMP"' EXIT
cp -a "$DIR/site/." "$TMP/"
cd "$DIR/build"
SERVER=1 ASSETS="$DIR/build" OUT_DIR="$TMP" SITE_DATA="$DATA" python3 -B build2.py >/dev/null
for f in index.html; do [ -s "$TMP/$f" ] || { echo "сборка пустая" >&2; exit 1; }; done
cp -a "$TMP/." "$DIR/site/"
chown -R www-data:www-data "$DIR/site" 2>/dev/null || true
echo "$(date '+%F %T') сайт пересобран"
