#!/bin/sh

STATUS=$(/sbin/apcaccess 2>&1)
UPSNAME=$(echo "$STATUS" | grep "^UPSNAME"  | cut -d: -f2- | xargs)
UPSMODEL=$(echo "$STATUS" | grep "^MODEL"   | cut -d: -f2- | xargs)
UPSSTATUS=$(echo "$STATUS" | grep "^STATUS"  | cut -d: -f2- | xargs)

case "$UPSSTATUS" in
  *ONLINE*)  COLOR="#4ade80" ;;
  *ONBATT*)  COLOR="#f87171" ;;
  *)         COLOR="#facc15" ;;
esac

TITLE="${UPSNAME:-UPS} - ${UPSMODEL:-APC}"

cat <<EOF
Content-Type: text/html

<!DOCTYPE html>
<html>
<head>
  <title>$TITLE</title>
  <meta http-equiv="refresh" content="30">
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0f172a; color: #e2e8f0; padding: 2rem; }
    h1 { font-size: 1.5rem; margin-bottom: 0.25rem; }
    .subtitle { color: #64748b; margin-bottom: 1.5rem; }
    .status-badge { display: inline-block; padding: 0.25rem 0.75rem; border-radius: 9999px; font-size: 0.875rem; font-weight: 600; background: ${COLOR}20; color: ${COLOR}; border: 1px solid ${COLOR}40; margin-bottom: 1.5rem; }
    table { width: 100%; max-width: 600px; border-collapse: collapse; }
    tr { border-bottom: 1px solid #1e293b; }
    td { padding: 0.5rem 0; }
    td:first-child { color: #64748b; width: 45%; }
  </style>
</head>
<body>
  <h1>$TITLE</h1>
  <p class="subtitle">apcupsd NIS &middot; auto-refresh 30s</p>
  <div class="status-badge">$UPSSTATUS</div>
  <table>
EOF

echo "$STATUS" | while IFS= read -r line; do
  key=$(echo "$line" | cut -d: -f1 | xargs)
  value=$(echo "$line" | cut -d: -f2- | xargs)
  [ -z "$key" ] && continue
  echo "    <tr><td>$key</td><td>$value</td></tr>"
done

cat <<'EOF'
  </table>
</body>
</html>
EOF
