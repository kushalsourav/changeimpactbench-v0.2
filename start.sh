#!/usr/bin/env bash
set -e

PROJECT="$HOME/hackathons/changeimpactbench-v0.2"
SESSION="changeimpactbench"

cd "$PROJECT"

if ! command -v tmux >/dev/null 2>&1; then
  echo "tmux is not installed. Run: sudo apt install tmux"
  exit 1
fi

if tmux has-session -t "=$SESSION" 2>/dev/null; then
  exec tmux attach-session -t "$SESSION"
fi

tmux new-session -d -s "$SESSION" -n servers

# Left pane: FastAPI backend
tmux send-keys -t "$SESSION:servers.0" \
  "cd '$PROJECT' && source .venv/bin/activate && set -a && source .env && set +a && python -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000" C-m

# Right pane: Next.js frontend
tmux split-window -h -t "$SESSION:servers.0" \
  "cd '$PROJECT/web' && npm run dev"

tmux select-layout -t "$SESSION:servers" even-horizontal
tmux select-pane -t "$SESSION:servers.0"

exec tmux attach-session -t "$SESSION"
