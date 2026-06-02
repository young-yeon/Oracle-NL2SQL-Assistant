#!/usr/bin/env bash
set -euo pipefail

API_BASE="${API_BASE:-http://127.0.0.1:8000}"
WEB_BASE="${WEB_BASE:-${API_BASE}}"
SMOKE_TEST_TIMEOUT_SECONDS="${SMOKE_TEST_TIMEOUT_SECONDS:-90}"
SMOKE_TEST_RETRY_INTERVAL_SECONDS="${SMOKE_TEST_RETRY_INTERVAL_SECONDS:-2}"
if [[ -n "${PYTHON_BIN:-}" ]]; then
  :
elif command -v python3.12 >/dev/null; then
  PYTHON_BIN="python3.12"
else
  echo "python3.12 is required for smoke tests." >&2
  exit 1
fi

"${PYTHON_BIN}" - <<PY
import json
import sys
import time
import urllib.request
import uuid

api_base = "${API_BASE}"
web_base = "${WEB_BASE}"
timeout_seconds = int("${SMOKE_TEST_TIMEOUT_SECONDS}")
retry_interval_seconds = float("${SMOKE_TEST_RETRY_INTERVAL_SECONDS}")

def get(url, timeout=30):
    return urllib.request.urlopen(url, timeout=timeout).read()

def wait_for_bytes(url, label):
    deadline = time.monotonic() + timeout_seconds
    last_error = None
    while True:
        try:
            return get(url, timeout=5)
        except Exception as exc:
            last_error = exc
            if time.monotonic() >= deadline:
                raise RuntimeError(
                    f"{label} did not become ready within {timeout_seconds}s: {last_error}"
                ) from exc
            time.sleep(retry_interval_seconds)

def wait_for_json(url, label):
    return json.loads(wait_for_bytes(url, label).decode("utf-8"))

def post_json(url, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    return json.loads(urllib.request.urlopen(req, timeout=30).read().decode("utf-8"))

health = wait_for_json(api_base + "/api/health", "API health endpoint")
wait_for_bytes(web_base, "Web endpoint")

template = get(api_base + "/api/metadata/template")
boundary = "----oracle-nl2sql-" + uuid.uuid4().hex
body = b"".join([
    ("--" + boundary + "\\r\\n").encode(),
    b"Content-Disposition: form-data; name=\\"file\\"; filename=\\"template.xlsx\\"\\r\\n",
    b"Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet\\r\\n\\r\\n",
    template,
    b"\\r\\n",
    ("--" + boundary + "--\\r\\n").encode(),
])
upload_req = urllib.request.Request(
    api_base + "/api/metadata/upload",
    data=body,
    headers={"Content-Type": "multipart/form-data; boundary=" + boundary},
    method="POST",
)
upload = json.loads(urllib.request.urlopen(upload_req, timeout=30).read().decode("utf-8"))
preview = post_json(api_base + "/api/sql/preview", {"message": "show revenue"})
blocked = post_json(api_base + "/api/sql/preview", {"message": "delete all sales rows"})

ok = (
    health["status"] == "ok"
    and upload["errors"] == []
    and preview["validation"]["is_safe"] is True
    and blocked["sql"] is None
)
print(json.dumps({
    "health": health,
    "upload": upload,
    "preview_sql": preview["sql"],
    "blocked_answer": blocked["answer"],
    "ok": ok,
}, indent=2))
sys.exit(0 if ok else 1)
PY
