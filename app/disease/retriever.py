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
"""Phase 5D Deterministic Agricultural Knowledge Retrieval Provider.

Provides lightweight, fully deterministic, reproducible keyword-based retrieval
over the structured AgriculturalKnowledgeCorpus.

Key Invariants:
- Fully deterministic matching and scoring (no LLM, no vector DB, no BM25).
- Internal 'retrieval_score' is strictly a keyword-matching heuristic for ordering
  and MUST NEVER be exposed or interpreted as disease probability or confidence.
- Gracefully handles empty corpus and empty queries.
- Cleanly extracts crop, plant part, and symptom tokens with small explicit aliases.
- Stable tie-breaking via entry_id in lexicographical order.
"""

import unicodedata
from pydantic import BaseModel, ConfigDict, Field

from app.disease.corpus import AgriculturalKnowledgeCorpus
from app.disease.types import KnowledgeEntry

# ---------------------------------------------------------------------------
# Explicit deterministic alias mappings (English, Hindi transliterated, Devanagari)
# ---------------------------------------------------------------------------

CROP_ALIASES: dict[str, str] = {
    # Rice / Paddy
    "rice": "rice",
    "paddy": "rice",
    "dhan": "rice",
    "dhaan": "rice",
    "chawal": "rice",
    "धान": "rice",
    "चावल": "rice",
    # Wheat
    "wheat": "wheat",
    "gehun": "wheat",
    "gehu": "wheat",
    "गेहूं": "wheat",
    "गेहू": "wheat",
    # Maize / Corn
    "maize": "maize",
    "corn": "maize",
    "makka": "maize",
    "makke": "maize",
    "makai": "maize",
    "मक्का": "maize",
    "मक्के": "maize",
    "मकई": "maize",
    # Cotton
    "cotton": "cotton",
    "kapas": "cotton",
    "rui": "cotton",
    "कपास": "cotton",
    "रुई": "cotton",
    # Potato
    "potato": "potato",
    "aaloo": "potato",
    "aalu": "potato",
    "alu": "potato",
    "आलू": "potato",
    # Tomato
    "tomato": "tomato",
    "tamatar": "tomato",
    "टमाटर": "tomato",
    # Chickpea / Gram
    "chickpea": "chickpea",
    "gram": "chickpea",
    "chana": "chickpea",
    "chane": "chickpea",
    "चना": "chickpea",
    "चने": "chickpea",
    # Mustard
    "mustard": "mustard",
    "sarson": "mustard",
    "sarso": "mustard",
    "सरसों": "mustard",
    # Sugarcane
    "sugarcane": "sugarcane",
    "ganna": "sugarcane",
    "ganne": "sugarcane",
    "गन्ना": "sugarcane",
    "गन्ने": "sugarcane",
    # Pigeon pea / Pigeonpea / Arhar / Toor / Tur
    "pigeon": "pigeon pea",
    "pigeonpea": "pigeon pea",
    "arhar": "pigeon pea",
    "toor": "pigeon pea",
    "tur": "pigeon pea",
    "tuvar": "pigeon pea",
    "अरहर": "pigeon pea",
    "तूर": "pigeon pea",
    "तुवर": "pigeon pea",
    # Groundnut / Peanut
    "groundnut": "groundnut",
    "peanut": "groundnut",
    "peanuts": "groundnut",
    "mungfali": "groundnut",
    "moongfali": "groundnut",
    "moongphali": "groundnut",
    "मूंगफली": "groundnut",
    # Onion
    "onion": "onion",
    "pyaj": "onion",
    "pyaaz": "onion",
    "kanda": "onion",
    "प्याज": "onion",
    "कांदा": "onion",
    # Chilli
    "chilli": "chilli",
    "chili": "chilli",
    "mirch": "chilli",
    "मिर्च": "chilli",
    # Soybean
    "soybean": "soybean",
    "soyabean": "soybean",
    "soya": "soybean",
    "सोयाबीन": "soybean",
}

PLANT_PART_ALIASES: dict[str, str] = {
    # Leaf
    "leaf": "leaf",
    "leaves": "leaf",
    "foliage": "leaf",
    "patta": "leaf",
    "patte": "leaf",
    "patti": "leaf",
    "patto": "leaf",
    "patton": "leaf",
    "pattiyan": "leaf",
    "pattiyo": "leaf",
    "पत्ता": "leaf",
    "पत्ते": "leaf",
    "पत्ती": "leaf",
    "पत्तियां": "leaf",
    "पत्तियों": "leaf",
    "पत्तों": "leaf",
    # Stem
    "stem": "stem",
    "stems": "stem",
    "stalk": "stem",
    "stalks": "stem",
    "shoot": "stem",
    "shoots": "stem",
    "cane": "stem",
    "canes": "stem",
    "tana": "stem",
    "tane": "stem",
    "tano": "stem",
    "तना": "stem",
    "तने": "stem",
    "तनों": "stem",
    # Root
    "root": "root",
    "roots": "root",
    "jad": "root",
    "jadh": "root",
    "jade": "root",
    "jadein": "root",
    "jado": "root",
    "जड़": "root",
    "जड़ें": "root",
    "जड़ों": "root",
    # Fruit / Pod / Boll
    "fruit": "fruit",
    "fruits": "fruit",
    "pod": "fruit",
    "pods": "fruit",
    "boll": "fruit",
    "bolls": "fruit",
    "phal": "fruit",
    "fal": "fruit",
    "phalo": "fruit",
    "falo": "fruit",
    "phali": "fruit",
    "फल": "fruit",
    "फलों": "fruit",
    "फली": "fruit",
    "फलियां": "fruit",
    # Flower
    "flower": "flower",
    "flowers": "flower",
    "blossom": "flower",
    "phool": "flower",
    "fool": "flower",
    "phoolo": "flower",
    "फूल": "flower",
    "फूलों": "flower",
    # Seed / Grain
    "seed": "seed",
    "seeds": "seed",
    "grain": "seed",
    "grains": "seed",
    "dana": "seed",
    "daane": "seed",
    "beej": "seed",
    "bij": "seed",
    "बीज": "seed",
    "बीजों": "seed",
    "दाना": "seed",
    "दाने": "seed",
    "दानों": "seed",
    # Panicle / Ear / Head
    "panicle": "panicle",
    "panicles": "panicle",
    "ear": "panicle",
    "head": "panicle",
    "bali": "panicle",
    "baali": "panicle",
    "baliyan": "panicle",
    "बाली": "panicle",
    "बालियां": "panicle",
    "बालियों": "panicle",
    # Sheath
    "sheath": "sheath",
    "sheaths": "sheath",
    # Tiller
    "tiller": "tiller",
    "tillers": "tiller",
    "kalla": "tiller",
    "kalle": "tiller",
    "कल्ले": "tiller",
}

SYMPTOM_ALIASES: dict[str, str] = {
    # Colors
    "brown": "brown",
    "bhura": "brown",
    "bhure": "brown",
    "bhuri": "brown",
    "भूरा": "brown",
    "भूरे": "brown",
    "भूरी": "brown",
    "yellow": "yellow",
    "yellowing": "yellow",
    "chlorosis": "yellow",
    "peela": "yellow",
    "peele": "yellow",
    "peeli": "yellow",
    "पीला": "yellow",
    "पीले": "yellow",
    "पीली": "yellow",
    "black": "black",
    "dark": "black",
    "kala": "black",
    "kale": "black",
    "kali": "black",
    "काला": "black",
    "काले": "black",
    "काली": "black",
    "white": "white",
    "safed": "white",
    "chitta": "white",
    "सफ़ेद": "white",
    "सफेद": "white",
    "red": "red",
    "reddish": "red",
    "lal": "red",
    "laal": "red",
    "लाल": "red",
    "pink": "pink",
    "gulabi": "pink",
    "गुलाबी": "pink",
    # Spots / Lesions
    "spot": "spot",
    "spots": "spot",
    "spotting": "spot",
    "lesion": "spot",
    "lesions": "spot",
    "speck": "spot",
    "specks": "spot",
    "daag": "spot",
    "dag": "spot",
    "dhabba": "spot",
    "dhabbe": "spot",
    "dhabbo": "spot",
    "दाग": "spot",
    "दागों": "spot",
    "धब्बा": "spot",
    "धब्बे": "spot",
    "धब्बों": "spot",
    # Wilting / Drooping
    "wilt": "wilt",
    "wilts": "wilt",
    "wilting": "wilt",
    "droop": "wilt",
    "drooping": "wilt",
    "murjha": "wilt",
    "murjhana": "wilt",
    "मुरझाना": "wilt",
    "मुरझा": "wilt",
    # Rotting / Decay
    "rot": "rot",
    "rotting": "rot",
    "rotten": "rot",
    "decay": "rot",
    "galan": "rot",
    "sadna": "rot",
    "गलना": "rot",
    "सड़ना": "rot",
    # Blight / Burning
    "blight": "blight",
    "blighted": "blight",
    "burn": "blight",
    "burning": "blight",
    "jhulsa": "blight",
    "jhulsan": "blight",
    "झुलसा": "blight",
    "झुलस": "blight",
    # Rust
    "rust": "rust",
    "rusting": "rust",
    "pustule": "rust",
    "pustules": "rust",
    "gerui": "rust",
    "geru": "rust",
    "गेरुआ": "rust",
    "गेरुई": "rust",
    # Curled / Distorted
    "curl": "curl",
    "curls": "curl",
    "curling": "curl",
    "curled": "curl",
    "murna": "curl",
    "mudna": "curl",
    "मुड़ना": "curl",
    "मुड़े": "curl",
    # Mildew / Powdery
    "mildew": "mildew",
    "powdery": "powdery",
    "powder": "powdery",
    "churnil": "powdery",
    "चूर्णिल": "powdery",
    # Mosaic / Mottling
    "mosaic": "mosaic",
    "mottle": "mosaic",
    "mottling": "mosaic",
    # Stunting / Dwarfing
    "stunt": "stunt",
    "stunted": "stunt",
    "stunting": "stunt",
    "dwarf": "stunt",
    "bona": "stunt",
    # Shape descriptors
    "oval": "oval",
    "spindle": "oval",
    "elliptical": "oval",
    "andaakar": "oval",
    "अंडाकार": "oval",
    # Dry / Drying
    "dry": "dry",
    "drying": "dry",
    "wither": "dry",
    "withering": "dry",
    "sukha": "dry",
    "sookh": "dry",
    "सूख": "dry",
    "सूखा": "dry",
    "सूखे": "dry",
    # Holes / Damage
    "hole": "hole",
    "holes": "hole",
    "chhed": "hole",
    "छेद": "hole",
    # Streaks / Stripes
    "streak": "streak",
    "streaks": "streak",
    "stripe": "streak",
    "stripes": "streak",
}

# English stop words to ignore during broad token matching
STOP_WORDS: set[str] = {
    "a", "an", "the", "in", "on", "at", "to", "for", "of", "with", "by", "from",
    "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
    "do", "does", "did", "and", "or", "but", "if", "then", "my", "our", "your",
    "their", "its", "plant", "plants", "crop", "crops", "farm", "field", "see",
    "showing", "problem", "issue", "help", "please", "ka", "ki", "ke", "par",
    "me", "hai", "hain", "ko", "se", "ho", "gaya", "gayi", "raha", "rahi",
}


# ---------------------------------------------------------------------------
# Retrieval Contract
# ---------------------------------------------------------------------------


class KnowledgeRetrievalResult(BaseModel):
    """Deterministic retrieval result ranking a KnowledgeEntry against a query.

    NOTE: retrieval_score is an internal deterministic ranking heuristic based
    purely on keyword matching and field alignment. It has NO diagnostic
    interpretation, NO statistical confidence meaning, and MUST NOT be
    presented as a disease certainty or probability.
    """

    entry: KnowledgeEntry = Field(
        description="The retrieved knowledge entry"
    )
    retrieval_score: float = Field(
        description="Internal deterministic ranking heuristic for relevance ordering. NO diagnostic interpretation."
    )
    matched_terms: list[str] = Field(
        default_factory=list,
        description="Query terms or keywords that matched this entry"
    )
    matched_fields: list[str] = Field(
        default_factory=list,
        description="Entry fields that contributed to the match (e.g. 'crop', 'plant_part', 'symptom_keywords', 'condition_name')"
    )

    model_config = ConfigDict(frozen=True, extra="forbid")


# ---------------------------------------------------------------------------
# Lightweight Deterministic Normalization
# ---------------------------------------------------------------------------


def normalize_and_tokenize(text: str) -> list[str]:
    """Cleans punctuation, lowercases, and splits text into whitespace tokens.

    Accurately handles Unicode scripts (Devanagari, Latin) by stripping
    punctuation/symbols while preserving letters and combining marks.
    """
    if not text:
        return []
    cleaned = "".join(
        " " if unicodedata.category(c).startswith(("P", "S")) else c
        for c in text
    )
    tokens = [t.lower().strip() for t in cleaned.split() if t.strip()]
    return tokens


class ParsedQueryTerms:
    """Holds extracted, normalized tokens and canonical entity detections."""

    def __init__(self, raw_query: str) -> None:
        self.raw_query = raw_query
        self.tokens: list[str] = normalize_and_tokenize(raw_query)

        self.detected_crops: set[str] = set()
        self.detected_parts: set[str] = set()
        self.detected_symptoms: set[str] = set()
        self.canonical_tokens: list[str] = []

        for token in self.tokens:
            # Crop check
            if token in CROP_ALIASES:
                canonical_crop = CROP_ALIASES[token]
                self.detected_crops.add(canonical_crop)
                self.canonical_tokens.append(canonical_crop)

            # Plant part check
            if token in PLANT_PART_ALIASES:
                canonical_part = PLANT_PART_ALIASES[token]
                self.detected_parts.add(canonical_part)
                self.canonical_tokens.append(canonical_part)

            # Symptom check
            if token in SYMPTOM_ALIASES:
                canonical_symptom = SYMPTOM_ALIASES[token]
                self.detected_symptoms.add(canonical_symptom)
                self.canonical_tokens.append(canonical_symptom)

            # Preserve non-stopword tokens for broad matching
            if token not in STOP_WORDS:
                self.canonical_tokens.append(token)


# ---------------------------------------------------------------------------
# Scoring and Retrieval Logic
# ---------------------------------------------------------------------------

# Deterministic ranking weights (Heuristic ordering only; NOT disease probabilities)
WEIGHT_CROP_EXACT_MATCH: float = 10.0
WEIGHT_PLANT_PART_MATCH: float = 4.0
WEIGHT_SYMPTOM_KEYWORD_MATCH: float = 3.0
WEIGHT_CONDITION_TOKEN_MATCH: float = 2.0
WEIGHT_DESCRIPTION_TOKEN_MATCH: float = 0.5


def calculate_entry_relevance(
    parsed_query: ParsedQueryTerms,
    entry: KnowledgeEntry,
) -> tuple[float, list[str], list[str]]:
    """Calculates deterministic ranking score and matched terms for an entry.

    Returns:
        tuple[float, list[str], list[str]]: (retrieval_score, matched_terms, matched_fields)
    """
    entry_crop = entry.crop.strip().lower()
    entry_part = entry.plant_part.strip().lower()
    entry_symptoms = {s.strip().lower() for s in entry.symptom_keywords}
    entry_condition_tokens = set(normalize_and_tokenize(entry.condition_name))
    entry_description_tokens = set(normalize_and_tokenize(entry.description)) - STOP_WORDS

    score = 0.0
    matched_terms: list[str] = []
    matched_fields: list[str] = []

    # 1. Crop Matching Rule
    if parsed_query.detected_crops:
        if entry_crop in parsed_query.detected_crops:
            score += WEIGHT_CROP_EXACT_MATCH
            matched_terms.append(entry_crop)
            matched_fields.append("crop")
        else:
            # Hard exclusion: when the user explicitly queried for a specific crop,
            # entries from other crops receive 0 relevance.
            return 0.0, [], []
    else:
        # Query did NOT specify a crop: do not invent one, permit all crops to match
        # on symptoms/parts.
        pass

    # 2. Plant Part Matching Rule
    if parsed_query.detected_parts:
        if entry_part in parsed_query.detected_parts:
            score += WEIGHT_PLANT_PART_MATCH
            matched_terms.append(entry_part)
            matched_fields.append("plant_part")

    # 3. Symptom Keywords Matching Rule
    symptom_matches = set()
    all_query_symptom_candidates = parsed_query.detected_symptoms.union(
        {t for t in parsed_query.canonical_tokens if t in entry_symptoms}
    )
    for sym in entry_symptoms:
        if sym in all_query_symptom_candidates:
            symptom_matches.add(sym)

    if symptom_matches:
        score += len(symptom_matches) * WEIGHT_SYMPTOM_KEYWORD_MATCH
        matched_terms.extend(sorted(symptom_matches))
        matched_fields.append("symptom_keywords")

    # 4. Condition Name Token Overlap
    condition_matches = set()
    for token in parsed_query.canonical_tokens:
        if token in entry_condition_tokens and token not in STOP_WORDS:
            condition_matches.add(token)

    if condition_matches:
        score += len(condition_matches) * WEIGHT_CONDITION_TOKEN_MATCH
        matched_terms.extend(sorted(condition_matches))
        if "condition_name" not in matched_fields:
            matched_fields.append("condition_name")

    # 5. Description Token Overlap (low weight tie-breaker)
    desc_matches = set()
    for token in parsed_query.canonical_tokens:
        if token in entry_description_tokens and token not in STOP_WORDS:
            desc_matches.add(token)

    if desc_matches:
        score += len(desc_matches) * WEIGHT_DESCRIPTION_TOKEN_MATCH
        for dm in sorted(desc_matches):
            if dm not in matched_terms:
                matched_terms.append(dm)
        if "description" not in matched_fields:
            matched_fields.append("description")

    return score, matched_terms, matched_fields


def retrieve_knowledge(
    query: str,
    corpus: AgriculturalKnowledgeCorpus,
    top_k: int = 5,
    min_score: float = 1.0,
) -> list[KnowledgeRetrievalResult]:
    """Deterministically retrieves and ranks relevant KnowledgeEntry records from a corpus.

    Args:
        query: Free-text farmer question, symptom description, or localized query.
        corpus: The AgriculturalKnowledgeCorpus containing verified knowledge records.
        top_k: Maximum number of relevant entries to return (must be >= 1).
        min_score: Minimum deterministic ranking threshold to qualify as relevant.

    Returns:
        list[KnowledgeRetrievalResult]: Deterministically sorted results ordered by
        descending retrieval_score with entry_id tie-breaking.

    Raises:
        ValueError: If top_k < 1.

    Important:
        retrieval_score is strictly an internal keyword-matching ranking heuristic
        and MUST NEVER be interpreted as disease confidence or probability.
    """
    if top_k < 1:
        raise ValueError(f"top_k must be >= 1, got {top_k}")

    if not corpus.entries or not query or not query.strip():
        return []

    parsed = ParsedQueryTerms(query)
    scored_results: list[KnowledgeRetrievalResult] = []

    for entry in corpus.entries:
        score, matched_terms, matched_fields = calculate_entry_relevance(parsed, entry)
        if score >= min_score and matched_terms:
            scored_results.append(
                KnowledgeRetrievalResult(
                    entry=entry,
                    retrieval_score=score,
                    matched_terms=matched_terms,
                    matched_fields=matched_fields,
                )
            )

    # Sort deterministically:
    # Primary: descending retrieval_score
    # Tie-breaker: ascending entry_id (lexicographical order)
    scored_results.sort(key=lambda r: (-r.retrieval_score, r.entry.entry_id))

    return scored_results[:top_k]


def retrieve_knowledge_entries(
    query: str,
    corpus: AgriculturalKnowledgeCorpus,
    top_k: int = 5,
    min_score: float = 1.0,
) -> list[KnowledgeEntry]:
    """Convenience wrapper returning only the retrieved KnowledgeEntry objects."""
    results = retrieve_knowledge(query, corpus, top_k=top_k, min_score=min_score)
    return [r.entry for r in results]
