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
    """Package Lambda function code with shared modules"""
    source_path = Path(source_path).resolve()
    shared_path = Path(shared_path).resolve()
    zip_path = Path(zip_path).resolve()
    
    # Create temp directory
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        function_dir = temp_path / source_path.name
        shared_dir = temp_path / "shared"
        
        # Copy function code
        shutil.copytree(source_path, function_dir)
        
        # Copy shared code if it exists
        if shared_path.exists():
            shutil.copytree(shared_path, shared_dir)
        
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
                    arcname = file_path.relative_to(temp_path)
                    zipf.write(file_path, arcname)
        
        print(f"Created ZIP: {zip_path}")

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: package_lambda.py <source_path> <shared_path> <zip_path>")
        sys.exit(1)
    
    package_lambda(sys.argv[1], sys.argv[2], sys.argv[3])

