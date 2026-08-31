#!/usr/bin/env python3
import subprocess
import sys
import os

# Find pip
pip_path = r"C:\Users\NITDA\tickeven\venv\Scripts\pip.exe"

pkgs = ["python-jose[cryptography]", "qrcode", "Pillow", "httpx", "python-multipart"]

for pkg in pkgs:
    result = subprocess.run([pip_path, "install", pkg], capture_output=True, text=True)
    print(f"{pkg}: returncode={result.returncode}")
    if result.stderr:
        print(f"  stderr: {result.stderr[:200]}")
    if result.stdout:
        print(f"  stdout: {result.stdout[:200]}")

print("Remaining packages installed!")