# powere.ch – Website, API & AI-Guide (RAG) + DR-Simulationen

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-🚀-009688)]()
[![Astro](https://img.shields.io/badge/Astro-web-orange.svg)]()
[![Qdrant](https://img.shields.io/badge/VectorDB-Qdrant-6f42c1.svg)]()

Monorepo für **powere.ch**:

- **Web** – Statische Seite mit Astro/Starlight (`apps/web`)
- **API** – FastAPI-Backend mit RAG (Qdrant + Embeddings) (`apps/api`)
- **AI-Guide (RAG)** – Endpoints: `apps/api/app/routers/ai_guide_router.py`
- **Modelle/Steps** – DR-Fenster, Flex-Simulationen (`steps/**`)

Ziel: Daten + Modelle + Erklärtexte konsistent bereitstellen – inkl. Chat-Suche über eigene Inhalte (RAG) und reproduzierbaren **Demand-Response**-Simulationen.

---

## Inhaltsverzeichnis

- [Architektur](#architektur)
- [Lokal entwickeln (Envs/Ports)](#lokal-entwickeln-envsports)
- [Deployment auf der VM](#deployment-auf-der-vm)
- [Schnellstart (lokal)](#schnellstart-lokal)
- [Produktion (Docker Compose)](#produktion-docker-compose)
- [API – Endpunkte](#api--endpunkte)
- [DR-Simulationen (tre01…tre06)](#dr-simulationen-tre01tre06)
- [Große Dateien (Git LFS)](#große-dateien-git-lfs)
- [Troubleshooting](#troubleshooting)
- [Lizenz](#lizenz)

---

## Architektur

```text
Internet ─▶ Nginx Proxy Manager (ubuntu-vm)
        ├─▶ https://www.powere.ch  → web (Nginx, Astro dist)
        └─▶ https://api.powere.ch  → api (FastAPI, RAG)
                           └─▶ Qdrant (Vector-DB)

## Lokal entwickeln (Envs/Ports)

Kurzüberblick
- API (FastAPI) lokal auf Port `8000` starten.
- Web (Astro) auf Port `4321` (oder nächster freier Port).
- Port `9000` ist in PROD belegt (VM). Lokal am besten nicht verwenden.

Wichtige Env-Variablen
- `WAREHOUSE_DATA_ROOT`: Datenwurzel für Parquet-Datasets (lokal: `repo/data`).
- `PUBLIC_API_BASE`: Basis-URL für Web-Fetches (lokal: `http://127.0.0.1:8000`).

Einmalig: lokale Env setzen
```bash
# API nutzt lokale Daten unter ./data
export WAREHOUSE_DATA_ROOT="$(pwd)/data"

# Web zeigt auf die lokale API
printf 'PUBLIC_API_BASE=http://127.0.0.1:8000\n' > apps/web/.env.local
```

Start (2 Terminals)
```bash
# Terminal 1: API aus Repo-Root starten
python -m uvicorn apps.api.app.main:app --reload --port 8000

# Terminal 2: Web-Dev-Server
npm --prefix apps/web run dev
```

Schnelltests
```bash
curl http://127.0.0.1:8000/v1/ping
curl 'http://127.0.0.1:8000/warehouse/regelenergie/tertiary?agg=hour&limit=24'
curl 'http://127.0.0.1:8000/warehouse/survey/wide?limit=5'
# Browser: http://localhost:4321/dashboard/
```

Hinweise
- Fehlen Parquet-Dateien lokal, liefern die Endpoints `[]` (kein 500).
- `WAREHOUSE_DATA_ROOT` MUSS auf das lokale `data/` zeigen, sonst sucht die API unter `/app/data` (Container-Pfad).
- In der Web-App werden relative API-Pfade verwendet (`/warehouse/...`); `PUBLIC_API_BASE` setzt die Basis-URL zentral.

## Deployment auf der VM

Pull + Rebuild (nur API)
```bash
cd /srv/repos/powere.ch
git pull
docker compose -f infra/docker-compose.prod.yml up -d --no-deps --build api
```

Web-Dist aktualisieren (Nginx dient statisch aus `apps/web/dist`)
```bash
npm --prefix apps/web ci
npm --prefix apps/web run build
```

Checks (auf der VM)
```bash
curl http://127.0.0.1:9000/v1/ping
curl 'http://127.0.0.1:9000/warehouse/regelenergie/tertiary?agg=hour&limit=24'
curl 'http://127.0.0.1:9000/warehouse/survey/wide?limit=5'
# Browser: https://www.powere.ch/dashboard/
```

## Warehouse API

- Basis (lokal): `http://127.0.0.1:8000` – in Prod via NPM/Proxy `https://api.powere.ch` (Host 9000 → Container 8000).
- Web-Frontend nutzt `PUBLIC_API_BASE` (siehe `.env.local`).

Beispiele
- Joined (mFRR × Lastprofile):
  - `GET /warehouse/joined/mfrr_lastprofile?agg=hour&columns=total_mw&limit=3`
- Lastprofile:
  - `GET /warehouse/lastprofile?year=2024&month=1&limit=3`
  - `GET /warehouse/lastprofile/columns`
  - `GET /warehouse/lastprofile/series?agg=day&columns=total`
- mFRR (tertiary):
  - `GET /warehouse/regelenergie/tertiary?agg=raw&limit=3`
  - `GET /warehouse/regelenergie/tertiary/latest_ts`
- Survey (wide):
  - `GET /warehouse/survey/wide?limit=3`

Hinweise
- Start/End in Zeitfiltern werden robust per `CAST(? AS TIMESTAMP)` verglichen.
- Fehlen Parquet-Dateien unter dem jeweiligen Glob, liefern Endpunkte `[]` (kein 500).
- Zeitfeld: Aggregationen liefern `ts` (Alias), Rohlisten `timestamp`.

Smoke-Test
```bash
API_BASE=http://127.0.0.1:8000 bash scripts/smoke_warehouse.sh
```

Ports (VM)
- Host `9000` → Container `8000` (Compose Mapping).
- `WAREHOUSE_DATA_ROOT=/app/data` (Volume: `/srv/repos/powere.ch/data:/app/data:ro`).
