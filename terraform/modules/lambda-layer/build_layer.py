#!/usr/bin/env python3
"""
Build Lambda Layer ZIP file with Python dependencies
Usage: python3 build_layer.py <requirements.txt> <output_dir>
"""

import sys
import subprocess
import os
from pathlib import Path

def build_layer(requirements_path: str, output_dir: str):
    """Build Lambda layer by installing requirements into python/lib/python3.11/site-packages/"""
    
    requirements_path = Path(requirements_path).resolve()
    output_dir = Path(output_dir).resolve()
    
    # Lambda layer structure: python/lib/python3.11/site-packages/
    site_packages = output_dir / "python" / "lib" / "python3.11" / "site-packages"
    site_packages.mkdir(parents=True, exist_ok=True)
    
    # Install packages using pip with --target
    # Lambda layers need packages in python/lib/python3.11/site-packages/
    # Suppress output to stderr so only JSON goes to stdout
    result = subprocess.run(
        [
            sys.executable, "-m", "pip", "install",
            "-r", str(requirements_path),
            "--target", str(site_packages),
            "--upgrade",
            "--quiet",  # Suppress pip output
        ],
        stderr=subprocess.PIPE,
        text=True
    )
    
    if result.returncode != 0:
        # Output errors to stderr, JSON to stdout
        print(f"Error installing packages: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    
    # Return JSON for external data source (must be ONLY output to stdout)
    import json
    print(json.dumps({
        "output_dir": str(output_dir),
        "site_packages": str(site_packages)
    }))

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 build_layer.py <requirements.txt> <output_dir>", file=sys.stderr)
        sys.exit(1)
    
    build_layer(sys.argv[1], sys.argv[2])

