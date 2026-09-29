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
"""Phase 5D Unified Crop Problem & Disease Advisory Pipeline.

Orchestrates the complete end-to-end flow:
1. Farmer Query Validation
2. Deterministic Knowledge Retrieval over AgriculturalKnowledgeCorpus
3. Optional Environmental Context Ingestion
4. Controlled Gemini Advisory Service
5. Strict Multi-Stage Validation
6. Automated Deterministic Fallback on Gemini/Schema/Safety Failure

Architectural Invariants:
- Zero Live Calls in Testing: Completely testable offline with fake clients.
- Clean Fallback Boundary: Only catches controlled Step 3 service errors.
- Read-Only Context: Never mutates input context, corpus, or assessments.
"""

import logging

from app.assessment.gemini_service import GeminiModelClient
from app.assessment.gemini_types import GeminiAssessmentContext
from app.assessment.types import AgriculturalAssessment
from app.disease.corpus import DEFAULT_CORPUS, AgriculturalKnowledgeCorpus
from app.disease.fallback import generate_deterministic_crop_advisory
from app.disease.retriever import retrieve_knowledge
from app.disease.service import (
    CropProblemAdvisoryError,
    generate_crop_problem_advisory as call_gemini_service,
)
from app.disease.types import CropProblemAdvisory

logger = logging.getLogger(__name__)


def run_crop_problem_pipeline(
    farmer_query: str,
    corpus: AgriculturalKnowledgeCorpus = DEFAULT_CORPUS,
    environmental_context: AgriculturalAssessment | GeminiAssessmentContext | str | None = None,
    language: str = "en",
    client: GeminiModelClient | None = None,
    model: str | None = None,
    top_k: int = 5,
    min_retrieval_score: float = 1.0,
) -> CropProblemAdvisory:
    """Executes the Phase 5D Crop Problem & Disease Advisory pipeline with automated fallback.

    Args:
        farmer_query: Free-text farmer question or visual symptom description.
        corpus: AgriculturalKnowledgeCorpus containing verified reference records (defaults to DEFAULT_CORPUS).
        environmental_context: Optional Phase 5B/5C environmental assessment or summary.
        language: Target natural language code ('en' or 'hi').
        client: Optional GeminiModelClient for dependency injection.
        model: Optional model identifier.
        top_k: Maximum number of knowledge entries to retrieve.
        min_retrieval_score: Minimum deterministic retrieval ranking score.

    Returns:
        CropProblemAdvisory: Validated advisory payload (is_fallback=False if Gemini succeeded,
        is_fallback=True if fallback was triggered).

    Raises:
        ValueError: If farmer_query is empty or whitespace-only.
    """
    # 1. Validate Input Query
    if not farmer_query or not farmer_query.strip():
        raise ValueError("farmer_query must not be empty or whitespace-only")

    # 2. Deterministic Knowledge Retrieval
    retrieved_results = retrieve_knowledge(
        query=farmer_query,
        corpus=corpus,
        top_k=top_k,
        min_score=min_retrieval_score,
    )

    # 3. Handle Optional Environmental Context safely
    safe_env_context = environmental_context

    # 4. Invoke Controlled Gemini Service with Automated Deterministic Fallback
    try:
        advisory = call_gemini_service(
            farmer_query=farmer_query,
            retrieved_knowledge=retrieved_results,
            environmental_context=safe_env_context,
            language=language,
            client=client,
            model=model,
        )
        return advisory

    except CropProblemAdvisoryError as exc:
        logger.warning(
            "Gemini crop advisory service encountered controlled failure (%s: %s). "
            "Routing to pure-Python deterministic safe fallback.",
            type(exc).__name__,
            exc,
        )
        return generate_deterministic_crop_advisory(
            farmer_query=farmer_query,
            retrieved_results=retrieved_results,
            corpus=corpus,
            environmental_context=safe_env_context,
            language=language,
        )
