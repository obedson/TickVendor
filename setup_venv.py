#!/usr/bin/env python3
import subprocess
import sys
import os

# Create venv
result = subprocess.run([sys.executable, "-m", "venv", "venv"], capture_output=True, text=True)
print("Venv creation:", result.returncode)
if result.stderr:
    print("stderr:", result.stderr[:200])

# Find activate script
if os.name == 'nt':
    activate_script = r"C:\Users\NITDA\tickeven\venv\Scripts\activate.bat"
    pip_cmd = r"C:\Users\NITDA\tickeven\venv\Scripts\pip.exe"
else:
    activate_script = os.path.join(os.getcwd(), "venv", "bin", "activate")
    pip_cmd = os.path.join(os.getcwd(), "venv", "bin", "pip")

print("Activate script:", activate_script)

# Install packages
install_cmd = [pip_cmd, "install", "fastapi", "uvicorn", "sqlalchemy", "alembic", "python-dotenv", "pydantic", "python-jose[cryptography]", "qrcode", "Pillow", "httpx", "python-multipart"]
result = subprocess.run(install_cmd, capture_output=True, text=True)
print("Install returncode:", result.returncode)
if result.stdout:
    print("stdout:", result.stdout[:500])
if result.stderr:
    print("stderr:", result.stderr[:500])

print("Done!")