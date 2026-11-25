@echo off
start "Ollama Server" cmd /k "ollama serve"
start "LinkedIn Agent Backend" cmd /k "cd /d %~dp0backend && call conda activate env310tfgpu && python run.py"
start "LinkedIn Agent Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"
