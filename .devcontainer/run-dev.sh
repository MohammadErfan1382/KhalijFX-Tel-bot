#!/bin/bash
# اجرای ربات + celery در tmux (چند پنجره موازی)

set -e

# بررسی tmux
if ! command -v tmux &>/dev/null; then
    sudo apt-get install -y tmux -q
fi

SESSION="exchange-bot"

# اگه session قبلی هست kill کن
tmux kill-session -t $SESSION 2>/dev/null || true

echo "راه‌اندازی محیط توسعه..."

tmux new-session -d -s $SESSION -x 220 -y 50

# ── پنجره ۱: ربات ─────────────────────────────────────────
tmux rename-window -t $SESSION:0 "bot"
tmux send-keys -t $SESSION:0 "source .venv/bin/activate && python -m app.main" Enter

# ── پنجره ۲: Celery Worker ────────────────────────────────
tmux new-window -t $SESSION -n "worker"
tmux send-keys -t $SESSION:1 "source .venv/bin/activate && celery -A app.tasks.celery_app worker --loglevel=info --concurrency=2" Enter

# ── پنجره ۳: Celery Beat ──────────────────────────────────
tmux new-window -t $SESSION -n "beat"
tmux send-keys -t $SESSION:2 "source .venv/bin/activate && celery -A app.tasks.celery_app beat --loglevel=info" Enter

# ── پنجره ۴: Shell آزاد ──────────────────────────────────
tmux new-window -t $SESSION -n "shell"
tmux send-keys -t $SESSION:3 "source .venv/bin/activate && echo 'Shell آماده'" Enter

# برگشت به پنجره ربات
tmux select-window -t $SESSION:0

echo ""
echo "tmux session شروع شد: $SESSION"
echo ""
echo "کلیدهای کاربردی:"
echo "  Ctrl+B, 0  ← پنجره ربات"
echo "  Ctrl+B, 1  ← پنجره worker"
echo "  Ctrl+B, 2  ← پنجره beat"
echo "  Ctrl+B, 3  ← shell"
echo "  Ctrl+B, d  ← detach (بدون توقف)"
echo ""

tmux attach-session -t $SESSION
