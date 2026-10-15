#!/usr/bin/env bash
# Запускается cron'ом каждые 5 минут: подтягивает свежую версию сайта и,
# как только домен смотрит на этот сервер, выпускает бесплатный SSL (Let's Encrypt).
set -u
DOMAIN="xn----8sbccpraaeo3adgda1cf3e.xn--p1ai"
DIR="/var/www/nosbani"
STAMP="/var/lib/nosbani-ssl-try"

# 1. обновление сайта из ветки server
OLD=$(git -C "$DIR" rev-parse HEAD 2>/dev/null)
git -C "$DIR" fetch -q --depth 1 origin server && git -C "$DIR" reset -q --hard origin/server
NEW=$(git -C "$DIR" rev-parse HEAD 2>/dev/null)
if [ "$OLD" != "$NEW" ]; then
  chown -R www-data:www-data "$DIR/site" 2>/dev/null
  install -m 644 "$DIR/deploy/nosbani-common.conf" /etc/nginx/snippets/nosbani-common.conf
  install -m 755 "$DIR/deploy/tick.sh" /usr/local/bin/nosbani-tick
  nginx -t -q && systemctl reload nginx
  echo "$(date '+%F %T') обновлено до ${NEW:0:7}"
fi

# 2. SSL — когда DNS уже переключён
[ -d "/etc/letsencrypt/live/$DOMAIN" ] && exit 0
# не чаще раза в час, чтобы не упереться в лимиты Let's Encrypt
if [ -f "$STAMP" ] && [ $(( $(date +%s) - $(stat -c %Y "$STAMP") )) -lt 3600 ]; then exit 0; fi

MYIP=$(curl -s4 -m 8 https://ifconfig.me || true)
ALL="$MYIP $(hostname -I 2>/dev/null)"
A=$(dig +short A "$DOMAIN" @1.1.1.1 | tail -1)
W=$(dig +short A "www.$DOMAIN" @1.1.1.1 | tail -1)
[ -n "$A" ] && echo "$ALL" | grep -qw "$A" || exit 0   # домен ещё смотрит на Тильду

touch "$STAMP"
ARGS=(-d "$DOMAIN")
[ -n "$W" ] && echo "$ALL" | grep -qw "$W" && ARGS+=(-d "www.$DOMAIN")
if certbot --nginx "${ARGS[@]}" --redirect --non-interactive --agree-tos --register-unsafely-without-email; then
  echo "$(date '+%F %T') SSL выпущен: ${ARGS[*]}"
else
  echo "$(date '+%F %T') SSL пока не вышел, повторю через час"
fi
