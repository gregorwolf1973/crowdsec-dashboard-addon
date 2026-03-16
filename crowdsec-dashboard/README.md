# CrowdSec Dashboard — Home Assistant Add-on

Echtzeit-Dashboard für CrowdSec Bans, Alerts und Decisions mit voller Verwaltung direkt in der HA Sidebar.

## Features

- 🛡 **Lokale Bans** anzeigen (eigene Engine)
- 🌐 **CAPI Community Bans** anzeigen
- ⚠️ **Alerts** mit Detail-Ansicht und Ziel-URL
- 🗑 **Bans löschen** (einzeln, alle, nur lokale, per IP)
- 🔍 **Suche** nach IP, Szenario, Herkunft
- 🔄 **Auto-Refresh** alle 30 Sekunden
- 📊 **Statistiken** in der Sidebar
- ☀️/🌙 **Dark/Light Mode** Toggle
- ✅ **HA Sidebar Integration** via Ingress
- 📡 **HA Sensoren** für lokale Bans, aktive Bans, Alerts

---

## Voraussetzungen

- Home Assistant OS
- CrowdSec Add-on installiert (`424ccef4_crowdsec`)
- Nginx Proxy Manager Add-on (optional, für lokale Bans)
- Run On Startup.d Add-on (für persistenten Log-Forwarder)

---

## Installation

### Schritt 1: Repository in HA hinzufügen

**Einstellungen → Add-ons → Add-on Store → ⋮ → Repositories**

URL hinzufügen:
```
https://github.com/gregorwolf1973/crowdsec-dashboard-addon
```

### Schritt 2: CrowdSec Machine registrieren

```bash
docker exec addon_424ccef4_crowdsec cscli \
  --config /config/.storage/crowdsec/config/config.yaml \
  machines add crowdsec-dashboard --password dashboard123 --force
```

Prüfen:
```bash
sqlite3 /config/.storage/crowdsec/data/crowdsec.db \
  "SELECT machine_id, is_validated FROM machines WHERE machine_id='crowdsec-dashboard';"
```
Erwartete Ausgabe: `crowdsec-dashboard|1`

### Schritt 3: Bouncer API Key erstellen

```bash
docker exec addon_424ccef4_crowdsec cscli \
  --config /config/.storage/crowdsec/config/config.yaml \
  bouncers add crowdsec-dashboard-bouncer
```

Den ausgegebenen Key notieren.

### Schritt 4: CrowdSec Collections installieren

```bash
docker exec addon_424ccef4_crowdsec cscli \
  --config /config/.storage/crowdsec/config/config.yaml \
  hub update

docker exec addon_424ccef4_crowdsec cscli \
  --config /config/.storage/crowdsec/config/config.yaml \
  collections install crowdsecurity/nginx \
  crowdsecurity/nginx-proxy-manager \
  crowdsecurity/http-cve \
  crowdsecurity/nextcloud
```

### Schritt 5: Add-on installieren und konfigurieren

In der Add-on Konfiguration:
```yaml
crowdsec_url: "http://424ccef4-crowdsec:8080"
machine_id: "crowdsec-dashboard"
machine_password: "dashboard123"
bouncer_api_key: "DEIN_KEY_AUS_SCHRITT_3"
log_level: "info"
```

**"In der Seitenleiste anzeigen"** aktivieren → Add-on starten.

### Schritt 6: NPM Log-Forwarder einrichten

Erstelle `/config/startup.d/crowdsec_logs.sh` (benötigt **Run On Startup.d** Add-on):

```bash
cat > /config/startup.d/crowdsec_logs.sh << 'EOF'
#!/bin/bash
sleep 30
touch /config/.storage/crowdsec/2fauth.log
touch /config/.storage/crowdsec/npm.log
chmod 666 /config/.storage/crowdsec/2fauth.log
chmod 666 /config/.storage/crowdsec/npm.log
docker logs -f addon_a0d7b954_nginxproxymanager >> /config/.storage/crowdsec/npm.log 2>&1 &
docker logs -f addon_57fef649_2fauth >> /config/.storage/crowdsec/2fauth.log 2>&1 &
EOF
chmod +x /config/startup.d/crowdsec_logs.sh
/config/startup.d/crowdsec_logs.sh &
```

### Schritt 7: acquis.yaml prüfen

```bash
cat /config/.storage/crowdsec/config/acquis.yaml
```

Sollte enthalten:
```yaml
---
source: file
filenames:
  - /config/.storage/crowdsec/npm.log
labels:
  type: nginx
```

---

## Home Assistant Sensoren & Steuerung

### Sensoren in configuration.yaml

Port jeweils anpassen

```yaml
sensor:
  - platform: rest
    name: "CrowdSec Lokale Bans"
    resource: "http://172.30.33.4:8099/api/metrics"
    value_template: "{{ value_json.by_origin.crowdsec | default(0) }}"
    scan_interval: 60

  - platform: rest
    name: "CrowdSec Aktive Bans"
    resource: "http://172.30.33.4:8099/api/metrics"
    value_template: "{{ value_json.total_decisions | default(0) }}"
    scan_interval: 60

  - platform: rest
    name: "CrowdSec Alerts"
    resource: "http://172.30.33.4:8099/api/metrics"
    value_template: "{{ value_json.total_alerts | default(0) }}"
    scan_interval: 60
```

### REST Commands in configuration.yaml

```yaml
rest_command:
  # Einzelnen Ban per ID löschen
  crowdsec_delete_ban:
    url: "http://172.30.33.4:8099/api/decisions/{{ decision_id }}/remove"
    method: GET

  # Alle Bans löschen (inkl. CAPI - kommen nach 2h zurück)
  crowdsec_delete_all_bans:
    url: "http://172.30.33.4:8099/api/decisions/remove-all"
    method: GET

  # Nur lokale Bans löschen (origin: crowdsec/cscli)
  crowdsec_delete_local_bans:
    url: "http://172.30.33.4:8099/api/decisions/local/remove-all"
    method: GET

  # Ban für spezifische IP löschen
  crowdsec_delete_ip:
    url: "http://172.30.33.4:8099/api/decisions/ip/{{ ip }}/remove"
    method: GET
```

### Lovelace Karte

```yaml
type: entities
title: CrowdSec
entities:
  - entity: sensor.crowdsec_aktive_bans
    name: Aktive Bans
  - entity: sensor.crowdsec_lokale_bans
    name: Lokale Bans
  - entity: sensor.crowdsec_alerts
    name: Alerts
  - type: button
    name: Lokale Bans löschen
    tap_action:
      action: call-service
      service: rest_command.crowdsec_delete_local_bans
```

---
## Manuel eine IP Sperren

Im Terminal
```bash
docker exec addon_424ccef4_crowdsec cscli --config /config/.storage/crowdsec/config/config.yaml decisions add --ip 1.2.3.4 --duration 1h --reason "test"
```

## API Endpoints

| Endpoint | Methode | Beschreibung |
|----------|---------|--------------|
| `/api/decisions` | GET | Alle aktiven Decisions |
| `/api/alerts` | GET | Alerts (max 500) |
| `/api/metrics` | GET | Statistiken |
| `/api/decisions/{id}/remove` | GET | Ban per ID löschen |
| `/api/decisions/remove-all` | GET | Alle Bans löschen |
| `/api/decisions/local/remove-all` | GET | Nur lokale Bans löschen |
| `/api/decisions/ip/{ip}/remove` | GET | Ban per IP löschen |

---

## Architektur

```
HA Sidebar (Ingress)
       │
       ▼
Flask Backend (Port 8099)
  ├── Bouncer API Key  → GET  /v1/decisions  (Lesen)
  └── Machine JWT      → GET  /v1/alerts     (Lesen)
                       → DELETE /v1/decisions (Löschen)
       │
       ▼
CrowdSec LAPI (http://424ccef4-crowdsec:8080)

NPM Docker Logs
       │ (startup.d Script)
       ▼
/config/.storage/crowdsec/npm.log
       │
       ▼
CrowdSec Engine → Alerts → Decisions (lokale Bans)
```

---

## Nach einem Neustart

Nach jedem HA-Neustart werden automatisch wiederhergestellt:
- ✅ NPM Log-Forwarder (via `startup.d`)
- ✅ CrowdSec Machine (in persistenter DB)
- ✅ Bouncer Key (in persistenter DB)
- ✅ Collections (in persistenter DB)

Falls JWT-Login fehlschlägt (401 in Logs):
```bash
docker exec addon_424ccef4_crowdsec cscli \
  --config /config/.storage/crowdsec/config/config.yaml \
  machines add crowdsec-dashboard --password dashboard123 --force
```

Falls Firewall Bouncer fehlschlägt (access forbidden):
```bash
docker exec addon_424ccef4_crowdsec cscli \
  --config /config/.storage/crowdsec/config/config.yaml \
  bouncers add firewall-bouncer
```
→ Key in HA Firewall Bouncer Add-on Konfiguration eintragen.

---

## Troubleshooting

### Dashboard zeigt keine Daten
```bash
ha apps logs 54b27e84_crowdsec_dashboard | tail -20
```

### Keine lokalen Bans
```bash
# Log-Forwarder läuft?
ps aux | grep "docker logs" | grep -v grep
# Logs ankommen?
tail -5 /config/.storage/crowdsec/npm.log
# CrowdSec verarbeitet Logs?
docker exec addon_424ccef4_crowdsec cscli \
  --config /config/.storage/crowdsec/config/config.yaml metrics | head -10
```

### Collections nach Neustart weg
```bash
docker exec addon_424ccef4_crowdsec cscli \
  --config /config/.storage/crowdsec/config/config.yaml \
  collections list
```

---

## Dateistruktur

```
crowdsec-dashboard-addon/
├── repository.yaml
└── crowdsec-dashboard/
    ├── config.yaml
    ├── Dockerfile
    ├── build.yaml
    ├── README.md
    └── rootfs/app/
        ├── app.py        ← Flask Backend
        └── index.html    ← Dashboard UI
```
