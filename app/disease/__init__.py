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
"""Phase 5D Crop Problem & Disease Advisory package.

Provides structured domain contracts, curated agricultural knowledge containers,
deterministic knowledge retrieval, grounded Gemini advisory services, and deterministic
safe fallback for crop problem identification and safe IPM advisory.
"""

from .corpus import (
    DEFAULT_CORPUS,
    AgriculturalKnowledgeCorpus,
    get_empty_corpus,
)
from .fallback import (
    generate_deterministic_crop_advisory,
)
from .pipeline import (
    run_crop_problem_pipeline,
)
from .prompt import (
    build_crop_problem_prompt,
)
from .retriever import (
    KnowledgeRetrievalResult,
    retrieve_knowledge,
    retrieve_knowledge_entries,
)
from .service import (
    AdvisoryParsingError,
    AdvisorySafetyRejectionError,
    AdvisoryValidationError,
    CropProblemAdvisoryError,
    GeminiGenerationError,
    generate_crop_problem_advisory,
    validate_advisory_payload,
)
from .types import (
    AdvisoryStatus,
    CropProblemAdvisory,
    ExpertReferralUrgency,
    KnowledgeEntry,
    KnowledgeReference,
    KnowledgeSourceProvenance,
    PathogenCategory,
    PossibleCondition,
    SafeActionCategory,
    SafeCulturalAction,
    SymptomMatchLevel,
)

__all__ = [
    "DEFAULT_CORPUS",
    "AdvisoryParsingError",
    "AdvisorySafetyRejectionError",
    "AdvisoryStatus",
    "AdvisoryValidationError",
    "AgriculturalKnowledgeCorpus",
    "CropProblemAdvisory",
    "CropProblemAdvisoryError",
    "ExpertReferralUrgency",
    "GeminiGenerationError",
    "KnowledgeEntry",
    "KnowledgeReference",
    "KnowledgeRetrievalResult",
    "KnowledgeSourceProvenance",
    "PathogenCategory",
    "PossibleCondition",
    "SafeActionCategory",
    "SafeCulturalAction",
    "SymptomMatchLevel",
    "build_crop_problem_prompt",
    "generate_crop_problem_advisory",
    "generate_deterministic_crop_advisory",
    "get_empty_corpus",
    "retrieve_knowledge",
    "retrieve_knowledge_entries",
    "run_crop_problem_pipeline",
    "validate_advisory_payload",
]
