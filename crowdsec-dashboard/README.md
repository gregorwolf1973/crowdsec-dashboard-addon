# CrowdSec Dashboard — Home Assistant Add-on

Echtzeit-Dashboard für CrowdSec Bans, Alerts und Decisions mit voller Verwaltung über die HA Sidebar.

## Features

- **Alle aktiven Bans** anzeigen (lokal & CAPI Community)
- **Alerts** mit Detail-Ansicht
- **Bans per Knopfdruck löschen** (einzeln oder alle)
- **Suche** nach IP, Szenario, Herkunft
- **Auto-Refresh** alle 30 Sekunden
- **HA Sidebar Integration** via Ingress (kein separater Port nötig)
- **JWT Auth** automatisch – Token wird beim Start geholt und erneuert

## Architektur

```
HA Sidebar (Ingress)
       │
       ▼
Flask Backend (Port 8099)
  ├── GET  /              → HTML Dashboard
  ├── GET  /api/decisions → Aktive Bans
  ├── GET  /api/alerts    → Alerts
  ├── DELETE /api/decisions/{id}  → Einzelnen Ban löschen
  ├── DELETE /api/decisions/all   → Alle Bans löschen
  └── GET  /api/metrics   → Aggregierte Statistiken
       │
       ▼
CrowdSec LAPI (http://424ccef4-crowdsec:8080)
  └── JWT Auth via /v1/watchers/login
```

## Installation

### 1. Add-on Repository hinzufügen

In Home Assistant:
- `Einstellungen → Add-ons → Add-on Store → ⋮ → Repositories`
- URL deines Repos hinzufügen (oder lokalen Pfad)

### 2. Machine Credentials in CrowdSec DB eintragen

Die Machine muss in der **persistenten** SQLite DB registriert sein:

```bash
# Im CrowdSec Container:
docker exec -it addon_424ccef4_crowdsec bash

# SQLite DB bearbeiten:
sqlite3 /config/.storage/crowdsec/data/crowdsec.db

-- Machine eintragen:
INSERT OR REPLACE INTO machines (machine_id, password, ipaddress, isvalid, isforced, auth_type)
VALUES (
  'crowdsec-dashboard',
  '$2y$10$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uheWG/igi',
  '127.0.0.1',
  1, 1, 'password'
);
.quit
```

Der BCrypt Hash entspricht dem Passwort `dashboard123`.

### 3. Add-on konfigurieren

In der Add-on Konfiguration:
```yaml
crowdsec_url: "http://424ccef4-crowdsec:8080"
machine_id: "crowdsec-dashboard"
machine_password: "dashboard123"
log_level: "info"
```

### 4. "In Sidebar anzeigen" aktivieren

Im Add-on unter "In der Seitenleiste anzeigen" einschalten.

## Wichtige Hinweise

### Bouncer vs. Machine Login
- **Bouncer Keys** (`X-Api-Key`): Nur Lesezugriff auf `/v1/decisions` — kein Löschen möglich
- **Machine JWT**: Voller Zugriff — Login via `/v1/watchers/login`

### CrowdSec DB Pfade
- **Temporär** (wird bei Neustart geleert): `/var/lib/crowdsec/data/crowdsec.db`
- **Persistent** (HA Add-on): `/config/.storage/crowdsec/data/crowdsec.db`

→ Machine **muss** in die persistente DB eingetragen werden!

### CORS
Da das Flask Backend alle Requests proxied (HTML + API auf gleichem Origin), gibt es **keine CORS-Probleme**.

## Entwicklung / Debugging

```bash
# Logs anzeigen:
ha addon logs local_crowdsec_dashboard

# Manuell testen (wenn Ingress aktiv):
curl http://homeassistant.local/api/hassio_ingress/.../api/health
```

## Dateistruktur

```
crowdsec-dashboard/
├── config.yaml           ← HA Add-on Konfiguration
├── Dockerfile            ← Build-Anweisungen
├── build.yaml            ← Multi-Arch Build Config
└── rootfs/
    ├── app/
    │   ├── app.py        ← Flask Backend
    │   └── index.html    ← Dashboard Frontend
    └── etc/
        ├── cont-init.d/
        │   └── crowdsec-dashboard.sh
        └── services.d/
            └── crowdsec-dashboard/
                ├── run
                └── finish
```
