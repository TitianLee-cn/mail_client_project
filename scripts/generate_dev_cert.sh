#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cert_dir="$project_root/certs"
mkdir -p "$cert_dir"

openssl req -x509 -newkey rsa:3072 -sha256 -nodes \
  -keyout "$cert_dir/mailapp-key.pem" \
  -out "$cert_dir/mailapp-cert.pem" \
  -days 3650 \
  -subj "/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"

chmod 600 "$cert_dir/mailapp-key.pem"
printf 'Created %s and %s\n' \
  "$cert_dir/mailapp-cert.pem" "$cert_dir/mailapp-key.pem"
