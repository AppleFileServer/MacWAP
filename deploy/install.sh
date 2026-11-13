#!/bin/bash
# Installs the WAP gateway on the Pi. Run ON THE PI, as root, from the
# directory holding these files:
#
#   sudo ./install.sh base                  Kannel (WAP only) + page server
#   sudo ./install.sh enable-sms +447...    add the SMS side (HAT fitted;
#                                           argument = the HAT SIM's number)
#
# "base" changes nothing about the Pi's serial port and starts no modem.
set -euo pipefail
cd "$(dirname "$0")"

rand() { openssl rand -hex 16; }

case "${1:-}" in
base)
    apt-get update
    apt-get install -y kannel
    id wapgw >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin wapgw

    install -d /opt/wapgateway /srv/wap /etc/wapgateway
    install -m 755 wapserver.py wap-over-sms /opt/wapgateway/
    cp -r www/. /srv/wap/
    install -m 644 wapserver.service wap-over-sms.service /etc/systemd/system/

    # Keep the packaged configuration the first time only.
    [ -e /etc/kannel/kannel.conf.dist ] || cp /etc/kannel/kannel.conf /etc/kannel/kannel.conf.dist
    ADMIN=$(rand)
    sed "s/@ADMIN_PASSWORD@/$ADMIN/" kannel.conf > /etc/kannel/kannel.conf
    [ -e /etc/kannel/sms.conf ] || : > /etc/kannel/sms.conf
    # Keep the SMS side on if it was already enabled.
    [ -s /etc/kannel/sms.conf ] && sed -i 's/^#smsbox-port/smsbox-port/' /etc/kannel/kannel.conf
    # Kannel runs as user "kannel" with no group of its own, so the files
    # belong to that user and nobody else can read them.
    chown kannel:root /etc/kannel/kannel.conf /etc/kannel/sms.conf
    chmod 600 /etc/kannel/kannel.conf /etc/kannel/sms.conf

    # Debian starts the wapbox only when asked to.
    if [ -e /etc/default/kannel ]; then
        sed -i 's/^#\?START_WAPBOX=.*/START_WAPBOX=1/' /etc/default/kannel
        grep -q '^START_WAPBOX=1' /etc/default/kannel || echo 'START_WAPBOX=1' >> /etc/default/kannel
    fi

    systemctl daemon-reload
    systemctl enable --now wapserver.service
    systemctl restart kannel
    echo "base install done"
    ;;
enable-sms)
    NUMBER="${2:?give the HAT SIM number, e.g. +447700900123}"
    TOKEN=$(rand); PASS=$(rand)
    sed -e "s/@MODEM_NUMBER@/$NUMBER/" -e "s/@SENDSMS_PASSWORD@/$PASS/" -e "s/@TOKEN@/$TOKEN/" \
        sms.conf.hat > /etc/kannel/sms.conf
    chown kannel:root /etc/kannel/sms.conf; chmod 600 /etc/kannel/sms.conf
    sed -i 's/^#smsbox-port/smsbox-port/' /etc/kannel/kannel.conf
    umask 077
    printf 'MODEM_NUMBER=%s\nSENDSMS_PASSWORD=%s\nTOKEN=%s\n' "$NUMBER" "$PASS" "$TOKEN" > /etc/wapgateway/sms.env
    chown root:root /etc/wapgateway/sms.env
    if [ -e /etc/default/kannel ]; then
        sed -i 's/^#\?START_SMSBOX=.*/START_SMSBOX=1/' /etc/default/kannel
        grep -q '^START_SMSBOX=1' /etc/default/kannel || echo 'START_SMSBOX=1' >> /etc/default/kannel
    fi
    systemctl restart kannel
    systemctl enable --now wap-over-sms.service
    echo "SMS side enabled for $NUMBER"
    ;;
*)
    sed -n '2,10p' "$0"; exit 1 ;;
esac
