# Tools

```powershell
.\tools\dev.ps1 check
.\tools\dev.ps1 doctor
.\tools\dev.ps1 logs -Tail 120
.\tools\dev.ps1 run
.\tools\dev.ps1 ai-preflight
.\tools\dev.ps1 ai-postedit
.\tools\dev.ps1 ai-logscan
```

`check` compiles Python files and validates config loading.
`doctor` checks ADB connection, device status, and screen size.
`logs` prints the log tail plus recent warnings/errors.
`ai-preflight`, `ai-postedit`, and `ai-logscan` are project-local AI hook commands for agents.
