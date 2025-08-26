# powere.ch – Website, API & AI-Guide (RAG) + DR-Simulationen

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-🚀-009688)]()
[![Astro](https://img.shields.io/badge/Astro-web-orange.svg)]()
[![Qdrant](https://img.shields.io/badge/VectorDB-Qdrant-6f42c1.svg)]()

Monorepo für **powere.ch**:

- **Web** – Statische Seite mit Astro/Starlight (`apps/web`)
- **API** – FastAPI-Backend mit RAG (Qdrant + Embeddings) (`apps/api`)
- **AI-Guide (RAG)** – Endpoints: `apps/api/app/routers/ai_guide_router.py
- **Modelle/Steps** – DR-Fenster, Flex-Simulationen (`steps/**`)

Ziel: Daten + Modelle + Erklärtexte konsistent bereitstellen – inkl. Chat-Suche über eigene Inhalte (RAG) und reproduzierbaren **Demand-Response**-Simulationen.

---

## Inhaltsverzeichnis

- [Architektur](#architektur)
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
