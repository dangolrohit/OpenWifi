#!/usr/bin/env python3
"""WiFiRouter V2 local development runner.
Starts the simulated network agent, FastAPI backend, and Vite frontend simultaneously.
"""
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent

def main():
    print("=" * 60)
    print("  WiFiRouter V2 — Development Environment")
    print("  Operating Mode: Local Simulated Networking")
    print("=" * 60)

    env = os.environ.copy()
    env["WIFIROUTER_SIMULATE"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    env["HOST"] = "127.0.0.1"
    env["PORT"] = "8090"
    env["DATABASE_URL"] = "sqlite+aiosqlite:///./wifirouter.db"

    processes = []

    try:
        # 1. Start Network Agent
        print("\n[1/3] Starting Network Agent on http://127.0.0.1:8091 ...")
        agent_proc = subprocess.Popen(
            [sys.executable, "-m", "agent.main"],
            cwd=str(ROOT_DIR / "network-agent"),
            env=env
        )
        processes.append(agent_proc)
        time.sleep(1)

        # 2. Start FastAPI Backend
        print("[2/3] Starting FastAPI Backend on http://127.0.0.1:8090 ...")
        backend_proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8090", "--reload"],
            cwd=str(ROOT_DIR / "backend"),
            env=env
        )
        processes.append(backend_proc)
        time.sleep(1)

        # 3. Start Vite Frontend
        print("[3/3] Starting Vite Frontend on http://localhost:5173 ...")
        npm_cmd = "npm.cmd" if os.name == "nt" else "npm"
        frontend_proc = subprocess.Popen(
            [npm_cmd, "run", "dev"],
            cwd=str(ROOT_DIR / "frontend"),
            env=env
        )
        processes.append(frontend_proc)

        print("\n" + "=" * 60)
        print("  All services are running!")
        print("  - Frontend UI:  http://localhost:5173")
        print("  - Backend API:  http://127.0.0.1:8090/api/docs")
        print("  - Network Agent: http://127.0.0.1:8091/health")
        print("  Press Ctrl+C to stop all services.")
        print("=" * 60 + "\n")

        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nShutting down WiFiRouter services...")
        for p in processes:
            p.terminate()
        for p in processes:
            p.wait()
        print("All services stopped.")

if __name__ == "__main__":
    main()

