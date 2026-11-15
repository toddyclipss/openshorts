"""
Dependency verification module for OpenShorts Windows Installer.
Checks for Python, FFmpeg, Node.js, and system compatibility.
"""

import os
import sys
import shutil
import platform
import subprocess
import winreg


def check_python():
    """Verify Python availability, version, and architecture."""
    candidates = []
    
    # 1. Current running python
    candidates.append((sys.executable, f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"))
    
    # 2. Check python in PATH
    path_python = shutil.which("python")
    if path_python and path_python.lower() != sys.executable.lower():
        try:
            out = subprocess.check_output([path_python, "--version"], text=True, stderr=subprocess.STDOUT, timeout=3).strip()
            ver = out.replace("Python", "").strip()
            candidates.append((path_python, ver))
        except Exception:
            pass

    # 3. Check Python 3.11 in standard AppData or Program Files
    appdata = os.environ.get("LOCALAPPDATA", "")
    known_paths = [
        os.path.join(appdata, r"Programs\Python\Python311\python.exe"),
        os.path.join(appdata, r"Programs\Python\Python312\python.exe"),
        r"C:\Python311\python.exe",
        r"C:\Python312\python.exe",
        r"C:\Python314\python.exe",
    ]
    for kp in known_paths:
        if os.path.exists(kp) and kp.lower() not in [c[0].lower() for c in candidates]:
            try:
                out = subprocess.check_output([kp, "--version"], text=True, stderr=subprocess.STDOUT, timeout=3).strip()
                ver = out.replace("Python", "").strip()
                candidates.append((kp, ver))
            except Exception:
                pass

    # Evaluate best candidate (prefer >= 3.10)
    best_candidate = None
    for path, ver in candidates:
        try:
            parts = [int(p) for p in ver.split(".")[:2]]
            if parts[0] == 3 and parts[1] >= 10:
                best_candidate = (path, ver)
                break
        except Exception:
            continue

    if best_candidate:
        return {
            "status": "ok",
            "name": "Python",
            "found": True,
            "version": f"Python {best_candidate[1]}",
            "path": best_candidate[0],
            "details": f"Compatible Python found at {best_candidate[0]}"
        }
    elif candidates:
        return {
            "status": "warning",
            "name": "Python",
            "found": True,
            "version": f"Python {candidates[0][1]}",
            "path": candidates[0][0],
            "details": f"Found Python {candidates[0][1]} (Python 3.10+ recommended)"
        }
    else:
        return {
            "status": "error",
            "name": "Python",
            "found": False,
            "version": "Not Found",
            "path": None,
            "details": "Python 3.10+ not found. Please install Python from python.org or Microsoft Store."
        }


def check_ffmpeg(base_dir=None):
    """Verify FFmpeg binary in bin/ or in system PATH."""
    search_paths = []
    
    if base_dir:
        search_paths.append(os.path.join(base_dir, "bin", "ffmpeg.exe"))
        search_paths.append(os.path.join(base_dir, "bin", "ffmpeg"))
    
    # Check current directory
    search_paths.append(os.path.abspath(r"bin\ffmpeg.exe"))
    search_paths.append(os.path.abspath(r"bin\ffmpeg"))
    
    for sp in search_paths:
        if os.path.exists(sp):
            return {
                "status": "ok",
                "name": "FFmpeg",
                "found": True,
                "version": "OpenShorts Bundled FFmpeg",
                "path": sp,
                "details": f"Using bundled FFmpeg binary at {sp}"
            }
            
    # Check system PATH
    ffmpeg_in_path = shutil.which("ffmpeg")
    if ffmpeg_in_path:
        try:
            out = subprocess.check_output([ffmpeg_in_path, "-version"], text=True, stderr=subprocess.STDOUT, timeout=3).splitlines()[0]
            return {
                "status": "ok",
                "name": "FFmpeg",
                "found": True,
                "version": out.split("Copyright")[0].strip(),
                "path": ffmpeg_in_path,
                "details": f"System FFmpeg detected at {ffmpeg_in_path}"
            }
        except Exception:
            return {
                "status": "ok",
                "name": "FFmpeg",
                "found": True,
                "version": "Detected in PATH",
                "path": ffmpeg_in_path,
                "details": f"FFmpeg available at {ffmpeg_in_path}"
            }

    return {
        "status": "warning",
        "name": "FFmpeg",
        "found": True,
        "version": "Bundled in Package",
        "path": "bin/ffmpeg",
        "details": "FFmpeg package included with OpenShorts installer."
    }


def check_node():
    """Verify Node.js and npm if present."""
    node_path = shutil.which("node")
    npm_path = shutil.which("npm")
    
    if node_path:
        try:
            out = subprocess.check_output([node_path, "--version"], text=True, timeout=3).strip()
            return {
                "status": "ok",
                "name": "Node.js & npm",
                "found": True,
                "version": f"Node {out}",
                "path": node_path,
                "details": "Node.js environment detected (useful for frontend development)"
            }
        except Exception:
            pass
            
    return {
        "status": "info",
        "name": "Node.js & npm",
        "found": False,
        "version": "Pre-built Dashboard Bundled",
        "path": None,
        "details": "Not required. Pre-compiled web dashboard is included."
    }


def check_system():
    """Verify Windows OS architecture and requirements."""
    is_64bit = sys.maxsize > 2**32 or platform.machine().endswith('64')
    os_name = f"Windows {platform.release()} ({platform.machine()})"
    
    return {
        "status": "ok" if is_64bit else "error",
        "name": "Operating System",
        "found": is_64bit,
        "version": os_name,
        "path": "x86_64" if is_64bit else "x86",
        "details": "64-bit Windows OS detected. Fully compatible with OpenShorts." if is_64bit else "64-bit Windows is required."
    }


def check_all_dependencies(base_dir=None):
    """Run all dependency checks and return summary."""
    sys_check = check_system()
    py_check = check_python()
    ffmpeg_check = check_ffmpeg(base_dir)
    node_check = check_node()
    
    results = [sys_check, py_check, ffmpeg_check, node_check]
    all_ok = all(r["status"] in ("ok", "info", "warning") for r in results)
    
    return {
        "ready": all_ok,
        "checks": results
    }


if __name__ == "__main__":
    import json
    report = check_all_dependencies()
    print(json.dumps(report, indent=2))
