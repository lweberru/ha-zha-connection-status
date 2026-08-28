# ZHA Connection Status

[English](README.md)

Eine Home-Assistant-Custom-Integration, die die Verfügbarkeit von ZHA- und Philips-Hue-Zigbee-Geräten überwacht. Sie erstellt eine Benachrichtigung im Home-Assistant-Frontend und informiert beliebig viele Mobile-App-Geräte, wenn ein Gerät nicht mehr erreichbar ist. Beim Reconnect wird die Frontend-Benachrichtigung entfernt; ausgewählte Geräte erhalten optional eine Erfolgsmeldung.

## Funktionen

- Überwacht ZHA- und Philips-Hue-Entities auf die Zustände `unavailable` und `unknown`.
- Wartet vor der Offline-Meldung eine einstellbare Zeit (standardmäßig 30 Sekunden), damit kurze Aussetzer nicht stören.
- Erstellt genau eine persistente Frontend-Benachrichtigung pro Zigbee-Gerät.
- Entfernt diese Benachrichtigung bei erfolgreichem Reconnect automatisch.
- Stellt die Überwachung nach Home-Assistant-Neustarts und Integrationsupdates sauber wieder her, ohne Mobile-Meldungen zu duplizieren.
- Unterstützt beliebig viele `notify`-Dienste und getrennte Empfängerlisten für Offline- und Online-Meldungen.
- Fügt einen diagnostischen Sensor **Verbindungsstatus** hinzu. Sein Zustand ist die Zahl der Geräte, bei denen alle relevanten Entities nicht verfügbar sind; seine Attribute zeigen überwachte ZHA-/Hue-Geräte, batteriebetriebene Geräte und Geräte mit niedrigem Batteriestand. Szenen, Buttons, Events und Update-Entities werden für die Verbindungsprüfung ausgeschlossen.

## Installation über HACS

1. Öffne HACS in Home Assistant und gehe zu **Integrationen**.
2. Wähle das Drei-Punkte-Menü, dann **Benutzerdefinierte Repositories**.
3. Füge `https://github.com/weberruss/ha-zha-connection-status` als Kategorie **Integration** hinzu.
4. Suche nach **ZHA Connection Status**, installiere die Integration und starte Home Assistant neu.
5. Gehe zu **Einstellungen > Geräte & Dienste > Integration hinzufügen** und füge **ZHA Connection Status** hinzu.

## Konfiguration

Wähle bei der Einrichtung aus den verfügbaren `notify`-Diensten.

- **Empfänger für Offline-Meldungen:** Diese Geräte bekommen stets die Offline-Meldung.
- **Empfänger für Online-Meldungen:** Nur diese Geräte erhalten die Meldung, dass das Gerät wieder erreichbar ist. So lässt sich die Erfolgsmeldung pro Mobilgerät ein- oder ausschalten.
- **Wartezeit:** Zeit in Sekunden, die ein Gerät nicht erreichbar sein muss, bevor eine Meldung gesendet wird.
- **Sprache der Benachrichtigungen:** Sprache der Frontend- und Mobile-Benachrichtigungen. Englisch ist die Vorgabe, Deutsch steht ebenfalls zur Auswahl.
- **Schwellenwert für niedrigen Batteriestand:** Bei einem Batteriestand an oder unter diesem Prozentwert nennt die Offline-Meldung eine schwache Batterie als mögliche Ursache. Andernfalls wird der letzte Batteriestand angezeigt, sofern verfügbar. Vorgabe: 20 %.

Die Einstellung lässt sich nach der Einrichtung über **Konfigurieren** in der Integration ändern.

## Voraussetzungen

- Home Assistant 2024.4 oder neuer
- Die offizielle [ZHA-Integration](https://www.home-assistant.io/integrations/zha/) und/oder [Philips-Hue-Integration](https://www.home-assistant.io/integrations/hue/)
- Mindestens ein eingerichteter Notify-Dienst, etwa die Home-Assistant-Companion-App

## Entwicklung

Die Integration liegt unter `custom_components/zha_connection_status`. Für eine lokale Installation kopiere diesen Ordner nach `<config>/custom_components/` und starte Home Assistant neu.