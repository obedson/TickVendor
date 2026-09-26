// Windows asset helper; generated PNGs are checked in for all build platforms.
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
execFileSync('powershell.exe', ['-NoProfile', '-File', fileURLToPath(new URL('./generate-icons.ps1', import.meta.url))], { stdio: 'inherit' });
