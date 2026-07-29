#!/usr/bin/env python3
"""
scripts/run_api.py

Starts the FastAPI server on port 8000.
Run alongside Flask (port 5050) during the migration period.

Usage:
    python scripts/run_api.py

Or directly with uvicorn for more control:
    uvicorn api.main:app --reload --port 8000 --host 0.0.0.0
"""

import os
import sys

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)
os.chdir(project_root)

import uvicorn

if __name__ == "__main__":
    print("\n  Vendor Threat Monitor — FastAPI")
    print("  Running at http://localhost:8000")
    print("  Swagger UI at http://localhost:8000/api/docs\n")

    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["api", "app"],
    )