#!/usr/bin/env bash
# Ставит/обновляет сервис заявок. Запускается из tick.sh и install.sh, повторный запуск безопасен.
set -u
DIR="/var/www/nosbani/deploy"
changed=0
if ! cmp -s "$DIR/lead.py" /usr/local/bin/nosbani-lead; then install -m 755 "$DIR/lead.py" /usr/local/bin/nosbani-lead; changed=1; fi
if ! cmp -s "$DIR/nosbani-lead.service" /etc/systemd/system/nosbani-lead.service; then
  install -m 644 "$DIR/nosbani-lead.service" /etc/systemd/system/nosbani-lead.service; systemctl daemon-reload; systemctl enable -q nosbani-lead; changed=1
fi
# админка сайта и пересборка
mkdir -p /usr/local/lib/nosbani
for f in admin.py admin.html; do if ! cmp -s "$DIR/$f" /usr/local/lib/nosbani/$f; then install -m 755 "$DIR/$f" /usr/local/lib/nosbani/$f; achanged=1; fi; done
ln -sf /usr/local/lib/nosbani/admin.py /usr/local/bin/nosbani-admin
install -m 755 "$DIR/rebuild.sh" /usr/local/bin/nosbani-rebuild
if [ ! -f /etc/nosbani/site.env ]; then mkdir -p /etc/nosbani; printf 'SITE=https://xn----8sbccpraaeo3adgda1cf3e.xn--p1ai/\nINDEX=1\nLEAD_API=/api/lead\n' > /etc/nosbani/site.env; fi
if ! cmp -s "$DIR/nosbani-admin.service" /etc/systemd/system/nosbani-admin.service; then
  install -m 644 "$DIR/nosbani-admin.service" /etc/systemd/system/nosbani-admin.service; systemctl daemon-reload; systemctl enable -q nosbani-admin; achanged=1
fi
if [ "${achanged:-0}" = 1 ] || ! systemctl is-active -q nosbani-admin; then systemctl restart nosbani-admin && echo "$(date '+%F %T') админка обновлена"; fi

# корневой сертификат Минцифры — нужен для API мессенджера MAX
if [ ! -f /usr/local/share/ca-certificates/russian_trusted_root_ca.crt ]; then
  curl -fsS -m 20 https://gu-st.ru/content/lending/russian_trusted_root_ca_pem.crt -o /tmp/rtr.crt \
    && install -m 644 /tmp/rtr.crt /usr/local/share/ca-certificates/russian_trusted_root_ca.crt \
    && curl -fsS -m 20 https://gu-st.ru/content/lending/russian_trusted_sub_ca_pem.crt -o /tmp/rts.crt \
    && install -m 644 /tmp/rts.crt /usr/local/share/ca-certificates/russian_trusted_sub_ca.crt \
    && update-ca-certificates >/dev/null 2>&1 && changed=1
fi
if [ "$changed" = 1 ] || ! systemctl is-active -q nosbani-lead; then systemctl restart nosbani-lead && echo "$(date '+%F %T') сервис заявок обновлён"; fi
