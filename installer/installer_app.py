"""
OpenShorts Setup Wizard
Windows Installer Executable for OpenShorts.
Provides a modern GUI setup wizard and silent/CLI installation modes.
"""

import os
import sys
import argparse
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# Support local package imports whether running frozen (PyInstaller) or directly
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
PARENT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

from installer.dependency_checker import check_all_dependencies
from installer.installer_engine import InstallTask, get_default_install_dir


def set_high_dpi_awareness():
    """Enable crisp text rendering on high-DPI displays."""
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            import ctypes
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


class InstallerWizard(tk.Tk):
    def __init__(self, target_dir=None):
        super().__init__()
        
        self.title("OpenShorts Setup")
        self.geometry("640x500")
        self.resizable(False, False)
        
        # Center window
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = max(0, (sw - 640) // 2)
        y = max(0, (sh - 500) // 2)
        self.geometry(f"640x500+{x}+{y}")
        
        # Theme colors (Dark mode matching OpenShorts)
        self.c_bg = "#0f1319"
        self.c_card = "#161b22"
        self.c_header = "#12161f"
        self.c_border = "#2b323c"
        self.c_text_main = "#f0f6fc"
        self.c_text_dim = "#8b949e"
        self.c_accent = "#6366f1"
        self.c_accent_hover = "#4f46e5"
        self.c_success = "#2ea043"
        self.c_warning = "#d29922"
        self.c_error = "#f85149"

        self.configure(bg=self.c_bg)

        # Set window icon if available
        self._load_icon()

        # State
        self.target_dir = tk.StringVar(value=target_dir or get_default_install_dir())
        self.var_desktop = tk.BooleanVar(value=True)
        self.var_start_menu = tk.BooleanVar(value=True)
        self.var_register = tk.BooleanVar(value=True)
        self.var_launch = tk.BooleanVar(value=True)
        self.dep_results = None
        self.install_success = False
        self.current_step = 0
        
        # Build UI Structure
        self._build_header()
        self._build_container()
        self._build_footer()
        
        # Show first step
        self.show_step(0)

    def _load_icon(self):
        """Set window icon from bundled resources."""
        icon_candidates = [
            os.path.join(getattr(sys, "_MEIPASS", ""), "openshorts.ico"),
            os.path.join(SCRIPT_DIR, "openshorts.ico"),
            os.path.join(PARENT_DIR, "openshorts.ico"),
        ]
        for ic in icon_candidates:
            if os.path.exists(ic):
                try:
                    self.iconbitmap(ic)
                    break
                except Exception:
                    pass

    def _build_header(self):
        """Top banner bar."""
        self.header_frame = tk.Frame(self, bg=self.c_header, height=75, padx=24, pady=12)
        self.header_frame.pack(side="top", fill="x")
        self.header_frame.pack_propagate(False)

        self.lbl_header_title = tk.Label(
            self.header_frame, text="OpenShorts Setup",
            font=("Segoe UI", 13, "bold"), fg=self.c_text_main, bg=self.c_header, anchor="w"
        )
        self.lbl_header_title.pack(fill="x")

        self.lbl_header_sub = tk.Label(
            self.header_frame, text="AI-Powered Vertical Video Generator",
            font=("Segoe UI", 9), fg=self.c_text_dim, bg=self.c_header, anchor="w"
        )
        self.lbl_header_sub.pack(fill="x", pady=(2, 0))

        # Bottom border for header
        border = tk.Frame(self, bg=self.c_border, height=1)
        border.pack(side="top", fill="x")

    def _build_footer(self):
        """Bottom navigation bar."""
        border = tk.Frame(self, bg=self.c_border, height=1)
        border.pack(side="bottom", fill="x")

        self.footer_frame = tk.Frame(self, bg=self.c_header, height=60, padx=20, pady=12)
        self.footer_frame.pack(side="bottom", fill="x")
        self.footer_frame.pack_propagate(False)

        # Cancel / Exit button on left
        self.btn_cancel = tk.Button(
            self.footer_frame, text="Cancel", font=("Segoe UI", 9),
            bg="#21262d", fg=self.c_text_main, activebackground="#30363d", activeforeground="#ffffff",
            bd=0, relief="flat", padx=16, pady=6, cursor="hand2", command=self.on_cancel
        )
        self.btn_cancel.pack(side="left")

        # Next / Finish button on right
        self.btn_next = tk.Button(
            self.footer_frame, text="Next >", font=("Segoe UI", 9, "bold"),
            bg=self.c_accent, fg="#ffffff", activebackground=self.c_accent_hover, activeforeground="#ffffff",
            bd=0, relief="flat", padx=20, pady=6, cursor="hand2", command=self.on_next
        )
        self.btn_next.pack(side="right", padx=(8, 0))

        # Back button
        self.btn_back = tk.Button(
            self.footer_frame, text="< Back", font=("Segoe UI", 9),
            bg="#21262d", fg=self.c_text_main, activebackground="#30363d", activeforeground="#ffffff",
            bd=0, relief="flat", padx=16, pady=6, cursor="hand2", command=self.on_back
        )
        self.btn_back.pack(side="right")

    def _build_container(self):
        """Central content area for wizard pages."""
        self.content_frame = tk.Frame(self, bg=self.c_bg, padx=30, pady=20)
        self.content_frame.pack(side="top", fill="both", expand=True)

    def clear_content(self):
        for widget in self.content_frame.winfo_children():
            widget.destroy()

    def show_step(self, step_idx):
        self.current_step = step_idx
        self.clear_content()

        if step_idx == 0:
            self._render_welcome()
        elif step_idx == 1:
            self._render_dependencies()
        elif step_idx == 2:
            self._render_options()
        elif step_idx == 3:
            self._render_installing()
        elif step_idx == 4:
            self._render_finished()

    # ==================== STEP 0: WELCOME ====================
    def _render_welcome(self):
        self.lbl_header_title.config(text="Welcome to OpenShorts Setup")
        self.lbl_header_sub.config(text="Install the AI vertical video clipping & reframing desktop tool")
        self.btn_back.config(state="disabled")
        self.btn_next.config(text="Next >", state="normal")

        # Welcome heading
        lbl_heading = tk.Label(
            self.content_frame, text="Turn Long Videos into Viral Shorts",
            font=("Segoe UI", 14, "bold"), fg=self.c_text_main, bg=self.c_bg, anchor="w"
        )
        lbl_heading.pack(fill="x", pady=(10, 8))

        lbl_desc = tk.Label(
            self.content_frame,
            text="OpenShorts automatically clips highlight moments, reframes footage to 9:16\n"
                 "using face tracking, adds animated word-by-word subtitles, and generates viral titles.",
            font=("Segoe UI", 10), fg=self.c_text_dim, bg=self.c_bg, justify="left", anchor="w"
        )
        lbl_desc.pack(fill="x", pady=(0, 16))

        # Features box
        box = tk.Frame(self.content_frame, bg=self.c_card, bd=1, relief="solid", padx=16, pady=14)
        box.pack(fill="x", pady=(0, 16))

        features = [
            ("⚡ AI Viral Moment Detection", "Gemini AI finds the highest-scoring hooks and segments"),
            ("🎯 Smart 9:16 Video Reframing", "Automated active speaker framing and camera inset modes"),
            ("💬 Dynamic Animated Subtitles", "Word-level sync, custom fonts, emojis, and hook text"),
            ("🖥️ Full Desktop Interface", "Native preview window, zero-config local engine"),
        ]

        for title, desc in features:
            f_frame = tk.Frame(box, bg=self.c_card)
            f_frame.pack(fill="x", pady=3)
            tk.Label(f_frame, text=title, font=("Segoe UI", 9, "bold"), fg=self.c_text_main, bg=self.c_card).pack(anchor="w")
            tk.Label(f_frame, text=f"    {desc}", font=("Segoe UI", 8), fg=self.c_text_dim, bg=self.c_card).pack(anchor="w")

        tk.Label(
            self.content_frame, text="Click Next to check system dependencies and choose installation options.",
            font=("Segoe UI", 9, "italic"), fg=self.c_text_dim, bg=self.c_bg, anchor="w"
        ).pack(fill="x", pady=(8, 0))

    # ==================== STEP 1: DEPENDENCIES ====================
    def _render_dependencies(self):
        self.lbl_header_title.config(text="System & Dependency Verification")
        self.lbl_header_sub.config(text="Checking required runtime tools and environment")
        self.btn_back.config(state="normal")
        self.btn_next.config(text="Next >", state="disabled")

        lbl_desc = tk.Label(
            self.content_frame, text="Verifying system requirements for OpenShorts:",
            font=("Segoe UI", 11, "bold"), fg=self.c_text_main, bg=self.c_bg, anchor="w"
        )
        lbl_desc.pack(fill="x", pady=(5, 12))

        self.dep_box = tk.Frame(self.content_frame, bg=self.c_card, padx=16, pady=12)
        self.dep_box.pack(fill="x", pady=(0, 12))

        lbl_loading = tk.Label(
            self.dep_box, text="Scanning system components...",
            font=("Segoe UI", 10), fg=self.c_text_dim, bg=self.c_card
        )
        lbl_loading.pack(pady=20)

        # Run verification asynchronously so UI stays responsive
        threading.Thread(target=self._run_dep_check, daemon=True).start()

    def _run_dep_check(self):
        res = check_all_dependencies()
        self.dep_results = res
        self.after(50, self._display_dep_results)

    def _display_dep_results(self):
        for w in self.dep_box.winfo_children():
            w.destroy()

        all_ready = self.dep_results.get("ready", True)

        for item in self.dep_results.get("checks", []):
            row = tk.Frame(self.dep_box, bg=self.c_card)
            row.pack(fill="x", pady=4)

            # Icon / Status badge
            st = item.get("status", "ok")
            if st == "ok":
                badge_text = "✓ OK"
                badge_fg = self.c_success
            elif st == "info":
                badge_text = "ℹ INFO"
                badge_fg = self.c_text_dim
            else:
                badge_text = "⚠ WARN"
                badge_fg = self.c_warning

            lbl_badge = tk.Label(row, text=badge_text, font=("Segoe UI", 9, "bold"), fg=badge_fg, bg=self.c_card, width=8, anchor="w")
            lbl_badge.pack(side="left")

            lbl_name = tk.Label(row, text=item.get("name", ""), font=("Segoe UI", 9, "bold"), fg=self.c_text_main, bg=self.c_card, width=18, anchor="w")
            lbl_name.pack(side="left")

            lbl_ver = tk.Label(row, text=item.get("version", ""), font=("Segoe UI", 9), fg=self.c_text_dim, bg=self.c_card, anchor="w")
            lbl_ver.pack(side="left", fill="x", expand=True)

        # Summary line
        sum_frame = tk.Frame(self.content_frame, bg=self.c_bg)
        sum_frame.pack(fill="x", pady=(6, 0))

        if all_ready:
            lbl_summary = tk.Label(
                sum_frame, text="✓ All core system dependencies are verified and ready.",
                font=("Segoe UI", 10, "bold"), fg=self.c_success, bg=self.c_bg, anchor="w"
            )
            lbl_summary.pack(side="left")
            self.btn_next.config(state="normal")
        else:
            lbl_summary = tk.Label(
                sum_frame, text="⚠ Some components may need attention before running jobs.",
                font=("Segoe UI", 10, "bold"), fg=self.c_warning, bg=self.c_bg, anchor="w"
            )
            lbl_summary.pack(side="left")
            self.btn_next.config(state="normal")

    # ==================== STEP 2: INSTALL OPTIONS ====================
    def _render_options(self):
        self.lbl_header_title.config(text="Installation Settings")
        self.lbl_header_sub.config(text="Select destination folder and desktop options")
        self.btn_back.config(state="normal")
        self.btn_next.config(text="Install", state="normal")

        # Destination folder
        lbl_dir = tk.Label(
            self.content_frame, text="Destination Folder:",
            font=("Segoe UI", 10, "bold"), fg=self.c_text_main, bg=self.c_bg, anchor="w"
        )
        lbl_dir.pack(fill="x", pady=(5, 6))

        dir_frame = tk.Frame(self.content_frame, bg=self.c_bg)
        dir_frame.pack(fill="x", pady=(0, 16))

        entry_dir = tk.Entry(
            dir_frame, textvariable=self.target_dir, font=("Segoe UI", 9),
            bg=self.c_card, fg=self.c_text_main, insertbackground="#ffffff", bd=1, relief="solid"
        )
        entry_dir.pack(side="left", fill="x", expand=True, ipady=5, padx=(0, 8))

        btn_browse = tk.Button(
            dir_frame, text="Browse...", font=("Segoe UI", 9),
            bg="#21262d", fg=self.c_text_main, activebackground="#30363d", activeforeground="#ffffff",
            bd=0, relief="flat", padx=12, pady=5, cursor="hand2", command=self.on_browse
        )
        btn_browse.pack(side="right")

        # Options box
        lbl_opts = tk.Label(
            self.content_frame, text="Shortcuts & System Integration:",
            font=("Segoe UI", 10, "bold"), fg=self.c_text_main, bg=self.c_bg, anchor="w"
        )
        lbl_opts.pack(fill="x", pady=(0, 8))

        opts_box = tk.Frame(self.content_frame, bg=self.c_card, padx=16, pady=12)
        opts_box.pack(fill="x", pady=(0, 14))

        cb_desktop = tk.Checkbutton(
            opts_box, text="Create a Desktop shortcut", variable=self.var_desktop,
            font=("Segoe UI", 9), fg=self.c_text_main, bg=self.c_card, activebackground=self.c_card,
            selectcolor=self.c_bg, activeforeground=self.c_text_main
        )
        cb_desktop.pack(anchor="w", pady=3)

        cb_start = tk.Checkbutton(
            opts_box, text="Create a Start Menu folder and shortcut", variable=self.var_start_menu,
            font=("Segoe UI", 9), fg=self.c_text_main, bg=self.c_card, activebackground=self.c_card,
            selectcolor=self.c_bg, activeforeground=self.c_text_main
        )
        cb_start.pack(anchor="w", pady=3)

        cb_reg = tk.Checkbutton(
            opts_box, text="Register OpenShorts in Windows Settings (Add or Remove Programs)",
            variable=self.var_register, font=("Segoe UI", 9), fg=self.c_text_main, bg=self.c_card,
            activebackground=self.c_card, selectcolor=self.c_bg, activeforeground=self.c_text_main
        )
        cb_reg.pack(anchor="w", pady=3)

        # Space requirement note
        tk.Label(
            self.content_frame, text="Estimated disk space required: ~120 MB",
            font=("Segoe UI", 8), fg=self.c_text_dim, bg=self.c_bg, anchor="w"
        ).pack(fill="x")

    def on_browse(self):
        chosen = filedialog.askdirectory(initialdir=self.target_dir.get(), title="Select OpenShorts Installation Folder")
        if chosen:
            self.target_dir.set(os.path.abspath(chosen))

    # ==================== STEP 3: INSTALLING ====================
    def _render_installing(self):
        self.lbl_header_title.config(text="Installing OpenShorts")
        self.lbl_header_sub.config(text="Please wait while setup copies files and configures the app")
        self.btn_back.config(state="disabled")
        self.btn_next.config(state="disabled")
        self.btn_cancel.config(state="disabled")

        lbl_status = tk.Label(
            self.content_frame, text="Installing OpenShorts...",
            font=("Segoe UI", 11, "bold"), fg=self.c_text_main, bg=self.c_bg, anchor="w"
        )
        lbl_status.pack(fill="x", pady=(5, 10))

        # Progress bar
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Custom.Horizontal.TProgressbar", thickness=16, troughcolor=self.c_card, background=self.c_accent)

        self.progress_bar = ttk.Progressbar(self.content_frame, orient="horizontal", mode="determinate", style="Custom.Horizontal.TProgressbar")
        self.progress_bar.pack(fill="x", pady=(0, 10))
        self.progress_bar["value"] = 0

        self.lbl_progress_text = tk.Label(
            self.content_frame, text="Starting installation...",
            font=("Segoe UI", 9), fg=self.c_text_dim, bg=self.c_bg, anchor="w"
        )
        self.lbl_progress_text.pack(fill="x", pady=(0, 12))

        # Log box
        log_frame = tk.Frame(self.content_frame, bg=self.c_card, bd=1, relief="solid")
        log_frame.pack(fill="both", expand=True)

        self.txt_log = tk.Text(
            log_frame, font=("Consolas", 8), bg=self.c_card, fg="#c9d1d9",
            bd=0, relief="flat", wrap="none", padx=8, pady=8
        )
        self.txt_log.pack(side="left", fill="both", expand=True)

        sb = tk.Scrollbar(log_frame, command=self.txt_log.yview)
        sb.pack(side="right", fill="y")
        self.txt_log.config(yscrollcommand=sb.set)

        # Launch worker thread
        threading.Thread(target=self._run_install_worker, daemon=True).start()

    def _progress_callback(self, pct, msg):
        def _update():
            if pct is not None:
                self.progress_bar["value"] = pct
            self.lbl_progress_text.config(text=msg)
            self.txt_log.insert(tk.END, msg + "\n")
            self.txt_log.see(tk.END)
        self.after(10, _update)

    def _run_install_worker(self):
        task = InstallTask(
            install_dir=self.target_dir.get(),
            create_desktop=self.var_desktop.get(),
            create_start_menu=self.var_start_menu.get(),
            register_app=self.var_register.get()
        )
        ok, msg = task.run_installation(progress_cb=self._progress_callback)
        self.install_success = ok
        self.installed_task = task
        self.after(500, lambda: self.show_step(4))

    # ==================== STEP 4: FINISHED ====================
    def _render_finished(self):
        self.lbl_header_title.config(text="Installation Complete")
        self.lbl_header_sub.config(text="OpenShorts is ready to use")
        self.btn_back.config(state="disabled")
        self.btn_cancel.config(state="disabled")
        self.btn_next.config(text="Finish", state="normal")

        if self.install_success:
            lbl_done = tk.Label(
                self.content_frame, text="✓ Setup Completed Successfully!",
                font=("Segoe UI", 14, "bold"), fg=self.c_success, bg=self.c_bg, anchor="w"
            )
            lbl_done.pack(fill="x", pady=(15, 8))

            lbl_sub = tk.Label(
                self.content_frame,
                text="OpenShorts has been installed on your computer.\n"
                     f"Installed location: {self.target_dir.get()}",
                font=("Segoe UI", 9), fg=self.c_text_main, bg=self.c_bg, justify="left", anchor="w"
            )
            lbl_sub.pack(fill="x", pady=(0, 20))

            box = tk.Frame(self.content_frame, bg=self.c_card, padx=16, pady=16)
            box.pack(fill="x", pady=(0, 20))

            cb_launch = tk.Checkbutton(
                box, text="Launch OpenShorts now", variable=self.var_launch,
                font=("Segoe UI", 10, "bold"), fg=self.c_text_main, bg=self.c_card, activebackground=self.c_card,
                selectcolor=self.c_bg, activeforeground=self.c_text_main
            )
            cb_launch.pack(anchor="w")

            tk.Label(
                box, text="OpenShorts will start its desktop window and background processing engine.",
                font=("Segoe UI", 8), fg=self.c_text_dim, bg=self.c_card
            ).pack(anchor="w", padx=(24, 0), pady=(4, 0))

        else:
            lbl_done = tk.Label(
                self.content_frame, text="⚠ Installation encountered errors",
                font=("Segoe UI", 14, "bold"), fg=self.c_error, bg=self.c_bg, anchor="w"
            )
            lbl_done.pack(fill="x", pady=(15, 8))

    # ==================== ACTIONS ====================
    def on_next(self):
        if self.current_step == 0:
            self.show_step(1)
        elif self.current_step == 1:
            self.show_step(2)
        elif self.current_step == 2:
            self.show_step(3)
        elif self.current_step == 4:
            # Finish clicked
            if self.install_success and self.var_launch.get() and hasattr(self, "installed_task"):
                self.installed_task.launch_app()
            self.destroy()

    def on_back(self):
        if self.current_step > 0 and self.current_step != 3:
            self.show_step(self.current_step - 1)

    def on_cancel(self):
        if messagebox.askyesno("Exit Setup", "Are you sure you want to cancel OpenShorts setup?"):
            self.destroy()


def run_silent_install(install_dir=None, create_desktop=True, create_start_menu=True, register_app=True, launch=False):
    """Silent unattended installation mode."""
    print("=" * 60)
    print("OpenShorts Setup - Unattended Installation")
    print("=" * 60)
    
    task = InstallTask(
        install_dir=install_dir,
        create_desktop=create_desktop,
        create_start_menu=create_start_menu,
        register_app=register_app
    )
    
    def log_cb(pct, msg):
        print(f"[{pct or 0:3d}%] {msg}")
        
    ok, err = task.run_installation(progress_cb=log_cb)
    if ok:
        print("\nSUCCESS: OpenShorts installed successfully to:", task.install_dir)
        if launch:
            print("Launching OpenShorts application...")
            task.launch_app()
        return 0
    else:
        print(f"\nFAILURE: Installation failed: {err}", file=sys.stderr)
        return 1


def main():
    set_high_dpi_awareness()
    
    parser = argparse.ArgumentParser(description="OpenShorts Setup Installer")
    parser.add_argument("--silent", "-s", action="store_true", help="Run unattended silent installation")
    parser.add_argument("--install-dir", "-d", type=str, default=None, help="Installation directory")
    parser.add_argument("--no-desktop", action="store_true", help="Do not create desktop shortcut")
    parser.add_argument("--no-start-menu", action="store_true", help="Do not create start menu shortcut")
    parser.add_argument("--no-register", action="store_true", help="Do not register in Windows Add/Remove Programs")
    parser.add_argument("--launch", action="store_true", help="Launch OpenShorts after installation")
    parser.add_argument("--verify", action="store_true", help="Run system & dependency check and exit")

    # Support Windows-style slash flags (/S, /SILENT)
    slash_silent = any(arg.upper() in ("/S", "/SILENT", "/VERYSILENT") for arg in sys.argv)

    args, unknown = parser.parse_known_args()
    if slash_silent:
        args.silent = True

    if args.verify:
        print("Running OpenShorts dependency verification...")
        deps = check_all_dependencies()
        import json
        print(json.dumps(deps, indent=2))
        sys.exit(0 if deps.get("ready") else 1)

    if args.silent:
        rc = run_silent_install(
            install_dir=args.install_dir,
            create_desktop=not args.no_desktop,
            create_start_menu=not args.no_start_menu,
            register_app=not args.no_register,
            launch=args.launch
        )
        sys.exit(rc)
    else:
        app = InstallerWizard(target_dir=args.install_dir)
        app.mainloop()


if __name__ == "__main__":
    main()
