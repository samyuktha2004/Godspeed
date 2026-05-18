#!/bin/bash
# Start GodSpeed backend and ngrok tunnel

# Kill any existing ngrok / uvicorn
pkill -f "ngrok http" 2>/dev/null
pkill -f "uvicorn" 2>/dev/null
sleep 1

echo "Starting ngrok..."
ngrok http 8000 --log=stdout > /tmp/ngrok.log 2>&1 &
NGROK_PID=$!

# Wait for ngrok to be ready
for i in $(seq 1 15); do
  NGROK_URL=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    for t in data.get('tunnels', []):
        if t.get('proto') == 'https':
            print(t['public_url'])
            break
except: pass
" 2>/dev/null)
  [ -n "$NGROK_URL" ] && break
  sleep 1
done

if [ -z "$NGROK_URL" ]; then
  echo "ERROR: Could not get ngrok URL. Is ngrok authenticated? Run: ngrok config add-authtoken <token>"
  kill $NGROK_PID 2>/dev/null
  exit 1
fi

echo "Starting backend with FRONTEND_URL=$NGROK_URL ..."
FRONTEND_URL=$NGROK_URL .venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

sleep 2

echo ""
echo "========================================="
echo "  GodSpeed is live at: $NGROK_URL"
echo "  Share this URL with your friends!"
echo "========================================="
echo ""
echo "Press Ctrl+C to stop everything"

trap "kill $BACKEND_PID $NGROK_PID 2>/dev/null; exit" INT
wait
