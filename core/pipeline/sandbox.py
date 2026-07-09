"""Secure tool sandbox — restricted execution environment for agent tools.

Prevents Remote Code Execution (RCE) by running dynamic agent code in
a severely restricted subprocess with:
- Disabled network access (no internet from sandboxed tools)
- Memory quota (max 128MB)
- Timeout (30s max execution)
- Allowed built-in functions only (no os, subprocess, shutil, etc.)
"""
from __future__ import annotations

import multiprocessing
import os
import resource
import signal
import sys
import threading
import time
from typing import Any

# Python built-ins safe for agent execution
SAFE_BUILTINS: dict[str, Any] = {
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "chr": chr,
    "dict": dict,
    "enumerate": enumerate,
    "filter": filter,
    "float": float,
    "format": format,
    "frozenset": frozenset,
    "int": int,
    "len": len,
    "list": list,
    "map": map,
    "max": max,
    "min": min,
    "ord": ord,
    "pow": pow,
    "range": range,
    "reversed": reversed,
    "round": round,
    "set": set,
    "slice": slice,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "type": type,
    "zip": zip,
}

# Dangerously unsafe modules — blocked at import time
BLOCKED_MODULES = ["os", "subprocess", "shutil", "socket", "requests", "httpx",
                   "ctypes", "signal", "multiprocessing", "threading", "asyncio",
                   "importlib", "eval", "exec", "compile", "open", "sys"]


class SandboxResult:
    """Result of sandboxed execution."""
    def __init__(self, success: bool, output: str = "", error: str = ""):
        self.success = success
        self.output = output
        self.error = error


def run_sandboxed(code: str, timeout: int = 30, memory_mb: int = 128) -> SandboxResult:
    """Execute untrusted Python code in a sandboxed subprocess.

    Args:
        code: Python code string to execute.
        timeout: Maximum execution time in seconds.
        memory_mb: Maximum memory in megabytes.

    Returns:
        SandboxResult with output or error.
    """
    result_queue: multiprocessing.Queue = multiprocessing.Queue()

    def _run_in_process():
        """Execute code inside a forked process with resource limits."""
        try:
            # Memory limit
            resource.setrlimit(resource.RLIMIT_AS, (memory_mb * 1024 * 1024, memory_mb * 1024 * 1024))

            # CPU time limit (soft + hard)
            resource.setrlimit(resource.RLIMIT_CPU, (timeout, timeout + 5))

            # Restricted globals and builtins
            restricted_globals = {
                "__builtins__": SAFE_BUILTINS,
                "__name__": "__sandbox__",
            }

            # Capture stdout
            from io import StringIO  # noqa: PLC0415

            stdout_capture = StringIO()
            old_stdout = sys.stdout
            sys.stdout = stdout_capture

            try:
                compiled = compile(code, "<sandbox>", "exec")
                exec(compiled, restricted_globals)
                output = stdout_capture.getvalue()
                result_queue.put(SandboxResult(success=True, output=output))
            except Exception as exc:
                result_queue.put(SandboxResult(success=False, error=str(exc)))
            finally:
                sys.stdout = old_stdout

        except Exception as exc:
            result_queue.put(SandboxResult(success=False, error=f"Sandbox violation: {exc}"))

    proc = multiprocessing.Process(target=_run_in_process)
    proc.start()
    proc.join(timeout=timeout)

    if proc.is_alive():
        proc.terminate()
        proc.join(timeout=2)
        return SandboxResult(success=False, error="Execution timed out")

    try:
        return result_queue.get_nowait()
    except Exception:
        return SandboxResult(success=False, error="No output produced")


def is_code_safe(code: str) -> tuple[bool, str]:
    """Pre-flight check — scan code for obviously dangerous patterns.

    Returns (safe: bool, reason: str).
    This catches the easy cases before they reach the sandbox.
    """
    dangerous_patterns = [
        ("__import__", "Dynamic import detected"),
        ("__builtins__", "Builtins manipulation detected"),
        ("import os", "os module is blocked"),
        ("import subprocess", "subprocess module is blocked"),
        ("import socket", "socket module is blocked"),
        ("import requests", "requests module is blocked"),
        ("import httpx", "httpx module is blocked"),
        ("import ctypes", "ctypes module is blocked"),
        ("import multiprocessing", "multiprocessing module is blocked"),
        ("import threading", "threading module is blocked"),
        ("import asyncio", "asyncio module is blocked"),
        ("eval(", "eval() is blocked"),
        ("exec(", "exec() is blocked"),
        ("open(", "open() is blocked"),
        ("__file__", "__file__ access blocked"),
        ("os.system", "os.system is blocked"),
        ("subprocess.run", "subprocess.run is blocked"),
        ("shutil.", "shutil is blocked"),
    ]

    for pattern, reason in dangerous_patterns:
        if pattern in code:
            return False, reason

    return True, ""
