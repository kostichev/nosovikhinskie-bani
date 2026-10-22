#!/usr/bin/env bash
# Ставит/обновляет сервис заявок. Запускается из tick.sh и install.sh, повторный запуск безопасен.
set -u
DIR="/var/www/nosbani/deploy"
changed=0
if ! cmp -s "$DIR/lead.py" /usr/local/bin/nosbani-lead; then install -m 755 "$DIR/lead.py" /usr/local/bin/nosbani-lead; changed=1; fi
if ! cmp -s "$DIR/nosbani-lead.service" /etc/systemd/system/nosbani-lead.service; then
  install -m 644 "$DIR/nosbani-lead.service" /etc/systemd/system/nosbani-lead.service; systemctl daemon-reload; systemctl enable -q nosbani-lead; changed=1
fi
# корневой сертификат Минцифры — нужен для API мессенджера MAX
if [ ! -f /usr/local/share/ca-certificates/russian_trusted_root_ca.crt ]; then
  curl -fsS -m 20 https://gu-st.ru/content/lending/russian_trusted_root_ca_pem.crt -o /tmp/rtr.crt \
    && install -m 644 /tmp/rtr.crt /usr/local/share/ca-certificates/russian_trusted_root_ca.crt \
    && curl -fsS -m 20 https://gu-st.ru/content/lending/russian_trusted_sub_ca_pem.crt -o /tmp/rts.crt \
    && install -m 644 /tmp/rts.crt /usr/local/share/ca-certificates/russian_trusted_sub_ca.crt \
    && update-ca-certificates >/dev/null 2>&1 && changed=1
fi
if [ "$changed" = 1 ] || ! systemctl is-active -q nosbani-lead; then systemctl restart nosbani-lead && echo "$(date '+%F %T') сервис заявок обновлён"; fi
