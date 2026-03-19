from __future__ import annotations

import json
from pathlib import Path

from src.main import app

output_path = Path(__file__).resolve().parents[1] / "openapi.json"
output_path.write_text(json.dumps(app.openapi(), indent=2) + "\n", encoding="utf-8")
