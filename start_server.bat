@echo off
:: 如果存在 venv 虚拟环境，优先使用；否则使用系统全局 Python
if exist "%~dp0venv\Scripts\python.exe" (
    "%~dp0venv\Scripts\python.exe" "%~dp0hfss_mcp_server.py"
) else (
    python "%~dp0hfss_mcp_server.py"
)
pause