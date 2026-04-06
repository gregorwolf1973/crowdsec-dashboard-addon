# CrowdSec Dashboard — Home Assistant Add-on

Echtzeit-Dashboard für CrowdSec Bans, Alerts und Decisions direkt in der Home Assistant Sidebar.

[![Release](https://img.shields.io/github/v/release/gregorwolf1973/crowdsec-dashboard-addon?style=flat-square)](https://github.com/gregorwolf1973/crowdsec-dashboard-addon/releases)
[![License](https://img.shields.io/github/license/gregorwolf1973/crowdsec-dashboard-addon?style=flat-square)](LICENSE)

---

## Installation

**Schritt 1 — Repository hinzufügen:**

[![Add Repository to Home Assistant](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fgregorwolf1973%2Fcrowdsec-dashboard-addon)

Oder manuell unter **Einstellungen → Add-ons → Add-on Store → ⋮ → Repositories**:
```
https://github.com/gregorwolf1973/crowdsec-dashboard-addon
```

**Schritt 2 — Add-on installieren:**

Nach dem Hinzufügen des Repositories erscheint **CrowdSec Dashboard** im Add-on Store. Installieren, konfigurieren und starten.

Die vollständige Einrichtungsanleitung (Machine registrieren, Bouncer Key, Sensoren etc.) findest du in der [Add-on Dokumentation](crowdsec-dashboard/README.md).

---

## Features

- **Bans / Decisions** — Lokale, CAPI und manuelle Bans auf einen Blick
- **Alerts** — Vollständige Alert-Liste mit IP, Szenario, Event-Anzahl und Zeitstempel
- **Verwaltung** — Bans einzeln oder alle auf einmal löschen
- **Suche & Filter** — Nach IP, Szenario, Herkunft filtern und sortieren
- **Statistiken** — Sidebar mit Live-Zählern für Bans, Alerts, CAPI und lokale Erkennungen
- **Auto-Refresh** — Aktualisiert automatisch alle 30 Sekunden
- **Dark / Light Mode** — Umschaltbar per Klick
- **HA Sidebar Integration** — Vollständig über Ingress eingebunden

---

## Screenshots

| Bans / Decisions | Alerts |
|---|---|
| ![Decisions](https://raw.githubusercontent.com/gregorwolf1973/crowdsec-dashboard-addon/main/crowdsec-dashboard/icon.png) | ![Alerts](https://raw.githubusercontent.com/gregorwolf1973/crowdsec-dashboard-addon/main/crowdsec-dashboard/icon.png) |

---

## Voraussetzungen

- Home Assistant OS
- [CrowdSec Add-on](https://github.com/crowdsecurity/home-assistant-addons) installiert

---

## Support

Gefällt dir das Add-on? Über einen Kaffee freue ich mich sehr! ☕

[![Buy Me A Coffee](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://buymeacoffee.com/gregorwolf1973)

---

## Lizenz

MIT License — siehe [LICENSE](LICENSE)
