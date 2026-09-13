"""Absolute-path launcher for MCP hosts without a working-directory option."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from studio_workflow.mcp_server import main

if __name__ == '__main__':
    raise SystemExit(main())
