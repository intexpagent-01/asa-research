#!/bin/bash
# Deploy the Ask endpoint (signal/ask_worker.js) to Cloudflare Workers. Run once, when the Operator has sent a
# scoped API token. Everything after that is the agent's own: the ADMIN_KEY and SALT below are generated here and
# stored only in ~/private/asa-ask.env (~/keys is the Operator’s read-only credential drop), so the wake-to-wake read path never touches a Cloudflare credential.
#
# Requires in ~/keys/cloudflare.env:  CF_ACCOUNT_ID=...   CF_API_TOKEN=...
# Token scope needed (nothing else):  Account | Workers Scripts | Edit
#                                     Account | Workers KV Storage | Edit
set -euo pipefail
NAME=asa-ask
HERE="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1090
set -a; . "$HOME/keys/cloudflare.env"; set +a
: "${CF_ACCOUNT_ID:?}" "${CF_API_TOKEN:?}"
API="https://api.cloudflare.com/client/v4/accounts/$CF_ACCOUNT_ID"
auth=(-H "authorization: Bearer $CF_API_TOKEN")
jqv() { python3 -c 'import json,sys;d=json.load(sys.stdin);sys.exit(0) if d.get("success") else sys.exit("cloudflare: "+json.dumps(d.get("errors")))' ; }

echo "1/5 KV namespace"
NS=$(curl -sS "${auth[@]}" "$API/storage/kv/namespaces?per_page=100" |
  python3 -c 'import json,sys;r=json.load(sys.stdin)["result"];print(next((n["id"] for n in r if n["title"]=="asa-ask"),""))')
if [ -z "$NS" ]; then
  NS=$(curl -sS -X POST "${auth[@]}" -H 'content-type: application/json' \
    --data '{"title":"asa-ask"}' "$API/storage/kv/namespaces" |
    python3 -c 'import json,sys;d=json.load(sys.stdin);print(d["result"]["id"] if d.get("success") else sys.exit(json.dumps(d.get("errors"))))')
fi
echo "    namespace $NS"

echo "2/5 secrets"
KEYFILE="$HOME/private/asa-ask.env"
if [ -f "$KEYFILE" ] && grep -q ASK_ADMIN_KEY "$KEYFILE"; then
  # shellcheck disable=SC1090
  set -a; . "$KEYFILE"; set +a
else
  ASK_ADMIN_KEY=$(head -c 32 /dev/urandom | base64 | tr -d '=+/' | cut -c1-40)
  ASK_SALT=$(head -c 32 /dev/urandom | base64 | tr -d '=+/' | cut -c1-40)
fi

echo "3/5 upload worker"
python3 - "$NS" "$ASK_ADMIN_KEY" "${ASK_SALT:-$ASK_ADMIN_KEY}" > /tmp/asa-ask-metadata.json <<'PY'
import json, sys
ns, admin, salt = sys.argv[1:4]
json.dump({"main_module": "ask_worker.js", "compatibility_date": "2025-01-01",
           "bindings": [{"type": "kv_namespace", "name": "ASKS", "namespace_id": ns},
                        {"type": "secret_text", "name": "ADMIN_KEY", "text": admin},
                        {"type": "secret_text", "name": "SALT", "text": salt}]}, sys.stdout)
PY
curl -sS -X PUT "${auth[@]}" \
  -F "metadata=@/tmp/asa-ask-metadata.json;type=application/json" \
  -F "ask_worker.js=@$HERE/ask_worker.js;type=application/javascript+module" \
  "$API/workers/scripts/$NAME" | jqv
rm -f /tmp/asa-ask-metadata.json

echo "4/5 enable workers.dev route"
curl -sS -X POST "${auth[@]}" -H 'content-type: application/json' --data '{"enabled":true}' \
  "$API/workers/scripts/$NAME/subdomain" | jqv
SUB=$(curl -sS "${auth[@]}" "$API/workers/subdomain" |
  python3 -c 'import json,sys;print(json.load(sys.stdin)["result"]["subdomain"])')
ENDPOINT="https://$NAME.$SUB.workers.dev"

echo "5/5 store the agent's own key"
umask 077
cat > "$KEYFILE" <<EOF
ASK_ENDPOINT=$ENDPOINT
ASK_ADMIN_KEY=$ASK_ADMIN_KEY
ASK_SALT=${ASK_SALT:-$ASK_ADMIN_KEY}
EOF
chmod 600 "$KEYFILE"

echo
echo "Endpoint: $ENDPOINT"
echo "Smoke test:"
curl -sS -X POST -H 'content-type: application/json' -H 'origin: https://pacificaidsignal.org' \
  --data '{"text":"deployment smoke test from the agent","kind":"feedback","country":""}' "$ENDPOINT"; echo
echo
echo "Then: export SIGNAL_ASK_ENDPOINT=$ENDPOINT  and re-render, and add it to the wake environment."
