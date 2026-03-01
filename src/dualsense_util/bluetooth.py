"""Windows Bluetooth API via ctypes for discovering, pairing, and removing devices."""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wintypes
from dataclasses import dataclass
from enum import IntEnum

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SONY_VENDOR_ID = 0x054C
DUALSENSE_NAMES = {"wireless controller", "dualsense wireless controller"}

BLUETOOTH_MAX_NAME_SIZE = 248
BTH_ADDR = ctypes.c_ulonglong

ERROR_SUCCESS = 0
ERROR_NO_MORE_ITEMS = 259


class DeviceStatus(IntEnum):
    PAIRED = 0
    CONNECTED = 1
    REMEMBERED = 2
    UNKNOWN = 3


class BLUETOOTH_AUTHENTICATION_REQUIREMENTS(IntEnum):
    MITMProtectionNotRequired = 0
    MITMProtectionRequired = 1
    MITMProtectionNotRequiredBonding = 2
    MITMProtectionRequiredBonding = 3
    MITMProtectionNotRequiredGeneralBonding = 4
    MITMProtectionRequiredGeneralBonding = 5
    MITMProtectionNotDefined = 6


# ---------------------------------------------------------------------------
# Structs
# ---------------------------------------------------------------------------

class SYSTEMTIME(ctypes.Structure):
    _fields_ = [
        ("wYear", wintypes.WORD),
        ("wMonth", wintypes.WORD),
        ("wDayOfWeek", wintypes.WORD),
        ("wDay", wintypes.WORD),
        ("wHour", wintypes.WORD),
        ("wMinute", wintypes.WORD),
        ("wSecond", wintypes.WORD),
        ("wMilliseconds", wintypes.WORD),
    ]


class BLUETOOTH_DEVICE_INFO(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("Address", BTH_ADDR),
        ("ulClassofDevice", ctypes.c_ulong),
        ("fConnected", wintypes.BOOL),
        ("fRemembered", wintypes.BOOL),
        ("fAuthenticated", wintypes.BOOL),
        ("stLastSeen", SYSTEMTIME),
        ("stLastUsed", SYSTEMTIME),
        ("szName", ctypes.c_wchar * BLUETOOTH_MAX_NAME_SIZE),
    ]


class BLUETOOTH_DEVICE_SEARCH_PARAMS(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("fReturnAuthenticated", wintypes.BOOL),
        ("fReturnRemembered", wintypes.BOOL),
        ("fReturnUnknown", wintypes.BOOL),
        ("fReturnConnected", wintypes.BOOL),
        ("fIssueInquiry", wintypes.BOOL),
        ("cTimeoutMultiplier", ctypes.c_ulong),
        ("hRadio", wintypes.HANDLE),
    ]


class BLUETOOTH_FIND_RADIO_PARAMS(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
    ]


# -- Structs for authentication callback (silent pairing) --

BTH_MAX_PIN_SIZE = 16


class BLUETOOTH_PIN_INFO(ctypes.Structure):
    _fields_ = [
        ("pin", ctypes.c_ubyte * BTH_MAX_PIN_SIZE),
        ("pinLength", ctypes.c_ubyte),
    ]


class BLUETOOTH_OOB_DATA_INFO(ctypes.Structure):
    _fields_ = [
        ("C", ctypes.c_ubyte * 16),
        ("R", ctypes.c_ubyte * 16),
    ]


class BLUETOOTH_NUMERIC_COMPARISON_INFO(ctypes.Structure):
    _fields_ = [("NumericValue", ctypes.c_ulong)]


class BLUETOOTH_PASSKEY_INFO(ctypes.Structure):
    _fields_ = [("passkey", ctypes.c_ulong)]


class _AUTH_UNION(ctypes.Union):
    _fields_ = [
        ("pinInfo", BLUETOOTH_PIN_INFO),
        ("oobInfo", BLUETOOTH_OOB_DATA_INFO),
        ("numericCompInfo", BLUETOOTH_NUMERIC_COMPARISON_INFO),
        ("passkeyInfo", BLUETOOTH_PASSKEY_INFO),
    ]


class BLUETOOTH_AUTHENTICATE_RESPONSE(ctypes.Structure):
    _fields_ = [
        ("bthAddressRemote", BTH_ADDR),
        ("authMethod", ctypes.c_ulong),
        ("u", _AUTH_UNION),
        ("negativeResponse", ctypes.c_ubyte),
    ]


class BLUETOOTH_AUTHENTICATION_CALLBACK_PARAMS(ctypes.Structure):
    _fields_ = [
        ("deviceInfo", BLUETOOTH_DEVICE_INFO),
        ("authenticationMethod", ctypes.c_ulong),
        ("ioCapability", ctypes.c_ulong),
        ("authenticationRequirements", ctypes.c_ulong),
        ("Numeric_Value", ctypes.c_ulong),
    ]


# BOOL CALLBACK fn(LPVOID pvParam, PBLUETOOTH_AUTHENTICATION_CALLBACK_PARAMS)
AUTHENTICATION_CALLBACK_EX = ctypes.WINFUNCTYPE(
    wintypes.BOOL,
    ctypes.c_void_p,
    ctypes.POINTER(BLUETOOTH_AUTHENTICATION_CALLBACK_PARAMS),
)


# ---------------------------------------------------------------------------
# DLL bindings
# ---------------------------------------------------------------------------

_bt = ctypes.windll.BluetoothAPIs  # type: ignore[attr-defined]

_bt.BluetoothFindFirstRadio.argtypes = [
    ctypes.POINTER(BLUETOOTH_FIND_RADIO_PARAMS),
    ctypes.POINTER(wintypes.HANDLE),
]
_bt.BluetoothFindFirstRadio.restype = wintypes.HANDLE

_bt.BluetoothFindRadioClose.argtypes = [wintypes.HANDLE]
_bt.BluetoothFindRadioClose.restype = wintypes.BOOL

_bt.BluetoothFindFirstDevice.argtypes = [
    ctypes.POINTER(BLUETOOTH_DEVICE_SEARCH_PARAMS),
    ctypes.POINTER(BLUETOOTH_DEVICE_INFO),
]
_bt.BluetoothFindFirstDevice.restype = wintypes.HANDLE

_bt.BluetoothFindNextDevice.argtypes = [
    wintypes.HANDLE,
    ctypes.POINTER(BLUETOOTH_DEVICE_INFO),
]
_bt.BluetoothFindNextDevice.restype = wintypes.BOOL

_bt.BluetoothFindDeviceClose.argtypes = [wintypes.HANDLE]
_bt.BluetoothFindDeviceClose.restype = wintypes.BOOL

_bt.BluetoothRemoveDevice.argtypes = [ctypes.POINTER(BTH_ADDR)]
_bt.BluetoothRemoveDevice.restype = wintypes.DWORD

_kernel32 = ctypes.windll.kernel32
_kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
_kernel32.CloseHandle.restype = wintypes.BOOL


_bthprops: ctypes.WinDLL | None = None


def _resolve_bt_func(name: str) -> ctypes._NamedFuncPointer:
    """Resolve a Bluetooth API function, trying BluetoothAPIs.dll then bthprops.cpl."""
    global _bthprops
    if _bthprops is None:
        try:
            _bthprops = ctypes.WinDLL("bthprops.cpl")
        except OSError:
            _bthprops = _bt  # type: ignore[assignment]
    for dll in (_bt, _bthprops):
        try:
            return getattr(dll, name)  # type: ignore[no-any-return]
        except AttributeError:
            continue
    raise OSError(f"{name} not found in any Bluetooth DLL")


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class BluetoothDevice:
    name: str
    address: int
    connected: bool
    remembered: bool
    authenticated: bool

    @property
    def paired(self) -> bool:
        return self.remembered or self.authenticated

    @property
    def mac_str(self) -> str:
        b = self.address.to_bytes(6, byteorder="big")
        return ":".join(f"{x:02X}" for x in b)

    @property
    def status_text(self) -> str:
        if not self.paired:
            return "Found (not paired)"
        parts: list[str] = []
        if self.connected:
            parts.append("Connected")
        if self.remembered:
            parts.append("Paired")
        if self.authenticated:
            parts.append("Authenticated")
        return ", ".join(parts) if parts else "Unknown"

    def is_dualsense(self) -> bool:
        return self.name.strip().lower() in DUALSENSE_NAMES


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _get_radio_handle() -> wintypes.HANDLE | None:
    params = BLUETOOTH_FIND_RADIO_PARAMS()
    params.dwSize = ctypes.sizeof(BLUETOOTH_FIND_RADIO_PARAMS)
    radio = wintypes.HANDLE()
    h_find = _bt.BluetoothFindFirstRadio(ctypes.byref(params), ctypes.byref(radio))
    if not h_find:
        return None
    _bt.BluetoothFindRadioClose(h_find)
    return radio


def find_all_paired_devices() -> list[BluetoothDevice]:
    """Return all paired/remembered Bluetooth devices."""
    radio = _get_radio_handle()

    search = BLUETOOTH_DEVICE_SEARCH_PARAMS()
    search.dwSize = ctypes.sizeof(BLUETOOTH_DEVICE_SEARCH_PARAMS)
    search.fReturnAuthenticated = True
    search.fReturnRemembered = True
    search.fReturnConnected = True
    search.fReturnUnknown = True
    search.fIssueInquiry = False
    search.cTimeoutMultiplier = 0
    search.hRadio = radio if radio else wintypes.HANDLE(0)

    info = BLUETOOTH_DEVICE_INFO()
    info.dwSize = ctypes.sizeof(BLUETOOTH_DEVICE_INFO)

    devices: list[BluetoothDevice] = []
    h_find = _bt.BluetoothFindFirstDevice(ctypes.byref(search), ctypes.byref(info))
    if not h_find:
        if radio:
            _kernel32.CloseHandle(radio)
        return devices

    while True:
        devices.append(BluetoothDevice(
            name=info.szName,
            address=info.Address,
            connected=bool(info.fConnected),
            remembered=bool(info.fRemembered),
            authenticated=bool(info.fAuthenticated),
        ))
        info = BLUETOOTH_DEVICE_INFO()
        info.dwSize = ctypes.sizeof(BLUETOOTH_DEVICE_INFO)
        if not _bt.BluetoothFindNextDevice(h_find, ctypes.byref(info)):
            break

    _bt.BluetoothFindDeviceClose(h_find)
    if radio:
        _kernel32.CloseHandle(radio)
    return devices


def find_dualsense_devices() -> list[BluetoothDevice]:
    """Return only DualSense / Wireless Controller devices.

    Filters out ghost entries (no flags set) that linger after removal.
    """
    return [
        d for d in find_all_paired_devices()
        if d.is_dualsense() and (d.connected or d.remembered or d.authenticated)
    ]


def discover_devices(timeout_multiplier: int = 8) -> list[BluetoothDevice]:
    """Active Bluetooth inquiry for unpaired DualSense controllers.

    Uses fIssueInquiry to scan for nearby devices. A timeout_multiplier of 8
    results in roughly 10 seconds of scanning.
    """
    radio = _get_radio_handle()

    search = BLUETOOTH_DEVICE_SEARCH_PARAMS()
    search.dwSize = ctypes.sizeof(BLUETOOTH_DEVICE_SEARCH_PARAMS)
    search.fReturnAuthenticated = False
    search.fReturnRemembered = False
    search.fReturnConnected = False
    search.fReturnUnknown = True
    search.fIssueInquiry = True
    search.cTimeoutMultiplier = timeout_multiplier
    search.hRadio = radio if radio else wintypes.HANDLE(0)

    info = BLUETOOTH_DEVICE_INFO()
    info.dwSize = ctypes.sizeof(BLUETOOTH_DEVICE_INFO)

    devices: list[BluetoothDevice] = []
    h_find = _bt.BluetoothFindFirstDevice(ctypes.byref(search), ctypes.byref(info))
    if not h_find:
        if radio:
            _kernel32.CloseHandle(radio)
        return devices

    while True:
        dev = BluetoothDevice(
            name=info.szName,
            address=info.Address,
            connected=bool(info.fConnected),
            remembered=bool(info.fRemembered),
            authenticated=bool(info.fAuthenticated),
        )
        if dev.is_dualsense() and not dev.paired:
            devices.append(dev)

        info = BLUETOOTH_DEVICE_INFO()
        info.dwSize = ctypes.sizeof(BLUETOOTH_DEVICE_INFO)
        if not _bt.BluetoothFindNextDevice(h_find, ctypes.byref(info)):
            break

    _bt.BluetoothFindDeviceClose(h_find)
    if radio:
        _kernel32.CloseHandle(radio)
    return devices


def pair_device(address: int) -> tuple[bool, str]:
    """Pair a Bluetooth device via the Windows pairing dialog."""
    radio = _get_radio_handle()
    radio_h = radio if radio else wintypes.HANDLE(0)

    get_info = _resolve_bt_func("BluetoothGetDeviceInfo")
    get_info.argtypes = [wintypes.HANDLE, ctypes.POINTER(BLUETOOTH_DEVICE_INFO)]
    get_info.restype = wintypes.DWORD

    info = BLUETOOTH_DEVICE_INFO()
    info.dwSize = ctypes.sizeof(BLUETOOTH_DEVICE_INFO)
    info.Address = address
    get_info(radio_h, ctypes.byref(info))

    authenticate = _resolve_bt_func("BluetoothAuthenticateDeviceEx")
    authenticate.argtypes = [
        wintypes.HANDLE,
        wintypes.HANDLE,
        ctypes.POINTER(BLUETOOTH_DEVICE_INFO),
        ctypes.c_void_p,
        ctypes.c_int,
    ]
    authenticate.restype = wintypes.DWORD

    result = authenticate(
        wintypes.HANDLE(0),
        radio_h,
        ctypes.byref(info),
        None,
        BLUETOOTH_AUTHENTICATION_REQUIREMENTS.MITMProtectionNotRequiredBonding,
    )

    if radio:
        _kernel32.CloseHandle(radio)

    if result == ERROR_SUCCESS:
        return True, "Device paired successfully"
    return False, f"BluetoothAuthenticateDeviceEx failed (Error {result})"


def remove_device(address: int) -> tuple[bool, str]:
    """Remove a paired Bluetooth device by address. Returns (success, message)."""
    addr = BTH_ADDR(address)
    result = _bt.BluetoothRemoveDevice(ctypes.byref(addr))
    if result == ERROR_SUCCESS:
        return True, "Device removed successfully"
    return False, f"BluetoothRemoveDevice failed (Error {result})"
