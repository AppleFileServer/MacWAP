#!/bin/bash
# Installs the WAP gateway on the Pi. Run ON THE PI, as root, from the
# directory holding these files:
#
#   sudo ./install.sh base                  Kannel (WAP only) + page server
#   sudo ./install.sh enable-sms HAT PHONE  add the SMS side (HAT fitted).
#       HAT   = the HAT SIM's number, e.g. +447700900123
#       PHONE = the one phone allowed to use the gateway, same format
#   sudo ./install.sh enable-mactrack [DIR]  mirror the calorie log to the
#       shared drive for MacTrack. DIR defaults to "/srv/macshare/MacTrack
#       Link"; the shared drive (the Pi-gateway side) must already exist.
#   sudo ./install.sh enable-gym FILE.wbmp   install a gym-entry QR image so
#       a "Gym" card shows on the menu. FILE is a 1-bit WBMP; it is an
#       access code, so it lives only on the Pi, never in the repository.
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
    install -m 644 wapapp.py /opt/wapgateway/
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
        sms.conf.hat > /etc/kannel/sms.conf
    chown kannel:root /etc/kannel/sms.conf; chmod 600 /etc/kannel/sms.conf
    sed -i 's/^#smsbox-port/smsbox-port/' /etc/kannel/kannel.conf
    # The allow-list is applied by wapsms.py (see its header), not by
    # Kannel, so that ordinary texts from other senders reach the inbox.
    sed -i '/white-list-sender-regex/d' /etc/kannel/kannel.conf
    install -m 755 wapsms.py /opt/wapgateway/
    install -m 644 smscmd.py /opt/wapgateway/
    install -m 644 wapsms.service wap-over-sms.service /etc/systemd/system/
    umask 077
    printf "MODEM_NUMBER=%s\nSENDSMS_PASSWORD=%s\nTOKEN=%s\nALLOWED='%s'\n" "$NUMBER" "$PASS" "$TOKEN" "$ALLOWED" > /etc/wapgateway/sms.env
    chown root:root /etc/wapgateway/sms.env
    if [ -e /etc/default/kannel ]; then
        # The modem's serial port belongs to group dialout.
        usermod -aG dialout kannel
        sed -i 's/^#\?START_SMSBOX=.*/START_SMSBOX=1/' /etc/default/kannel
        grep -q '^START_SMSBOX=1' /etc/default/kannel || echo 'START_SMSBOX=1' >> /etc/default/kannel
    fi
    systemctl daemon-reload
    systemctl enable wapsms.service wap-over-sms.service
    systemctl restart wapsms.service wap-over-sms.service
    systemctl restart kannel
    echo "SMS side enabled for $NUMBER; accepting texts from $PHONE only"
    ;;
enable-mactrack)
    DIR="${2:-/srv/macshare/MacTrack Link}"
    PARENT=$(dirname "$DIR")
    [ -d "$PARENT" ] || { echo "shared folder '$PARENT' not found; set up the Pi drive first" >&2; exit 1; }
    # Owned by the service user so it can write; world-readable so the FTP
    # and AppleTalk logins can fetch it. The file itself is 0644.
    install -d -o wapgw -g wapgw -m 755 "$DIR"
    CONF=/etc/wapgateway/services.conf
    [ -e "$CONF" ] || { echo "$CONF missing; run 'base' first" >&2; exit 1; }
    if grep -q '^[[:space:]]*feed_dir' "$CONF"; then
        # address uses /…/ (feed_dir has no slash), substitution uses #…#
        # (the path has slashes) — portable across GNU and BSD sed.
        sed -i "/^[[:space:]]*feed_dir/s#.*#feed_dir = $DIR#" "$CONF"
    else
        printf '\n[mactrack]\nfeed_dir = %s\n' "$DIR" >> "$CONF"
    fi
    chown root:wapgw "$CONF"; chmod 640 "$CONF"
    systemctl restart wapsms.service 2>/dev/null || echo "(enable the SMS side to start writing the feed)"
    echo "MacTrack feed -> $DIR"
    ;;
enable-gym)
    SRC="${2:?give the path to the gym QR .wbmp}"
    [ -f "$SRC" ] || { echo "file not found: $SRC" >&2; exit 1; }
    install -d -o wapgw -g wapgw -m 755 /srv/wap
    install -m 644 -o wapgw -g wapgw "$SRC" /srv/wap/gymqr.wbmp
    systemctl start wapfetch.service 2>/dev/null || true   # refresh the fallback menu
    echo "gym QR installed; a 'Gym' card now shows on the Today menu"
    ;;
*)
    sed -n '2,16p' "$0"; exit 1 ;;
esac
