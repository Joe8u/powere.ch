from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime

class BaseCard(BaseModel):
    id: str                        # z.B. "code:steps/step06/.../tre05#main"
    doc_type: str                  # "toc_node" | "code_unit" | "dataset_summary" | "concept_card" | "result_snapshot"
    title: str
    path: Optional[str] = None     # Repo-Path (für code/dataset)
    step: Optional[str] = None     # "step06_sozio_technisches_simulationsmodell"
    module: Optional[str] = None   # "simulation" / "dr_windows" / …
    tags: List[str] = []
    summary: Optional[str] = None  # 2–5 Sätze, was/wieso
    lang: str = "de"
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    source_hash: Optional[str] = None  # sha256 des Files (Stale-Check)
    embed_fields: List[str] = ["title","summary","body"]  # was in Embedding geht
    body: Optional[str] = None     # Fließtext/Erklärung

class CodeUnitCard(BaseCard):
    doc_type: str = "code_unit"
    functions: List[str] = []      # Namen oder "module-level"
    formulas: List[str] = []
    inputs: Dict[str, List[str]] = {}   # {"data_sources":[...], "params":[...]}
    outputs: List[str] = []             # Variablen/Dateien
    defaults: Dict[str, str] = {}       # Konstanten/Defaults
    depends_on: List[str] = []          # Pfade zu anderen Modulen

class DatasetSummaryCard(BaseCard):
    doc_type: str = "dataset_summary"
    shape: Optional[str] = None         # "rows=..., cols=..."
    columns: List[str] = []
    units: Dict[str, str] = {}          # {"price_chf_kwh":"CHF/kWh"}
    sample_rows: List[Dict] = []        # 3–5 Beispielzeilen
    period: Optional[str] = None        # z.B. "2024-01..2024-12"
    file_on_disk: Optional[str] = None  # relativer Pfad

class TocNodeCard(BaseCard):
    doc_type: str = "toc_node"
    children: List[str] = []            # IDs der Kinder (weitere Karten)

class ConceptCard(BaseCard):
    doc_type: str = "concept_card"
    synonyms: List[str] = []
    definition: Optional[str] = None