# CrowdSec Dashboard

Zeigt alle gebannten IPs und Alerts von CrowdSec an und erlaubt das Aufheben von Bans per Knopfdruck.

## Installation

1. Repository in Home Assistant hinzufügen
2. Add-on installieren
3. API Key konfigurieren (aus CrowdSec Add-on)
4. Starten

## Konfiguration

| Option | Beschreibung |
|--------|-------------|
| crowdsec_url | URL der CrowdSec API (Standard: http://424ccef4-crowdsec:8080) |
| crowdsec_api_key | API Key aus dem CrowdSec Add-on |

## API Key ermitteln

Im CrowdSec Terminal:
```bash
cscli bouncers list
```
