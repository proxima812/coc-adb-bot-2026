@echo off
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File ".\tools\dev.ps1" ui
