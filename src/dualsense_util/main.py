"""Entry point with admin privilege check and UAC elevation."""

from __future__ import annotations

import ctypes
import sys


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())  # type: ignore[attr-defined]
    except OSError:
        return False


def run_as_admin() -> None:
    """Re-launch the current script with UAC elevation."""
    ctypes.windll.shell32.ShellExecuteW(  # type: ignore[attr-defined]
        None, "runas", sys.executable, " ".join(sys.argv), None, 1
    )


def main() -> None:
    admin = is_admin()

    if not admin:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        answer = messagebox.askyesno(
            "Administrator Privileges",
            "This tool requires administrator privileges for full functionality.\n\n"
            "Restart as administrator?",
        )
        root.destroy()

        if answer:
            run_as_admin()
            return

    from .gui import App

    app = App(is_admin=admin)
    app.mainloop()


if __name__ == "__main__":
    main()
