# AI Hook: Log Diagnosis

Use when the user asks to inspect logs, errors, crashes, or runtime behavior.

1. Read the newest `logs\bot.log` entries first.
2. Lead with the newest blocking error, not old historical warnings.
3. Separate current blockers from older resolved warnings.
4. For OpenCV `!buf.empty()`, check ADB screenshot emptiness and LDPlayer state.
5. For `127.0.0.1:5555` refusal, check whether LDPlayer ADB is started and whether recovery waited long enough.
6. Use `.\tools\dev.ps1 ai-logscan -Tail 160` for the quick scan.
