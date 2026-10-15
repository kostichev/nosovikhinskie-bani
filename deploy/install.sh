#!/usr/bin/env bash
# Установка сайта «Носовихинские бани» на сервер (Ubuntu/Debian, запускать от root).
# Повторный запуск безопасен: другие сайты на сервере не трогает.
set -euo pipefail

DOMAIN="xn----8sbccpraaeo3adgda1cf3e.xn--p1ai"     # носовихинские-бани.рф
REPO="https://github.com/kostichev/nosovikhinskie-bani.git"
BRANCH="server"
DIR="/var/www/nosbani"

say() { printf '\n\033[1;32m▶ %s\033[0m\n' "$*"; }
die() { printf '\n\033[1;31m✖ %s\033[0m\n' "$*"; exit 1; }

[ "$(id -u)" = 0 ] || die "Запустите от root (или через sudo)."
command -v apt-get >/dev/null || die "Нужен Ubuntu или Debian."

# Порт 80 должен обслуживать nginx, а не другой веб-сервер
if command -v ss >/dev/null && ss -ltnp 2>/dev/null | grep -E ':80\s' | grep -vq nginx; then
  ss -ltnp | grep -E ':80\s' || true
  die "Порт 80 занят не nginx (см. строку выше). Пришлите этот вывод разработчику — настроим вручную."
fi

say "Ставлю nginx, git и certbot (если их ещё нет)"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq nginx git certbot python3-certbot-nginx dnsutils curl >/dev/null

say "Скачиваю сайт в $DIR"
if [ -d "$DIR/.git" ]; then
  git -C "$DIR" fetch -q --depth 1 origin "$BRANCH" && git -C "$DIR" reset -q --hard "origin/$BRANCH"
else
  rm -rf "$DIR"
  git clone -q --depth 1 -b "$BRANCH" "$REPO" "$DIR"
fi
chown -R www-data:www-data "$DIR/site" 2>/dev/null || true

say "Настраиваю nginx"
install -m 644 "$DIR/deploy/nosbani-common.conf" /etc/nginx/snippets/nosbani-common.conf
if [ ! -f /etc/nginx/sites-available/nosbani.conf ] || ! grep -q "ssl_certificate" /etc/nginx/sites-available/nosbani.conf; then
  install -m 644 "$DIR/deploy/nginx.conf" /etc/nginx/sites-available/nosbani.conf   # не затираем, если SSL уже выпущен
fi
ln -sf /etc/nginx/sites-available/nosbani.conf /etc/nginx/sites-enabled/nosbani.conf
if ! nginx -t; then rm -f /etc/nginx/sites-enabled/nosbani.conf; die "Ошибка в настройках nginx — наш сайт отключён обратно, другие сайты работают как прежде. Пришлите вывод выше разработчику."; fi
systemctl reload nginx || systemctl restart nginx

# Порт предпросмотра в фаерволе
if command -v ufw >/dev/null && ufw status | grep -q "Status: active"; then
  ufw allow 80/tcp >/dev/null; ufw allow 443/tcp >/dev/null; ufw allow 8088/tcp >/dev/null
fi

say "Включаю автообновление (каждые 5 минут) и автоматический SSL"
install -m 755 "$DIR/deploy/tick.sh" /usr/local/bin/nosbani-tick
echo "*/5 * * * * root /usr/local/bin/nosbani-tick >> /var/log/nosbani.log 2>&1" > /etc/cron.d/nosbani
chmod 644 /etc/cron.d/nosbani
/usr/local/bin/nosbani-tick || true

IP=$(curl -s4 -m 8 https://ifconfig.me || hostname -I | awk '{print $1}')
say "Готово!"
echo "  Предпросмотр сейчас:  http://$IP:8088/"
echo "  IP сервера для DNS:   $IP"
echo "  Когда A-записи носовихинские-бани.рф и www укажут на $IP — сайт и HTTPS включатся сами в течение ~5–10 минут."
