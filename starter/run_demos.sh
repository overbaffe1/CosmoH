#!/usr/bin/env bash
# Поднимает оба демо локально: пожары на 8000, риск ВКД на 8001.
# Требуется: python3 + зависимости из requirements.txt каждого проекта.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "Запускаю КосмоФАЙР на http://127.0.0.1:8000 ..."
(cd "$ROOT/fires-krasnoyarsk" && python -m uvicorn cosmofire.service:app --host 0.0.0.0 --port 8000 &)

echo "Запускаю КосмоРиск на http://127.0.0.1:8001 ..."
(cd "$ROOT/orbital-risk-spb" && python -m uvicorn cosmorisk.service:app --host 0.0.0.0 --port 8001 &)

echo "Оба демо подняты. Ctrl+C останавливает только этот скрипт — гасите процессы через pkill -f uvicorn"
wait
