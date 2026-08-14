#!/usr/bin/env bash
# Edit Once — scripted E2E (PRD 9.3, AC-8): start app, upload fixture,
# poll to done, assert 4 versions + downloads, print the checklist table.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${PORT:-8000}"
BASE="http://localhost:$PORT"
FIXTURE="$ROOT/backend/tests/fixtures/fixture.mp4"
SRT="$ROOT/backend/tests/fixtures/fixture.srt"
WORK="$(mktemp -d)"
PID=""

cleanup() {
  if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then kill "$PID" 2>/dev/null || true; fi
  rm -rf "$WORK"
}
trap cleanup EXIT

echo "==> starting server on :$PORT"
(cd "$ROOT/backend" && exec "$ROOT/.venv/bin/uvicorn" app.main:app --port "$PORT" >"$WORK/server.log" 2>&1) &
PID=$!

for i in $(seq 1 60); do
  curl -sf "$BASE/api/health" >/dev/null 2>&1 && break
  sleep 0.5
done
curl -sf "$BASE/api/health" >/dev/null || { echo "server failed to start"; cat "$WORK/server.log"; exit 1; }
echo "==> server up; uploading fixture ($(du -h "$FIXTURE" | cut -f1))"

RESP="$(curl -sf -F "video=@$FIXTURE" -F "srt=@$SRT" "$BASE/api/jobs")"
JOB_ID="$(echo "$RESP" | "$ROOT/.venv/bin/python" -c 'import json,sys; print(json.load(sys.stdin)["job_id"])')"
echo "==> job $JOB_ID; polling…"

STATE="$WORK/state.json"
for i in $(seq 1 600); do  # up to 10 min
  curl -sf "$BASE/api/jobs/$JOB_ID" -o "$STATE"
  STATUS="$("$ROOT/.venv/bin/python" -c 'import json,sys; print(json.load(open(sys.argv[1]))["status"])' "$STATE")"
  case "$STATUS" in
    done|failed) break ;;
  esac
  sleep 1
done

echo "==> final job status: $STATUS"
"$ROOT/.venv/bin/python" - "$STATE" "$BASE" <<'EOF'
import json, sys, urllib.request

state = json.load(open(sys.argv[1]))
base = sys.argv[2]
failures = 0

order = ["tiktok", "reels", "shorts", "x"]
print(f"{'platform':<8} {'status':<9} {'checks':<5} details")
print("-" * 72)
for pid in order:
    v = state["versions"][pid]
    line = f"{pid:<8} {v['status']:<9}"
    if v["status"] == "done":
        levels = " ".join(f"{c['name'][:3]}={c['result'][0].upper()}" for c in v["checks"])
        ok = all(c["result"] != "fail" for c in v["checks"])
        if not ok:
            failures += 1
        line += f"{len(v['checks']):<5} {levels}"
        # download check
        url = base + v["download_url"]
        data = urllib.request.urlopen(url).read()
        is_mp4 = data[4:8] == b"ftyp" or data[:4] == b"\x00\x00\x00"
        line += f"  dl={len(data)//1024}KB {'OK' if is_mp4 and len(data) > 1024 else 'FAIL'}"
        if not (is_mp4 and len(data) > 1024):
            failures += 1
    else:
        failures += 1
        line += v.get("error", "")[:80]
    print(line)

print("-" * 72)
if failures:
    print(f"RESULT: FAIL ({failures} issue(s))")
    sys.exit(1)
print("RESULT: PASS — 4 platform-correct MP4s, downloads verified")
EOF