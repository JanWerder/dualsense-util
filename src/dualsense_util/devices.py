"""Device Manager cleanup via PowerShell and pnputil as fallback."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass


@dataclass
class PnpDevice:
    instance_id: str
    friendly_name: str
    status: str
    device_class: str


def _run_powershell(script: str) -> str:
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0 and result.stderr.strip():
        raise RuntimeError(f"PowerShell error: {result.stderr.strip()}")
    return result.stdout.strip()


def find_bt_hid_devices() -> list[PnpDevice]:
    """Find DualSense-related devices in Device Manager via PowerShell."""
    script = r"""
        $devices = @()
        $btDevices = Get-PnpDevice -Class 'Bluetooth' -ErrorAction SilentlyContinue |
            Where-Object { $_.FriendlyName -match 'Wireless Controller|DualSense' }
        $hidDevices = Get-PnpDevice -Class 'HIDClass' -ErrorAction SilentlyContinue |
            Where-Object { $_.InstanceId -match 'BTHLE|BTHID' -and $_.FriendlyName -match 'game|controller|HID' }
        foreach ($d in @($btDevices) + @($hidDevices)) {
            if ($d) {
                $devices += @{
                    InstanceId = $d.InstanceId
                    FriendlyName = $d.FriendlyName
                    Status = $d.Status
                    Class = $d.Class
                }
            }
        }
        $devices | ConvertTo-Json -Compress
    """
    output = _run_powershell(script)
    if not output or output == "null":
        return []

    raw = json.loads(output)
    # PowerShell returns a single object instead of an array for one result
    if isinstance(raw, dict):
        raw = [raw]

    return [
        PnpDevice(
            instance_id=d["InstanceId"],
            friendly_name=d["FriendlyName"],
            status=d["Status"],
            device_class=d["Class"],
        )
        for d in raw
    ]


def remove_pnp_device(instance_id: str) -> tuple[bool, str]:
    """Remove a device from Device Manager via pnputil."""
    try:
        result = subprocess.run(
            ["pnputil", "/remove-device", instance_id],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return True, f"PnP device removed: {instance_id}"
        return False, f"pnputil failed: {result.stderr.strip() or result.stdout.strip()}"
    except subprocess.TimeoutExpired:
        return False, "pnputil Timeout"
    except FileNotFoundError:
        return False, "pnputil not found"


def cleanup_registry(mac_address: str) -> tuple[bool, str]:
    """Clean up leftover Bluetooth registry entries for a given MAC address."""
    mac_clean = mac_address.replace(":", "").replace("-", "").upper()

    script = f"""
        $removed = 0
        $basePaths = @(
            'HKLM:\\SYSTEM\\CurrentControlSet\\Services\\BTHPORT\\Parameters\\Devices',
            'HKLM:\\SYSTEM\\CurrentControlSet\\Enum\\BTHENUM'
        )
        foreach ($base in $basePaths) {{
            if (Test-Path $base) {{
                Get-ChildItem $base -Recurse -ErrorAction SilentlyContinue |
                    Where-Object {{ $_.Name -match '{mac_clean}' }} |
                    ForEach-Object {{
                        try {{
                            Remove-Item $_.PSPath -Recurse -Force -ErrorAction Stop
                            $removed++
                        }} catch {{}}
                    }}
            }}
        }}
        Write-Output $removed
    """
    try:
        output = _run_powershell(script)
        count = int(output) if output.isdigit() else 0
        if count > 0:
            return True, f"{count} registry entries removed"
        return True, "No registry entries found"
    except Exception as e:
        return False, f"Registry cleanup failed: {e}"
