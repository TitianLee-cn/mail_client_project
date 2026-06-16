#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$project_root"

if [ ! -f certs/mailapp-cert.pem ] || [ ! -f certs/mailapp-key.pem ]; then
  bash scripts/generate_dev_cert.sh
fi

python run_demo.py
