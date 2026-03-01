# DualSense Bluetooth Helper

A Windows utility for managing DualSense wireless controller Bluetooth connections.

## About

If you use a DualSense controller with both a PS5 and a Windows PC, you've likely
run into this: after pairing the controller back to your PS5, Windows refuses to
reconnect it. The controller shows up as "paired" in Windows Bluetooth settings
but won't actually connect, or doesn't appear at all.

This happens because Windows leaves behind ghost entries -- in the Bluetooth
device list, in Device Manager, and deep in the registry. These stale records
prevent a clean re-pairing. The standard "Remove device" in Windows Settings
often doesn't clean up everything, leaving you stuck.

## What This Tool Does

DualSense Bluetooth Helper provides a complete cleanup and re-pairing workflow:

- **Scan** -- Finds all paired DualSense controllers and discovers new ones in
  pairing mode (~10 second Bluetooth inquiry)
- **Remove / Remove All** -- Removes controller pairings at three levels:
  1. Bluetooth API (`BluetoothRemoveDevice`)
  2. Device Manager (PnP device removal via `pnputil`)
  3. Registry (cleans `BTHPORT\Parameters\Devices` and `BTHENUM` entries)
- **Pair** -- Pairs a discovered controller via `BluetoothAuthenticateDeviceEx`

## Usage

1. Run the tool as administrator (it will prompt for elevation)
2. Click **Scan** to find paired controllers and discover new ones
3. To clean up a broken pairing: select the controller and click **Remove**
4. To pair a new controller: put it in pairing mode (hold PS + Create until the
   light bar blinks), click **Scan**, select it, then click **Pair**

Click **Pairing Help** for the official PlayStation guide on entering pairing mode.

## Installation

Download `dualsense-util.exe` from the
[latest release](../../releases/latest) and run it -- no Python installation
required.

### From source

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/):

```
uv run dualsense-util
```
