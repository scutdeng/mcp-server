#!/usr/bin/env python3
"""
ANSYS HFSS MCP Server - Enterprise Demo Version
Connects AI clients (e.g., Claude, Cursor) to ANSYS HFSS via PyAEDT.

[Architecture Highlights]
1. Protocol Isolation: Custom stdout forwarding prevents PyAEDT logs from corrupting the MCP JSON-RPC stream.
2. State Management: Robust session handling (idle/connecting/connected) to manage the AEDT gRPC connection lifecycle.
3. Async Background Jobs: Long-running simulation tasks (like automated antenna design) are offloaded to threads, allowing the AI to poll for status.
"""
from __future__ import annotations

import json
import sys as _sys
import threading
import time
import logging as _logging
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Protocol Isolation: Redirect PyAEDT logs to stderr to prevent stdout pollution
# ---------------------------------------------------------------------------
class _StderrForwarder:
    def __init__(self, real_stdout):
        self._out = real_stdout
        self._err = _sys.stderr
        self.buffer = real_stdout.buffer

    def write(self, data):
        # Only let JSON-RPC payloads (MCP protocol) through to stdout
        stripped = data.lstrip()
        if stripped.startswith(("{", "[")):
            self._out.write(data)
        else:
            self._err.write(data)

    def flush(self):
        self._out.flush()
        self._err.flush()

    def fileno(self):
        return self._out.fileno()

_sys.stdout = _StderrForwarder(_sys.stdout)

# Silence internal logging
for _name in ("pyaedt", "ansys", "root"):
    _log = _logging.getLogger(_name)
    _log.handlers = [_logging.StreamHandler(_sys.stderr)]
    _log.propagate = False

# ---------------------------------------------------------------------------
# Global State
# ---------------------------------------------------------------------------
_hfss = None
_status = "idle"   # "idle" | "connecting" | "connected" | "error"
_status_msg = ""
__version__ = "0.1.0-demo"

mcp = FastMCP("ansys-hfss-mcp")

# For tracking async jobs
_script_results: dict = {}
_job_counter = 0

# ---------------------------------------------------------------------------
# Connection Management
# ---------------------------------------------------------------------------
@mcp.tool()
def connect_to_hfss(port: int = 50051, project: str = "", design: str = "") -> str:
    """Connect to a running AEDT/HFSS session via gRPC."""
    global _hfss, _status, _status_msg

    if _status == "connecting":
        return json.dumps({"ok": True, "status": "connecting", "message": "Already connecting..."})

    _status = "connecting"
    
    def _do_connect():
        global _hfss, _status, _status_msg
        try:
            from ansys.aedt.core import Hfss
            h = Hfss(project=project or None, design=design or None, machine="localhost", port=port, close_on_exit=False)
            _hfss = h
            _status = "connected"
            _status_msg = f"{h.project_name} / {h.design_name}"
        except ImportError:
            _status = "error"
            _status_msg = "PyAEDT not installed. Run: pip install pyaedt"
        except Exception as e:
            _status = "error"
            _status_msg = str(e)

    threading.Thread(target=_do_connect, daemon=True).start()
    return json.dumps({"ok": True, "status": "connecting", "message": "Connection initiated in background."})

@mcp.tool()
def check_connection() -> str:
    """Check current AEDT connection status."""
    if _status == "connected" and _hfss:
        return json.dumps({"ok": True, "status": "connected", "project": _hfss.project_name})
    return json.dumps({"ok": False, "status": _status, "error": _status_msg})

# ---------------------------------------------------------------------------
# Geometry Abstraction
# ---------------------------------------------------------------------------
@mcp.tool()
def create_box(name: str, origin: list[float], dimensions: list[float], material: str = "vacuum") -> str:
    """Create a rectangular box primitive in HFSS."""
    if _status != "connected":
        return json.dumps({"ok": False, "error": "Not connected. Call connect_to_hfss first."})
    try:
        obj = _hfss.modeler.create_box(origin, dimensions, name=name, material=material)
        return json.dumps({"ok": True, "name": obj.name, "id": obj.id})
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)})

# ---------------------------------------------------------------------------
# Advanced Workflow (Demo Placeholder)
# ---------------------------------------------------------------------------
def _build_patch_antenna_task(job_id: str, freq_ghz: float):
    """Background worker thread for antenna design."""
    global _script_results
    _script_results[job_id] = {"status": "running", "output": "Initializing..."}
    
    try:
        # [商业逻辑隐藏] 
        # 这里的真实代码包含：Pozar公式计算、参数化变量绑定、多层介质基板创建、
        # 同轴探针与防短路隔离环设计、波端口积分线计算、自适应网格设置与扫频等。
        
        # 模拟耗时任务
        time.sleep(2) 
        _script_results[job_id] = {
            "status": "done", 
            "output": f"Successfully designed {freq_ghz} GHz patch antenna.\n(Full implementation hidden in demo)."
        }
    except Exception as e:
        _script_results[job_id] = {"status": "error", "output": str(e)}

@mcp.tool()
def design_patch_antenna(freq_ghz: float = 2.4) -> str:
    """Design a complete coax-fed microstrip patch antenna at any frequency."""
    if _status != "connected":
        return json.dumps({"ok": False, "error": "Not connected."})
        
    global _job_counter
    _job_counter += 1
    job_id = f"job_{_job_counter}"
    
    threading.Thread(target=_build_patch_antenna_task, args=(job_id, freq_ghz), daemon=True).start()
    return json.dumps({"ok": True, "job_id": job_id, "message": "Workflow started. Poll with get_script_result."})

@mcp.tool()
def get_script_result(job_id: str) -> str:
    """Get the output of a previously submitted background task."""
    if job_id not in _script_results:
        return json.dumps({"ok": False, "error": f"Unknown job_id '{job_id}'."})
    result = _script_results[job_id]
    return json.dumps({"ok": result["status"] == "done", "status": result["status"], "output": result["output"]})

def main() -> None:
    mcp.run()

if __name__ == "__main__":
    main()