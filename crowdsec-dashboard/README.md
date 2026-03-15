# CrowdSec Dashboard — Home Assistant Add-on

Echtzeit-Dashboard für CrowdSec Bans, Alerts und Decisions mit voller Verwaltung direkt in der HA Sidebar.

## Features

- 🛡 **Lokale Bans** anzeigen (eigene Engine)
- 🌐 **CAPI Community Bans** anzeigen (15.000+ IPs)
- ⚠️ **Alerts** mit Detail-Ansicht
- 🗑 **Bans löschen** (einzeln oder alle) - noch in Arbeit, funktioniert noch nicht
- 🔍 **Suche** nach IP, Szenario, Herkunft
- 🔄 **Auto-Refresh** alle 30 Sekunden
- 📊 **Statistiken** in der Sidebar
- ✅ **HA Sidebar Integration** via Ingress

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

Die Dashboard-Machine muss in der **persistenten** CrowdSec DB registriert werden. Im HA Terminal:

```bash
docker exec addon_424ccef4_crowdsec cscli \
  --config /config/.storage/crowdsec/config/config.yaml \
  machines add crowdsec-dashboard --password dashboard123 --force
```

Prüfen ob erfolgreich:
```bash
sqlite3 /config/.storage/crowdsec/data/crowdsec.db \
  "SELECT machine_id, is_validated FROM machines WHERE machine_id='crowdsec-dashboard';"
```
Erwartete Ausgabe: `crowdsec-dashboard|1`

### Schritt 3: Bouncer API Key erstellen

```bash
docker exec addon_424ccef4_crowdsec cscli bouncers add crowdsec-dashboard-bouncer
```

Den ausgegebenen Key notieren — er wird in Schritt 5 benötigt.

### Schritt 4: CrowdSec Collections installieren

```bash
docker exec addon_424ccef4_crowdsec cscli \
  --config /config/.storage/crowdsec/config/config.yaml \
  hub update

docker exec addon_424ccef4_crowdsec cscli \
  --config /config/.storage/crowdsec/config/config.yaml \
  collections install crowdsecurity/nginx

docker exec addon_424ccef4_crowdsec cscli \
  --config /config/.storage/crowdsec/config/config.yaml \
  collections install crowdsecurity/nginx-proxy-manager

docker exec addon_424ccef4_crowdsec cscli \
  --config /config/.storage/crowdsec/config/config.yaml \
  collections install crowdsecurity/http-cve
```

### Schritt 5: Add-on installieren und konfigurieren

1. Im Add-on Store **CrowdSec Dashboard** installieren
2. Konfiguration anpassen:

```yaml
crowdsec_url: "http://424ccef4-crowdsec:8080"
machine_id: "crowdsec-dashboard"
machine_password: "dashboard123"
bouncer_api_key: "DEIN_KEY_AUS_SCHRITT_3"
log_level: "info"
```

3. **"In der Seitenleiste anzeigen"** aktivieren
4. Add-on starten

### Schritt 6: NPM Log-Forwarder einrichten (für lokale Bans)

Damit CrowdSec Angriffe auf deinen Nginx Proxy Manager erkennt und lokal bannt, müssen die NPM-Logs weitergeleitet werden.

Erstelle folgendes Script im `startup.d` Ordner (benötigt **Run On Startup.d** Add-on):

```bash
cat > /config/startup.d/crowdsec-npm-forwarder.sh << 'EOF'
#!/bin/bash
sleep 30
touch /config/.storage/crowdsec/2fauth.log
touch /config/.storage/crowdsec/npm.log
chmod 666 /config/.storage/crowdsec/2fauth.log
chmod 666 /config/.storage/crowdsec/npm.log
docker logs -f addon_a0d7b954_nginxproxymanager >> /config/.storage/crowdsec/npm.log 2>&1 &
EOF
chmod +x /config/startup.d/crowdsec-npm-forwarder.sh
```

Dann einmalig manuell starten:
```bash
/config/startup.d/crowdsec-npm-forwarder.sh &
```

### Schritt 7: CrowdSec acquis.yaml prüfen

```bash
cat /config/.storage/crowdsec/config/acquis.yaml
```

Die Datei sollte einen Eintrag für `npm.log` enthalten:
```yaml
---
source: file
filenames:
  - /config/.storage/crowdsec/npm.log
labels:
  type: nginx
```

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
       │
       ▼ (startup.d Script)
/config/.storage/crowdsec/npm.log
       │
       ▼
CrowdSec Engine → Alerts → Decisions (lokale Bans)
```

---

## Nach einem Neustart

Nach jedem HA-Neustart werden folgende Dinge automatisch wiederhergestellt:
- ✅ NPM Log-Forwarder (via `startup.d`)
- ✅ CrowdSec Machine (in persistenter DB)
- ✅ Bouncer Key (in persistenter DB)
- ✅ Collections (in persistenter DB)

Falls der JWT-Login fehlschlägt (401 in den Logs), Machine neu registrieren:
```bash
docker exec addon_424ccef4_crowdsec cscli \
  --config /config/.storage/crowdsec/config/config.yaml \
  machines add crowdsec-dashboard --password dashboard123 --force
```

---

## Troubleshooting

### Dashboard zeigt "Keine Einträge"
```bash
ha apps logs 54b27e84_crowdsec_dashboard | tail -20
```

### JWT Token Fehler (401)
Machine neu registrieren (siehe "Nach einem Neustart")

### Bouncer Key ungültig (403)
```bash
docker exec addon_424ccef4_crowdsec cscli bouncers delete crowdsec-dashboard-bouncer
docker exec addon_424ccef4_crowdsec cscli bouncers add crowdsec-dashboard-bouncer
```
Neuen Key in Add-on Konfiguration eintragen, neu starten.

### Keine lokalen Bans
Prüfen ob Log-Forwarder läuft:
```bash
ps aux | grep "docker logs" | grep -v grep
```
Prüfen ob Logs ankommen:
```bash
tail -5 /config/.storage/crowdsec/npm.log
```

### Collections nach Neustart weg
Collections müssen mit `--config` Flag installiert werden (persistente DB):
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
    └── rootfs/
        └── app/
            ├── app.py        ← Flask Backend
            └── index.html    ← Dashboard UI
```
