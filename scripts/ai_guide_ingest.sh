#!/usr/bin/env bash
set -euo pipefail
API="${API:-http://127.0.0.1:8000}"
python - "$API" <<'PY'
import sys, json, glob, os, urllib.request
api=sys.argv[1]
globs=[
"step_1_raw_data/**/README.md",
"step_2_preprocessing/**/*.py",
"step_2_preprocessing/README.md",
"step_3_processed_data/**/SCHEMA.md",
"step_3_processed_data/README.md",
"step_4_datenloader/**/*.py",
"step_4_datenloader/README.md",
"step_5_analyse/**/*.{md,py,ipynb}",
"step_6_Sozio-technisches_Simulationsmodell/**/*.{md,py}",
"docs/ai-guide/**/*.md",
]
files=set()
for g in globs:
  files.update(glob.glob(g, recursive=True))
docs=[]
for p in sorted(files):
  if any(s in p for s in (".ipynb_checkpoints","__pycache__")): continue
  if p.endswith(".csv"): continue
  try:
    with open(p,"r",encoding="utf-8") as f: content=f.read()
  except Exception: 
    continue
  docs.append({"id":p,"title":p,"url":None,"content":content})
req=urllib.request.Request(api+"/v1/ingest", data=json.dumps(docs).encode(), headers={"Content-Type":"application/json"})
print("posting",len(docs),"docs to",api)
print(urllib.request.urlopen(req).read().decode())
PY
