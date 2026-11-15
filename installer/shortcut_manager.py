"""
Shortcut management for OpenShorts Windows Installer.
Creates and removes Desktop and Start Menu shortcuts.
"""

import os
import sys
import tempfile
import subprocess


def create_windows_shortcut(target_path, shortcut_path, icon_path=None, working_dir=None, description="OpenShorts"):
    """Create a Windows .lnk shortcut using standard Windows Script Host (cscript/vbs)."""
    target_path = os.path.abspath(target_path)
    shortcut_path = os.path.abspath(shortcut_path)
    if working_dir is None:
        working_dir = os.path.dirname(target_path)
    else:
        working_dir = os.path.abspath(working_dir)
        
    os.makedirs(os.path.dirname(shortcut_path), exist_ok=True)
    
    vbs_path = os.path.join(tempfile.gettempdir(), f"mk_lnk_{os.getpid()}_{hash(shortcut_path) & 0xFFFFFFFF}.vbs")
    try:
        with open(vbs_path, "w", encoding="utf-8") as f:
            f.write('Set oWS = WScript.CreateObject("WScript.Shell")\n')
            f.write(f'sLinkFile = "{shortcut_path}"\n')
            f.write('Set oLink = oWS.CreateShortcut(sLinkFile)\n')
            f.write(f'oLink.TargetPath = "{target_path}"\n')
            f.write(f'oLink.WorkingDirectory = "{working_dir}"\n')
            if icon_path and os.path.exists(icon_path):
                f.write(f'oLink.IconLocation = "{os.path.abspath(icon_path)}"\n')
            f.write(f'oLink.Description = "{description}"\n')
            f.write('oLink.Save\n')
            
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        res = subprocess.run(["cscript", "//nologo", vbs_path], capture_output=True, text=True, creationflags=flags)
        return res.returncode == 0 and os.path.exists(shortcut_path)
    except Exception as e:
        print(f"Error creating shortcut {shortcut_path}: {e}")
        return False
    finally:
        if os.path.exists(vbs_path):
            try:
                os.remove(vbs_path)
            except Exception:
                pass


def configure_shortcuts(install_dir, create_desktop=True, create_start_menu=True):
    """Configure Desktop and Start Menu shortcuts for OpenShorts."""
    results = {}
    exe_path = os.path.join(install_dir, "OpenShorts.exe")
    icon_path = os.path.join(install_dir, "openshorts.ico")
    uninstall_cmd = os.path.join(install_dir, "uninstall.cmd")
    
    # 1. Desktop shortcut
    if create_desktop:
        desktop_dir = os.path.join(os.environ.get("USERPROFILE", os.path.expanduser("~")), "Desktop")
        desktop_lnk = os.path.join(desktop_dir, "OpenShorts.lnk")
        ok = create_windows_shortcut(
            target_path=exe_path,
            shortcut_path=desktop_lnk,
            icon_path=icon_path,
            working_dir=install_dir,
            description="OpenShorts - AI Vertical Video Generator"
        )
        results["desktop"] = {"path": desktop_lnk, "created": ok}
        
    # 2. Start Menu shortcuts
    if create_start_menu:
        appdata = os.environ.get("APPDATA", "")
        start_menu_folder = os.path.join(appdata, r"Microsoft\Windows\Start Menu\Programs\OpenShorts")
        os.makedirs(start_menu_folder, exist_ok=True)
        
        # App shortcut
        app_lnk = os.path.join(start_menu_folder, "OpenShorts.lnk")
        ok_app = create_windows_shortcut(
            target_path=exe_path,
            shortcut_path=app_lnk,
            icon_path=icon_path,
            working_dir=install_dir,
            description="OpenShorts - AI Vertical Video Generator"
        )
        
        # Uninstall shortcut
        uninst_lnk = os.path.join(start_menu_folder, "Uninstall OpenShorts.lnk")
        ok_uninst = create_windows_shortcut(
            target_path=uninstall_cmd,
            shortcut_path=uninst_lnk,
            icon_path=icon_path,
            working_dir=install_dir,
            description="Uninstall OpenShorts"
        )
        
        results["start_menu"] = {
            "folder": start_menu_folder,
            "app_shortcut": app_lnk,
            "created": ok_app and ok_uninst
        }
        
    return results


def remove_shortcuts():
    """Remove Desktop and Start Menu shortcuts during uninstallation."""
    # Desktop
    desktop_lnk = os.path.join(os.environ.get("USERPROFILE", os.path.expanduser("~")), "Desktop", "OpenShorts.lnk")
    if os.path.exists(desktop_lnk):
        try:
            os.remove(desktop_lnk)
        except Exception:
            pass
            
    # Start menu
    start_menu_folder = os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs\OpenShorts")
    if os.path.exists(start_menu_folder):
        try:
            shutil.rmtree(start_menu_folder, ignore_errors=True)
        except Exception:
            pass


if __name__ == "__main__":
    print("Testing shortcut manager...")
    res = configure_shortcuts(os.path.abspath("."), create_desktop=False, create_start_menu=False)
    print("Results:", res)
