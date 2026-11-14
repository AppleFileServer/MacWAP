#!/bin/bash
# Installs the WAP gateway on the Pi. Run ON THE PI, as root, from the
# directory holding these files:
#
#   sudo ./install.sh base                  Kannel (WAP only) + page server
#   sudo ./install.sh enable-sms HAT PHONE  add the SMS side (HAT fitted).
#       HAT   = the HAT SIM's number, e.g. +447700900123
#       PHONE = the one phone allowed to use the gateway, same format
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
    install -m 755 wapserver.py wapfetch.py wap-over-sms /opt/wapgateway/
    # The decks are written by wapfetch (user wapgw). www/ holds only a
    # fallback home deck for a Pi with no settings yet.
    [ -e /srv/wap/index.wml ] || cp -r www/. /srv/wap/
    chown -R wapgw: /srv/wap
    install -m 644 wapserver.service wap-over-sms.service wapfetch.service wapfetch.timer /etc/systemd/system/
    if [ ! -e /etc/wapgateway/services.conf ]; then
        install -m 640 -g wapgw services.conf.example /etc/wapgateway/services.conf
        echo "NOTE: edit /etc/wapgateway/services.conf (places for the weather)"
    fi

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
    systemctl enable --now wapfetch.timer
    systemctl start wapfetch.service || echo "wapfetch failed; see: journalctl -u wapfetch"
    systemctl restart kannel
    echo "base install done"
    ;;
enable-sms)
    NUMBER="${2:?give the HAT SIM number, e.g. +447700900123}"
    PHONE="${3:?give the phone number allowed to use the gateway, e.g. +447700900456}"
    case "$NUMBER$PHONE" in *[!+0-9]*) echo "numbers: digits with a leading + only" >&2; exit 1 ;; esac
    # Accept the phone's number however the network presents it:
    # +44..., 44..., 0044..., and for UK numbers the national 0... form.
    DIGITS="${PHONE#+}"
    ALLOWED="^([+]|00)?${DIGITS}\$"
    case "$DIGITS" in 44*) ALLOWED="$ALLOWED|^0${DIGITS#44}\$" ;; esac
    TOKEN=$(rand); PASS=$(rand)
    sed -e "s/@MODEM_NUMBER@/$NUMBER/" -e "s/@SENDSMS_PASSWORD@/$PASS/" -e "s/@TOKEN@/$TOKEN/" \
        -e "s#@ALLOWED_REGEX@#$ALLOWED#" \
        sms.conf.hat > /etc/kannel/sms.conf
    chown kannel:root /etc/kannel/sms.conf; chmod 600 /etc/kannel/sms.conf
    sed -i 's/^#smsbox-port/smsbox-port/' /etc/kannel/kannel.conf
    # A kannel.conf written by an older "base" has no allow-list line yet.
    grep -q 'white-list-sender-regex' /etc/kannel/kannel.conf || \
        sed -i '/^#\?smsbox-port/a #white-list-sender-regex = ""' /etc/kannel/kannel.conf
    sed -i "s#^\#\?white-list-sender-regex = .*#white-list-sender-regex = \"$ALLOWED\"#" /etc/kannel/kannel.conf
    grep -q '^white-list-sender-regex = "^' /etc/kannel/kannel.conf || { echo 'allow-list not set in kannel.conf; stopping' >&2; exit 1; }
    umask 077
    printf 'MODEM_NUMBER=%s\nSENDSMS_PASSWORD=%s\nTOKEN=%s\n' "$NUMBER" "$PASS" "$TOKEN" > /etc/wapgateway/sms.env
    chown root:root /etc/wapgateway/sms.env
    if [ -e /etc/default/kannel ]; then
        # The modem's serial port belongs to group dialout.
        usermod -aG dialout kannel
        sed -i 's/^#\?START_SMSBOX=.*/START_SMSBOX=1/' /etc/default/kannel
        grep -q '^START_SMSBOX=1' /etc/default/kannel || echo 'START_SMSBOX=1' >> /etc/default/kannel
    fi
    systemctl restart kannel
    systemctl enable --now wap-over-sms.service
    echo "SMS side enabled for $NUMBER; accepting texts from $PHONE only"
    ;;
*)
    sed -n '2,11p' "$0"; exit 1 ;;
esac
