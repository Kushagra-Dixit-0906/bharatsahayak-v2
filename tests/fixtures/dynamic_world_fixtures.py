# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Helper loader for deterministic offline Dynamic World JSON fixtures (Phase 3C, DEC-021)."""

import json
from pathlib import Path
from typing import Any

FIXTURES_DIR = Path(__file__).parent / "dynamic_world"


def load_dynamic_world_fixture(filename: str) -> dict[str, Any]:
    """Loads and parses a Dynamic World offline test fixture by filename."""
    file_path = FIXTURES_DIR / filename
    if not file_path.exists():
        raise FileNotFoundError(f"Dynamic World fixture '{filename}' not found at {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)
