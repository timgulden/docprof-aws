#!/usr/bin/env python3
"""
Package Lambda function with shared modules
"""
import sys
import os
import shutil
import zipfile
import tempfile
from pathlib import Path

def package_lambda(source_path, shared_path, zip_path):
    """Package Lambda function code with shared modules
    
    Structure in ZIP:
    - handler.py (at root)
    - requirements.txt (at root)
    - shared/ (directory with all shared modules)
    """
    source_path = Path(source_path).resolve()
    shared_path = Path(shared_path).resolve()
    zip_path = Path(zip_path).resolve()
    
    # Create temp directory
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Copy handler.py and requirements.txt to root of temp directory
        handler_file = source_path / "handler.py"
        if handler_file.exists():
            shutil.copy2(handler_file, temp_path / "handler.py")
            print(f"Copied handler.py to root")
        
        requirements_file = source_path / "requirements.txt"
        if requirements_file.exists():
            shutil.copy2(requirements_file, temp_path / "requirements.txt")
            print(f"Copied requirements.txt to root")
        
        # Copy shared code to shared/ directory
        if shared_path.exists():
            shared_dir = temp_path / "shared"
            shutil.copytree(shared_path, shared_dir)
            print(f"Copied shared/ directory")
        
        # Remove excluded files
        for pattern in ["*.pyc", "__pycache__", ".pytest_cache", "tests", "*.md"]:
            for path in temp_path.rglob(pattern):
                if path.is_file():
                    path.unlink()
                elif path.is_dir():
                    shutil.rmtree(path, ignore_errors=True)
        
        # Create ZIP
        zip_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in temp_path.rglob('*'):
                if file_path.is_file():
                    # Keep relative path structure (handler.py at root, shared/ as subdirectory)
                    arcname = file_path.relative_to(temp_path)
                    zipf.write(file_path, arcname)
        
        print(f"Created ZIP: {zip_path}")

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: package_lambda.py <source_path> <shared_path> <zip_path>")
        sys.exit(1)
    
    package_lambda(sys.argv[1], sys.argv[2], sys.argv[3])

