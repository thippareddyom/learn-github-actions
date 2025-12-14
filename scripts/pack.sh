#!/usr/bin/env bash
set -euo pipefail
rm -rf dist
mkdir -p dist/web dist/service
( cd ark_list_web_app && npm ci && npm run build && cp -r dist/* ../dist/web/ )
( cd ark_list_web_service && pip install -r requirements.txt && cp -r . ../dist/service )
rm -f dist/service/data/models/tiny-llm.gguf || true
pip freeze > dist/service/requirements.lock.txt
echo "Pack complete: dist/"
