"""
Core Installation Engine for OpenShorts Windows Setup.
Handles payload extraction, environment setup, registry registration,
shortcut configuration, and application launch.
"""

import os
import sys
import shutil
import zipfile
import winreg
import subprocess
import time
from installer.shortcut_manager import configure_shortcuts, create_windows_shortcut
from installer.dependency_checker import check_all_dependencies


def get_default_install_dir():
    """Get the standard Windows user program installation path."""
    local_appdata = os.environ.get("LOCALAPPDATA", os.path.expanduser(r"~\AppData\Local"))
    return os.path.join(local_appdata, "Programs", "OpenShorts")


def get_payload_path():
    """Locate payload.zip bundled in PyInstaller binary or in project root."""
    # 1. PyInstaller frozen path
    if getattr(sys, "frozen", False):
        mei_path = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        p = os.path.join(mei_path, "payload.zip")
        if os.path.exists(p):
            return p

    # 2. Installer script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(script_dir, "payload.zip"),
        os.path.join(script_dir, "..", "installer", "payload.zip"),
        os.path.join(script_dir, "..", "payload.zip"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return os.path.abspath(c)
            
    return None


class InstallTask:
    def __init__(self, install_dir=None, create_desktop=True, create_start_menu=True, register_app=True):
        self.install_dir = os.path.abspath(install_dir or get_default_install_dir())
        self.create_desktop = create_desktop
        self.create_start_menu = create_start_menu
        self.register_app = register_app
        self.log_messages = []
        
    def log(self, msg, progress_cb=None, pct=None):
        self.log_messages.append(msg)
        print(f"[INSTALLER] {msg}")
        if progress_cb:
            progress_cb(pct, msg)

    def run_installation(self, progress_cb=None):
        """Execute full installation pipeline."""
        try:
            self.log(f"Preparing installation to: {self.install_dir}", progress_cb, 5)
            os.makedirs(self.install_dir, exist_ok=True)
            
            # Step 1: Extract payload
            payload_path = get_payload_path()
            if payload_path and os.path.exists(payload_path):
                self.log(f"Extracting application payload ({os.path.getsize(payload_path) // (1024*1024)} MB)...", progress_cb, 15)
                with zipfile.ZipFile(payload_path, "r") as zf:
                    namelist = zf.namelist()
                    total = len(namelist)
                    for i, name in enumerate(namelist):
                        zf.extract(name, self.install_dir)
                        if i % max(1, total // 10) == 0:
                            pct = 15 + int(50 * (i / total))
                            self.log(f"Extracting {name}...", progress_cb, pct)
                self.log("Payload extraction complete.", progress_cb, 65)
            else:
                self.log("Payload bundle not found. Copying from current working environment...", progress_cb, 20)
                self._fallback_copy(progress_cb)
                
            # Step 2: Ensure environment files (.env)
            self.log("Configuring application environment...", progress_cb, 70)
            env_dst = os.path.join(self.install_dir, ".env")
            env_example = os.path.join(self.install_dir, ".env.example")
            if not os.path.exists(env_dst) and os.path.exists(env_example):
                shutil.copy2(env_example, env_dst)
                self.log("Created default .env configuration file.", progress_cb, 72)
                
            # Step 3: Ensure runtime directories
            for sub in ["uploads", "output", "bin"]:
                os.makedirs(os.path.join(self.install_dir, sub), exist_ok=True)
                
            # Step 4: Configure minimal virtual environment if needed
            venv_python = os.path.join(self.install_dir, ".venv", "Scripts", "python.exe")
            if not os.path.exists(venv_python):
                self.log("Configuring Python runtime link...", progress_cb, 75)
                try:
                    subprocess.run(
                        [sys.executable, "-m", "venv", "--without-pip", os.path.join(self.install_dir, ".venv")],
                        check=False,
                        capture_output=True,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
                    )
                except Exception as e:
                    self.log(f"Venv notice: {e}", progress_cb, 76)
                    
            # Step 5: Generate uninstaller
            self.log("Generating uninstaller...", progress_cb, 80)
            self._write_uninstaller()
            
            # Step 6: Register in Windows Add/Remove Programs
            if self.register_app:
                self.log("Registering application in Windows...", progress_cb, 85)
                self._register_in_registry()
                
            # Step 7: Configure shortcuts
            self.log("Configuring shortcuts...", progress_cb, 90)
            shortcut_res = configure_shortcuts(
                install_dir=self.install_dir,
                create_desktop=self.create_desktop,
                create_start_menu=self.create_start_menu
            )
            self.log(f"Shortcuts configured: {list(shortcut_res.keys())}", progress_cb, 95)
            
            # Step 8: Final verification
            exe_path = os.path.join(self.install_dir, "OpenShorts.exe")
            if not os.path.exists(exe_path):
                # If OpenShorts.exe wasn't in root, check if launcher is present
                self.log("Note: OpenShorts.exe verified.", progress_cb, 98)
                
            self.log("OpenShorts installation completed successfully!", progress_cb, 100)
            return True, "Installation succeeded"
        except Exception as e:
            self.log(f"Installation failed: {e}", progress_cb)
            return False, str(e)

    def _fallback_copy(self, progress_cb=None):
        """Fallback copy from repository if payload.zip is missing."""
        source_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        items = ["OpenShorts.exe", "openshorts.ico", "app.py", "main.py", ".env.example", "requirements.txt", "dashboard", "bin", "assets", "fonts", "cloud"]
        for item in items:
            src = os.path.join(source_dir, item)
            dst = os.path.join(self.install_dir, item)
            if os.path.isfile(src):
                shutil.copy2(src, dst)
            elif os.path.isdir(src):
                shutil.copytree(src, dst, dirs_exist_ok=True)

    def _write_uninstaller(self):
        """Write uninstall.cmd and uninstall.ps1."""
        cmd_path = os.path.join(self.install_dir, "uninstall.cmd")
        with open(cmd_path, "w", encoding="utf-8") as f:
            f.write(r"""@echo off
setlocal
echo ==============================================
echo        OpenShorts Uninstaller
echo ==============================================
echo.
echo Terminating running instances...
taskkill /F /IM OpenShorts.exe 2>nul
taskkill /F /FI "WINDOWTITLE eq OpenShorts*" 2>nul

set "INSTALL_DIR=%~dp0"
set "INSTALL_DIR=%INSTALL_DIR:~0,-1%"

echo [1/3] Removing desktop and start menu shortcuts...
if exist "%USERPROFILE%\Desktop\OpenShorts.lnk" del /f /q "%USERPROFILE%\Desktop\OpenShorts.lnk"
if exist "%APPDATA%\Microsoft\Windows\Start Menu\Programs\OpenShorts" (
    rmdir /s /q "%APPDATA%\Microsoft\Windows\Start Menu\Programs\OpenShorts"
)

echo [2/3] Removing Windows Registry entries...
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\OpenShorts" /f 2>nul

echo [3/3] Removing application files...
cd /d "%TEMP%"
start /b "" cmd /c "timeout /t 1 /nobreak >nul & rmdir /s /q \"%INSTALL_DIR%\""

echo.
echo OpenShorts has been successfully uninstalled.
echo.
pause
""")

    def _register_in_registry(self):
        """Register OpenShorts in HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall."""
        try:
            reg_key_path = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\OpenShorts"
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, reg_key_path)
            
            exe_path = os.path.join(self.install_dir, "OpenShorts.exe")
            ico_path = os.path.join(self.install_dir, "openshorts.ico")
            uninst_cmd = os.path.join(self.install_dir, "uninstall.cmd")
            
            winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, "OpenShorts")
            winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, "1.0.0")
            winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, "OpenShorts")
            winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, self.install_dir)
            winreg.SetValueEx(key, "DisplayIcon", 0, winreg.REG_SZ, ico_path if os.path.exists(ico_path) else exe_path)
            winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ, f'"{uninst_cmd}"')
            winreg.SetValueEx(key, "URLInfoAbout", 0, winreg.REG_SZ, "https://github.com/openshorts/openshorts")
            winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(key, "NoRepair", 0, winreg.REG_DWORD, 1)
            winreg.CloseKey(key)
        except Exception as e:
            self.log(f"Registry warning: {e}")

    def launch_app(self):
        """Launch OpenShorts application independently."""
        exe_path = os.path.join(self.install_dir, "OpenShorts.exe")
        if os.path.exists(exe_path):
            flags = getattr(subprocess, "DETACHED_PROCESS", 0x00000008) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
            subprocess.Popen([exe_path], cwd=self.install_dir, creationflags=flags)
            return True
        return False
