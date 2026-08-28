# ZHA Connection Status

[Deutsch](README.de.md)

A Home Assistant custom integration that monitors the availability of ZHA and Philips Hue Zigbee devices. It creates a notification in the Home Assistant frontend and notifies any number of mobile devices when a device becomes unavailable. When the device reconnects, the frontend notification is dismissed and selected devices can optionally receive a recovery notification.

## Features

- Uses ZHA's own device-level `available` status, the same source as the ZHA device list, instead of individual entity states such as LQI or RSSI.
- Uses Philips Hue's Zigbee connectivity status. Devices without a current Hue connectivity record are not reported as unavailable based on stale entity states.
- Waits for a configurable period before sending an offline notification (30 seconds by default), avoiding alerts for short interruptions.
- Creates one persistent frontend notification per Zigbee device.
- Automatically dismisses the notification once the device reconnects.
- Restores monitoring cleanly after Home Assistant restarts and integration updates without duplicating mobile alerts.
- Supports any number of `notify` services, with separate recipient lists for offline and recovery notifications.
- Adds a diagnostic **Connection status** sensor. Its state is the number of unavailable devices; its attributes show monitored ZHA/Hue devices, battery-powered devices, and low-battery devices. It updates immediately on state changes and reconciles every minute as a fallback.

## Installation through HACS

1. Open HACS in Home Assistant and go to **Integrations**.
2. Select the three-dot menu, then **Custom repositories**.
3. Add `https://github.com/weberruss/ha-zha-connection-status` with the **Integration** category.
4. Search for **ZHA Connection Status**, install the integration, and restart Home Assistant.
5. Go to **Settings > Devices & services > Add integration** and add **ZHA Connection Status**.

## Configuration

Choose from the available `notify` services during setup.

- **Offline notification recipients:** These devices always receive the offline notification.
- **Online notification recipients:** Only these devices receive the notification that the device is available again. This enables recovery notifications for each mobile device individually.
- **Wait time:** The number of seconds a device must be unavailable before a notification is sent.
- **Notification language:** The language of frontend and mobile notifications. English is the default; German is also available.
- **Low battery threshold:** The battery percentage at or below which the offline notification identifies a low battery as a possible cause. The latest battery level is otherwise shown when available. Default: 20%.

You can change these settings later by selecting **Configure** for the integration.

## Requirements

- Home Assistant 2024.4 or newer
- The official [ZHA](https://www.home-assistant.io/integrations/zha/) and/or [Philips Hue](https://www.home-assistant.io/integrations/hue/) integration
- At least one configured notify service, such as the Home Assistant Companion App

## Development

The integration resides in `custom_components/zha_connection_status`. For a local installation, copy this directory to `<config>/custom_components/` and restart Home Assistant.
