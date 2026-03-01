"""tkinter GUI for the DualSense Bluetooth Cleanup Utility."""

from __future__ import annotations

import threading
import tkinter as tk
import webbrowser
from tkinter import ttk, messagebox
from typing import Callable

from .bluetooth import BluetoothDevice, find_dualsense_devices, discover_devices, pair_device, remove_device
from .devices import find_bt_hid_devices, remove_pnp_device, cleanup_registry


class App(tk.Tk):
    def __init__(self, is_admin: bool) -> None:
        super().__init__()
        self.title("DualSense Bluetooth Helper")
        self.geometry("700x500")
        self.minsize(600, 400)
        self._devices: list[BluetoothDevice] = []
        self._is_admin = is_admin
        self._build_ui()

    def _build_ui(self) -> None:
        if not self._is_admin:
            warn = ttk.Label(
                self,
                text="Not running as administrator - some features are restricted",
                foreground="red",
            )
            warn.pack(padx=10, pady=(10, 0), anchor="w")

        # -- Toolbar --
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", padx=10, pady=10)

        self._btn_scan = ttk.Button(toolbar, text="Scan", command=self._on_scan)
        self._btn_scan.pack(side="left", padx=(0, 5))

        self._btn_remove = ttk.Button(toolbar, text="Remove", command=self._on_remove)
        self._btn_remove.pack(side="left", padx=5)

        self._btn_remove_all = ttk.Button(toolbar, text="Remove All", command=self._on_remove_all)
        self._btn_remove_all.pack(side="left", padx=5)

        self._btn_pair = ttk.Button(toolbar, text="Pair", command=self._on_pair)
        self._btn_pair.pack(side="left", padx=5)

        self._btn_help = ttk.Button(toolbar, text="Pairing Help", command=self._on_help)
        self._btn_help.pack(side="right")

        # -- Device list --
        columns = ("name", "mac", "status")
        self._tree = ttk.Treeview(self, columns=columns, show="headings", selectmode="browse")
        self._tree.heading("name", text="Name")
        self._tree.heading("mac", text="MAC Address")
        self._tree.heading("status", text="Status")
        self._tree.column("name", width=200)
        self._tree.column("mac", width=150)
        self._tree.column("status", width=200)
        self._tree.pack(fill="both", expand=True, padx=10)

        # -- Log area --
        log_frame = ttk.LabelFrame(self, text="Log")
        log_frame.pack(fill="x", padx=10, pady=10)

        self._log = tk.Text(log_frame, height=8, state="disabled", wrap="word")
        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self._log.yview)
        self._log.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self._log.pack(fill="both", expand=True, padx=5, pady=5)

    @staticmethod
    def _on_help() -> None:
        webbrowser.open(
            "https://www.playstation.com/en-us/support/hardware/"
            "pair-dualsense-controller-bluetooth/#blue"
        )

    def _log_msg(self, msg: str) -> None:
        self._log.configure(state="normal")
        self._log.insert("end", msg + "\n")
        self._log.see("end")
        self._log.configure(state="disabled")

    def _set_buttons_state(self, state: str) -> None:
        self._btn_scan.configure(state=state)
        self._btn_remove.configure(state=state)
        self._btn_remove_all.configure(state=state)
        self._btn_pair.configure(state=state)

    def _run_threaded(self, target: Callable[[], None]) -> None:
        """Run target in a background thread to keep the GUI responsive."""
        self._set_buttons_state("disabled")
        thread = threading.Thread(target=target, daemon=True)
        thread.start()

    def _on_scan(self) -> None:
        self._run_threaded(self._scan_worker)

    def _scan_worker(self) -> None:
        self.after(0, lambda: self._log_msg("Scanning for paired DualSense devices..."))
        try:
            paired = find_dualsense_devices()
            self.after(0, lambda: self._log_msg(f"{len(paired)} paired device(s) found."))

            if not paired:
                self.after(0, lambda: self._log_msg("Trying Device Manager..."))
                pnp = find_bt_hid_devices()
                if pnp:
                    for d in pnp:
                        self.after(0, lambda d=d: self._log_msg(
                            f"  PnP device: {d.friendly_name} ({d.instance_id}) [{d.status}]"
                        ))
                else:
                    self.after(0, lambda: self._log_msg("No devices found in Device Manager."))

            self.after(0, lambda: self._log_msg(
                "Searching for controllers in pairing mode (~10s)..."
            ))
            discovered = discover_devices()
            self.after(0, lambda: self._log_msg(
                f"{len(discovered)} unpaired controller(s) found."
            ))

            self._devices = paired + discovered
            self.after(0, lambda: self._populate_tree(self._devices))

            if discovered:
                self.after(0, lambda: self._log_msg(
                    "Select an unpaired controller and press 'Pair' to connect it."
                ))
        except Exception as e:
            self.after(0, lambda: self._log_msg(f"Scan error: {e}"))
        finally:
            self.after(0, lambda: self._set_buttons_state("normal"))

    def _populate_tree(self, devices: list[BluetoothDevice]) -> None:
        for item in self._tree.get_children():
            self._tree.delete(item)
        for i, dev in enumerate(devices):
            self._tree.insert("", "end", iid=str(i), values=(dev.name, dev.mac_str, dev.status_text))

    def _get_selected_device(self) -> BluetoothDevice | None:
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("No Device", "Please select a device first.")
            return None
        idx = int(sel[0])
        return self._devices[idx]

    def _on_remove(self) -> None:
        dev = self._get_selected_device()
        if dev:
            self._run_threaded(lambda: self._remove_worker(dev))

    def _remove_worker(self, dev: BluetoothDevice) -> None:
        self.after(0, lambda: self._log_msg(f"Removing {dev.name} ({dev.mac_str})..."))
        try:
            ok, msg = remove_device(dev.address)
            self.after(0, lambda: self._log_msg(f"  Bluetooth API: {msg}"))

            if ok:
                self.after(0, lambda: self._log_msg("Cleaning up Device Manager..."))
                self._cleanup_pnp_for(dev)

                self.after(0, lambda: self._log_msg("Cleaning up Registry..."))
                rok, rmsg = cleanup_registry(dev.mac_str)
                self.after(0, lambda: self._log_msg(f"  Registry: {rmsg}"))

            self.after(0, self._on_scan)
        except Exception as e:
            self.after(0, lambda: self._log_msg(f"Error: {e}"))
            self.after(0, lambda: self._set_buttons_state("normal"))

    def _on_remove_all(self) -> None:
        if not self._devices:
            messagebox.showinfo("No Devices", "No DualSense devices to remove.")
            return
        count = len(self._devices)
        if not messagebox.askyesno(
            "Remove All",
            f"Really remove {count} DualSense device(s)?",
        ):
            return
        self._run_threaded(self._remove_all_worker)

    def _remove_all_worker(self) -> None:
        devices = list(self._devices)
        for dev in devices:
            self.after(0, lambda d=dev: self._log_msg(f"Removing {d.name} ({d.mac_str})..."))
            try:
                ok, msg = remove_device(dev.address)
                self.after(0, lambda m=msg: self._log_msg(f"  Bluetooth API: {m}"))

                if ok:
                    self._cleanup_pnp_for(dev)
                    rok, rmsg = cleanup_registry(dev.mac_str)
                    self.after(0, lambda m=rmsg: self._log_msg(f"  Registry: {m}"))
            except Exception as e:
                self.after(0, lambda e=e: self._log_msg(f"  Error: {e}"))

        self.after(0, self._on_scan)

    def _on_pair(self) -> None:
        dev = self._get_selected_device()
        if not dev:
            return
        if dev.paired:
            messagebox.showinfo("Already Paired", f"{dev.name} is already paired.")
            return
        self._run_threaded(lambda: self._pair_worker(dev))

    def _pair_worker(self, dev: BluetoothDevice) -> None:
        self.after(0, lambda: self._log_msg(
            f"Pairing with {dev.name} ({dev.mac_str})..."
        ))
        try:
            ok, msg = pair_device(dev.address)
            self.after(0, lambda: self._log_msg(f"  {msg}"))
            if ok:
                self.after(0, self._on_scan)
                return
        except Exception as e:
            self.after(0, lambda: self._log_msg(f"Pairing error: {e}"))
        finally:
            self.after(0, lambda: self._set_buttons_state("normal"))

    def _cleanup_pnp_for(self, dev: BluetoothDevice) -> None:
        """Try to remove related PnP devices from Device Manager."""
        try:
            pnp_devices = find_bt_hid_devices()
            mac_clean = dev.mac_str.replace(":", "")
            for pnp in pnp_devices:
                if mac_clean.lower() in pnp.instance_id.lower():
                    ok, msg = remove_pnp_device(pnp.instance_id)
                    self.after(0, lambda m=msg: self._log_msg(f"  PnP: {m}"))
        except Exception as e:
            self.after(0, lambda: self._log_msg(f"  PnP cleanup failed: {e}"))
