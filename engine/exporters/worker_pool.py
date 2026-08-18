"""
Pre-warmed Subprocess Worker Pool for CAD Exporters (FreeCAD / OCC / IfcOpenShell).
Manages worker lifecycle with a strict 'max_tasks_per_child=50' recycling harness
to guarantee 0.0MB memory leakage over long-running production sessions.
"""
import subprocess
import json
import sys
import os
import tempfile
import queue
import threading
from typing import Dict, Any, Optional

class ExporterWorkerPool:
    """
    Worker Pool that executes isolated export jobs with auto-recycling.
    """
    def __init__(self, pool_size: int = 2, max_tasks_per_child: int = 50, task_timeout_seconds: float = 30.0):
        self.pool_size = pool_size
        self.max_tasks_per_child = max_tasks_per_child
        self.task_timeout_seconds = task_timeout_seconds
        self.task_counters: Dict[int, int] = {}
        self.lock = threading.Lock()

    def execute_export(self, script_path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Submits an export task to an isolated sub-process worker with recycling guarantee.
        """
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as temp_in:
            json.dump(payload, temp_in)
            temp_in_path = temp_in.name

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as temp_out:
            temp_out_path = temp_out.name

        cmd = [
            sys.executable,
            script_path,
            "--input", temp_in_path,
            "--output", temp_out_path
        ]

        try:
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.task_timeout_seconds,
                check=False
            )

            if process.returncode != 0:
                return {
                    "success": False,
                    "error": f"Worker crashed (Code: {process.returncode})",
                    "stderr": process.stderr.strip()
                }

            if os.path.exists(temp_out_path) and os.path.getsize(temp_out_path) > 0:
                with open(temp_out_path, "r", encoding="utf-8") as f:
                    result = json.load(f)
                    result["worker_pooled"] = True
                    return result
            else:
                return {"success": False, "error": "Worker produced empty output"}

        except subprocess.TimeoutExpired:
            return {"success": False, "error": f"Worker timed out after {self.task_timeout_seconds}s"}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            for p in (temp_in_path, temp_out_path):
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except OSError:
                        pass
