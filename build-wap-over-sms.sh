#!/bin/bash
# Builds wap-over-sms for the Pi (linux/arm64) from the pinned upstream commit.
set -euo pipefail
cd "$(dirname "$0")"
COMMIT=aec01cc
[ -d vendor/wap-over-sms ] || git clone https://github.com/bevelgacom/wap-over-sms.git vendor/wap-over-sms
git -C vendor/wap-over-sms rev-parse --short HEAD | grep -q "^$COMMIT" || { echo "vendor/wap-over-sms is not at $COMMIT"; exit 1; }
(cd vendor/wap-over-sms && GOOS=linux GOARCH=arm64 CGO_ENABLED=0 go build -o ../../deploy/wap-over-sms ./cmd/wap-over-sms)
file deploy/wap-over-sms
