"""
Sandbox Process Runner for FreeCAD & C-Extension Exporters.
Isolates dangerous C-API / OpenCASCADE / FreeCAD bindings into short-lived subprocesses.
Guarantees memory recovery, prevents main-process crashes (Segfaults), and enforces hard timeouts.
"""
import subprocess
import json
import sys
import os
import tempfile
from typing import Dict, Any, Optional

class SandboxExporterRunner:
    """
    Executes CAD export jobs in an isolated sub-process sandbox with timeout protection.
    """
    def __init__(self, timeout_seconds: float = 30.0, max_memory_mb: int = 1024):
        self.timeout_seconds = timeout_seconds
        self.max_memory_mb = max_memory_mb

    def run_isolated(self, script_path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Runs the specified exporter script inside an isolated python worker process.
        
        Args:
            script_path: Path to the worker exporter script.
            payload: JSON-serializable geometry data to be exported.
            
        Returns:
            Dictionary containing export status, output file paths, or error messages.
        """
        # Create a temporary payload file to safely pass data across process boundaries
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
            # Launch isolated worker
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False
            )

            if process.returncode != 0:
                return {
                    "success": False,
                    "error": f"Worker crashed with code {process.returncode}",
                    "stderr": process.stderr.strip()
                }

            # Read back generated result
            if os.path.exists(temp_out_path) and os.path.getsize(temp_out_path) > 0:
                with open(temp_out_path, "r", encoding="utf-8") as f:
                    result = json.load(f)
                    return result
            else:
                return {
                    "success": False,
                    "error": "Worker produced empty or missing output",
                    "stdout": process.stdout
                }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": f"Sandbox execution timed out ({self.timeout_seconds}s limit exceeded - possible FreeCAD C-API hang)"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Sandbox runner exception: {str(e)}"
            }
        finally:
            # Guaranteed cleanup of IPC temporary files
            for p in (temp_in_path, temp_out_path):
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except OSError:
                        pass
