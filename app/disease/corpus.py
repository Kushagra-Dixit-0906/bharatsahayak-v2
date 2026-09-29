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
"""Phase 5D Agricultural Knowledge Corpus Data Structure.

Defines the container and indexing structure for verified agricultural knowledge
records and their associated legal/source provenance manifests.

Important:
- This module defines the data structure ONLY.
- It contains ZERO fabricated, guessed, or unverified documents.
- The default corpus is empty until sources are individually verified.
- ZERO retrieval logic, vector embeddings, or BM25 code in this module.
"""

from pydantic import BaseModel, ConfigDict, Field

from app.disease.batch1_data import BATCH1_ENTRIES, BATCH1_SOURCES
from app.disease.batch2_data import BATCH2_ENTRIES, BATCH2_SOURCES
from app.disease.types import KnowledgeEntry, KnowledgeSourceProvenance


class AgriculturalKnowledgeCorpus(BaseModel):
    """Structured registry of verified agricultural knowledge entries and source provenances."""

    sources: dict[str, KnowledgeSourceProvenance] = Field(
        default_factory=dict,
        description="Map of source_id to verified KnowledgeSourceProvenance record",
    )
    entries: list[KnowledgeEntry] = Field(
        default_factory=list,
        description="List of verified KnowledgeEntry records",
    )
    corpus_version: str = Field(
        default="1.0.0",
        description="Semantic version of this knowledge corpus release",
    )

    model_config = ConfigDict(frozen=True, extra="forbid")

    def get_source(self, source_id: str) -> KnowledgeSourceProvenance | None:
        """Retrieves a source provenance record by its source_id."""
        return self.sources.get(source_id)

    def get_entry(self, entry_id: str) -> KnowledgeEntry | None:
        """Retrieves a knowledge entry by its unique entry_id."""
        for entry in self.entries:
            if entry.entry_id == entry_id:
                return entry
        return None

    def validate_provenance_integrity(self) -> list[str]:
        """Validates that every KnowledgeEntry references a valid, registered source_id.

        Returns:
            list[str]: List of error messages for orphan entries without valid source provenance.
        """
        errors = []
        for entry in self.entries:
            if entry.source_id not in self.sources:
                errors.append(
                    f"Integrity error: KnowledgeEntry '{entry.entry_id}' references "
                    f"unregistered source_id '{entry.source_id}'"
                )
        return errors


def get_empty_corpus() -> AgriculturalKnowledgeCorpus:
    """Returns a clean, empty knowledge corpus with zero unverified entries."""
    return AgriculturalKnowledgeCorpus(
        sources={},
        entries=[],
        corpus_version="1.0.0",
    )


def get_default_corpus() -> AgriculturalKnowledgeCorpus:
    """Returns the production agricultural knowledge corpus populated with verified Batch 1 & 2 records."""
    all_sources = {**BATCH1_SOURCES, **BATCH2_SOURCES}
    all_entries = BATCH1_ENTRIES + BATCH2_ENTRIES
    return AgriculturalKnowledgeCorpus(
        sources=all_sources,
        entries=all_entries,
        corpus_version="1.2.0",
    )


# Default initial corpus: populated with verified Batch 1 & 2 agricultural knowledge
DEFAULT_CORPUS: AgriculturalKnowledgeCorpus = get_default_corpus()

