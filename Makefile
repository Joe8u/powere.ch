SHELL := /bin/bash

# Variablen (anpassbar beim Aufruf: make REL=2024-09_release)
PY  ?= python3
REL ?= 2024-08_release

.PHONY: help lp-precompute lp-release lp-all

help:
	@printf "Targets:\n"
	@printf "  make lp-precompute [PY=python]\n"
	@printf "  make lp-release    [REL=2024-08_release]\n"
	@printf "  make lp-all        [REL=... PY=...]\n"

# 1) Lastprofile 2024 interpolieren (raw -> processed/2024/*.csv)
lp-precompute:
	@$(PY) processing/lastprofile/jobs/precompute_lastprofile_2024.py

# 2) Curated Release bauen (Manifest + current)
lp-release:
	@./scripts/release_lastprofile.sh $(REL)

# 3) Beides in einem Rutsch
lp-all: lp-precompute lp-release

.PHONY: survey-q1
survey-q1:
	@$(PY) processing/survey/jobs/preprocess_q1_age.py

.PHONY: survey-q2
survey-q2:
	@$(PY) processing/survey/jobs/preprocess_q2_gender.py

.PHONY: survey-q3
survey-q3:
	@$(PY) processing/survey/jobs/preprocess_q3_household_size.py

.PHONY: survey-q4
survey-q4:
	@$(PY) processing/survey/jobs/preprocess_q4_accommodation.py