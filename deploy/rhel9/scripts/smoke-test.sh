#!/usr/bin/env bash
set -euo pipefail

API_BASE="${API_BASE:-http://127.0.0.1:8000}"
WEB_BASE="${WEB_BASE:-http://127.0.0.1:3000}"
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
import urllib.request
import uuid

api_base = "${API_BASE}"
web_base = "${WEB_BASE}"

def get(url):
    return urllib.request.urlopen(url, timeout=30).read()

def post_json(url, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    return json.loads(urllib.request.urlopen(req, timeout=30).read().decode("utf-8"))

health = json.loads(get(api_base + "/api/health").decode("utf-8"))
get(web_base)

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
