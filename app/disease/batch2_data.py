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
"""Phase 5D Batch 2 Verified Production Agricultural Knowledge Data.

Provides verified reference records for the remaining 5 MVP crops:
1. Pigeon pea / Arhar / Toor (5 entries)
2. Groundnut / Peanut (5 entries)
3. Soybean (5 entries)
4. Cotton (4 entries)
5. Sugarcane (4 entries)

Total: 23 verified entries across 5 verified institutional sources.

Epistemic & Safety Invariants:
- Grounded in verified State Agricultural University (TNAU Agritech Portal) crop protection resources.
- ZERO chemical prescriptions, active ingredients, spray rates, or chemical brand names.
- Non-diagnostic candidate language only; zero claims of definitive diagnosis.
- Preserves 100% referential integrity: all entry source_ids resolve to registered sources.
"""

from app.disease.types import (
    KnowledgeEntry,
    KnowledgeSourceProvenance,
)

# ---------------------------------------------------------------------------
# Batch 2 Verified Source Provenance Records (5 Verified TNAU Extension Portals)
# ---------------------------------------------------------------------------

BATCH2_SOURCES: dict[str, KnowledgeSourceProvenance] = {
    "src_tnau_crop_protection_pigeonpea": KnowledgeSourceProvenance(
        source_id="src_tnau_crop_protection_pigeonpea",
        organization="Tamil Nadu Agricultural University (TNAU)",
        document_title="TNAU Agritech Portal: Crop Protection — Redgram (Pigeonpea) Diseases and Insect Pests (Pulses)",
        version_or_year="2024",
        source_url="https://agritech.tnau.ac.in/crop_protection/crop_prot.html",
        license_or_usage_terms="State Agricultural University open agricultural extension portal; factual symptom and cultural IPM extraction with institutional attribution",
        retrieval_date="2026-09-28",
        crops_covered=["Pigeon pea"],
        disease_topics=[
            "Sterility Mosaic Disease",
            "Fusarium Wilt",
            "Phytophthora Stem Blight",
            "Gram Pod Borer",
            "Pod Fly",
        ],
        attribution_requirement="Tamil Nadu Agricultural University (TNAU) Agritech Portal, Coimbatore",
        redistribution_status="bundled_permitted",
    ),
    "src_tnau_crop_protection_groundnut": KnowledgeSourceProvenance(
        source_id="src_tnau_crop_protection_groundnut",
        organization="Tamil Nadu Agricultural University (TNAU)",
        document_title="TNAU Agritech Portal: Crop Protection — Groundnut Diseases and Insect Pests (Oilseeds)",
        version_or_year="2024",
        source_url="https://agritech.tnau.ac.in/crop_protection/crop_prot.html",
        license_or_usage_terms="State Agricultural University open agricultural extension portal; factual symptom and cultural IPM extraction with institutional attribution",
        retrieval_date="2026-09-28",
        crops_covered=["Groundnut"],
        disease_topics=[
            "Stem Rot",
            "Early Leaf Spot",
            "Late Leaf Spot",
            "Groundnut Rust",
            "Bud Necrosis",
        ],
        attribution_requirement="Tamil Nadu Agricultural University (TNAU) Agritech Portal, Coimbatore",
        redistribution_status="bundled_permitted",
    ),
    "src_tnau_crop_protection_soybean": KnowledgeSourceProvenance(
        source_id="src_tnau_crop_protection_soybean",
        organization="Tamil Nadu Agricultural University (TNAU)",
        document_title="TNAU Agritech Portal: Crop Protection — Soybean Diseases and Insect Pests (Oilseeds / Pulses)",
        version_or_year="2024",
        source_url="https://agritech.tnau.ac.in/crop_protection/crop_prot.html",
        license_or_usage_terms="State Agricultural University open agricultural extension portal; factual symptom and cultural IPM extraction with institutional attribution",
        retrieval_date="2026-09-28",
        crops_covered=["Soybean"],
        disease_topics=[
            "Yellow Mosaic Disease",
            "Anthracnose Pod Blight",
            "Girdle Beetle",
            "Stem Fly",
            "Rhizoctonia Aerial Blight",
        ],
        attribution_requirement="Tamil Nadu Agricultural University (TNAU) Agritech Portal, Coimbatore",
        redistribution_status="bundled_permitted",
    ),
    "src_tnau_crop_protection_cotton": KnowledgeSourceProvenance(
        source_id="src_tnau_crop_protection_cotton",
        organization="Tamil Nadu Agricultural University (TNAU)",
        document_title="TNAU Agritech Portal: Crop Protection — Cotton Diseases and Insect Pests (Fiber Crops)",
        version_or_year="2024",
        source_url="https://agritech.tnau.ac.in/crop_protection/crop_prot.html",
        license_or_usage_terms="State Agricultural University open agricultural extension portal; factual symptom and cultural IPM extraction with institutional attribution",
        retrieval_date="2026-09-28",
        crops_covered=["Cotton"],
        disease_topics=[
            "Pink Bollworm",
            "Cotton Jassid",
            "Bacterial Blight",
            "Cotton Boll Rot",
        ],
        attribution_requirement="Tamil Nadu Agricultural University (TNAU) Agritech Portal, Coimbatore",
        redistribution_status="bundled_permitted",
    ),
    "src_tnau_crop_protection_sugarcane": KnowledgeSourceProvenance(
        source_id="src_tnau_crop_protection_sugarcane",
        organization="Tamil Nadu Agricultural University (TNAU)",
        document_title="TNAU Agritech Portal: Crop Protection — Sugarcane Diseases and Insect Pests (Sugar Crops)",
        version_or_year="2024",
        source_url="https://agritech.tnau.ac.in/crop_protection/crop_prot.html",
        license_or_usage_terms="State Agricultural University open agricultural extension portal; factual symptom and cultural IPM extraction with institutional attribution",
        retrieval_date="2026-09-28",
        crops_covered=["Sugarcane"],
        disease_topics=[
            "Red Rot",
            "Sugarcane Smut",
            "Yellow Leaf Disease",
            "Early Shoot Borer",
        ],
        attribution_requirement="Tamil Nadu Agricultural University (TNAU) Agritech Portal, Coimbatore",
        redistribution_status="bundled_permitted",
    ),
}

# ---------------------------------------------------------------------------
# Batch 2 Verified Knowledge Entries (23 Records across 5 crops)
# ---------------------------------------------------------------------------

BATCH2_ENTRIES: list[KnowledgeEntry] = [
    # =======================================================================
    # 1. PIGEON PEA (5 Entries)
    # =======================================================================
    KnowledgeEntry(
        entry_id="PIGEONPEA-01",
        crop="Pigeon pea",
        plant_part="leaf",
        symptom_keywords=[
            "sterility mosaic",
            "mosaic",
            "pigeonpea sterility",
            "bushy",
            "yellow patches",
            "green patches",
            "mottling",
            "no flowers",
            "no pods",
            "stunted",
            "mite",
            "sterility",
            "flower suppression",
            "arhar mosaic",
            "patch",
            "yellow",
            "green",
            "stunting",
        ],
        condition_name="Sterility Mosaic Disease",
        scientific_name="Pigeonpea sterility mosaic virus",
        category="viral",
        description=(
            "Symptoms may be associated with Sterility Mosaic Disease (SMD) transmitted by the eriophyid mite Aceria cajani. "
            "Leaves show characteristic mosaic mottling with alternating light green and chlorotic yellowish patches. "
            "Internodes become shortened and excessive secondary branching gives plants a dense, bushy appearance. "
            "Affected plants exhibit partial or complete sterility with suppression of flowering and pod formation."
        ),
        safe_cultural_practices=[
            "Rogue out and destroy infected plants showing early mosaic symptoms to limit secondary spread.",
            "Grow recommended SMD-resistant or tolerant varieties adapted to the region.",
            "Avoid ratooning or maintaining perennial pigeonpea crops which serve as continuous mite reservoirs.",
            "Deep summer plowing to reduce alternate host weeds along field borders.",
        ],
        clarifying_observations=[
            "Are leaves showing mosaic mottling with light and dark green or yellow patches?",
            "Does the plant have an abnormally dense bushy appearance with suppressed flowering?",
            "Are nearby plants also failing to set flowers and pods in patches?",
        ],
        source_id="src_tnau_crop_protection_pigeonpea",
    ),
    KnowledgeEntry(
        entry_id="PIGEONPEA-02",
        crop="Pigeon pea",
        plant_part="stem",
        symptom_keywords=[
            "fusarium wilt",
            "pigeonpea wilt",
            "arhar wilt",
            "vascular browning",
            "xylem browning",
            "wilting in patches",
            "drooping leaves",
            "lower leaf yellowing",
            "branch drying",
            "wilt",
            "drooping",
            "root discoloration",
            "dry",
            "yellow",
        ],
        condition_name="Fusarium Wilt",
        scientific_name="Fusarium udum",
        category="fungal",
        description=(
            "Symptoms can be consistent with Fusarium wilt of pigeonpea. Symptoms typically appear at flowering "
            "and podding stages with gradual drooping, yellowing, and drying of leaves starting on lower branches or one side "
            "of the plant. A prominent dark purple-brown band may extend upward from the collar on the stem surface. "
            "Splitting the main stem or taproot longitudinally reveals distinct dark brown to blackish vascular xylem discoloration."
        ),
        safe_cultural_practices=[
            "Follow a 3- to 4-year crop rotation with non-host crops like sorghum, maize, or pearl millet.",
            "Select certified wilt-resistant pigeonpea cultivars.",
            "Uproot and burn wilted plants and stubbles to minimize soilborne fungal inoculum.",
            "Ensure proper field drainage to avoid root stress in heavy soils.",
        ],
        clarifying_observations=[
            "Does splitting the lower stem or main root vertically reveal dark brown or black vascular lines inside?",
            "Did wilting start on one side of the plant or lower branches before spreading?",
            "Is the wilting occurring in distinct patches across the field?",
        ],
        source_id="src_tnau_crop_protection_pigeonpea",
    ),
    KnowledgeEntry(
        entry_id="PIGEONPEA-03",
        crop="Pigeon pea",
        plant_part="stem",
        symptom_keywords=[
            "phytophthora stem blight",
            "stem blight",
            "dark brown lesion",
            "stem girdling",
            "stem snapping",
            "waterlogging",
            "rain blight",
            "sudden plant collapse",
            "blight",
            "stem rot",
            "arhar blight",
            "brown",
            "rot",
            "lesion",
        ],
        condition_name="Phytophthora Stem Blight",
        scientific_name="Phytophthora cajani",
        category="fungal",
        description=(
            "Symptoms may indicate Phytophthora stem blight, especially following heavy rainfall, cloudy weather, "
            "or waterlogging. Dark brown to blackish, water-soaked sunken lesions form on the main stem and lower branches "
            "near the soil surface. Lesions rapidly enlarge and girdle the stem, causing the foliage above the lesion to wilt, "
            "turn brown, and dry up while remaining attached. The stem easily breaks or snaps at the point of infection."
        ),
        safe_cultural_practices=[
            "Improve surface drainage and avoid standing water in low-lying field sections.",
            "Sow pigeonpea on ridges or raised beds in heavy clay soils prone to temporary waterlogging.",
            "Maintain recommended plant-to-plant spacing to facilitate air circulation and lower canopy humidity.",
            "Avoid growing pigeonpea in fields with a recent history of severe stem blight.",
        ],
        clarifying_observations=[
            "Do you see dark brown or black girdling lesions on the main stem near ground level or branch junctions?",
            "Does the upper stem snap easily at the diseased lesion site?",
            "Did symptoms develop or escalate rapidly after heavy monsoon rain or water stagnation?",
        ],
        source_id="src_tnau_crop_protection_pigeonpea",
    ),
    KnowledgeEntry(
        entry_id="PIGEONPEA-04",
        crop="Pigeon pea",
        plant_part="fruit",
        symptom_keywords=[
            "gram pod borer",
            "helicoverpa",
            "caterpillar",
            "circular entry holes",
            "bored pods",
            "eaten seeds",
            "frass",
            "fecal pellets",
            "flower damage",
            "pod borer",
            "hole in pod",
            "arhar pod borer",
            "pod",
            "hole",
            "borer",
        ],
        condition_name="Gram Pod Borer",
        scientific_name="Helicoverpa armigera",
        category="pest_damage",
        description=(
            "Symptoms can indicate feeding damage by the gram pod borer caterpillar. Larvae feed on flower buds, "
            "flowers, and developing green pods. Caterpillars characteristically bore neat circular holes into pods, "
            "thrusting the anterior portion of their body inside to consume developing seeds while the posterior half remains "
            "outside. Dark granular fecal pellets (frass) may be observed around the entry hole or on adjacent foliage."
        ),
        safe_cultural_practices=[
            "Install pheromone traps (4–5 traps/acre) to monitor adult Helicoverpa moth activity.",
            "Erect T-shaped bird perches (15–20/acre) across the field to encourage predatory insectivorous birds.",
            "Intercrop with sorghum, maize, or coriander to encourage beneficial natural predators.",
            "Hand-pick and destroy visible caterpillars and bored pods during early morning hours in smallholder plots.",
        ],
        clarifying_observations=[
            "Are there neat, circular holes bored into green pods with seeds partially eaten inside?",
            "Can you see caterpillars with their heads inside the pod and rear bodies outside?",
            "Is dark granular frass present near the bored entry holes?",
        ],
        source_id="src_tnau_crop_protection_pigeonpea",
    ),
    KnowledgeEntry(
        entry_id="PIGEONPEA-05",
        crop="Pigeon pea",
        plant_part="fruit",
        symptom_keywords=[
            "pod fly",
            "maggot",
            "exit pinhole",
            "shriveled seeds",
            "striped grain",
            "internal seed feeding",
            "deformed seeds",
            "decayed grain",
            "pod fly hole",
            "arhar pod fly",
            "pod",
            "seed",
            "hole",
        ],
        condition_name="Pod Fly",
        scientific_name="Melanagromyza obtusa",
        category="pest_damage",
        description=(
            "Symptoms may be associated with pigeonpea pod fly damage. The female fly deposits eggs inside tender "
            "green pods; the apodous maggot mines and feeds on developing seeds beneath the seed coat. Affected grains "
            "become striped, deformed, shriveled, and decayed. External pod symptoms are unnoticeable during growth, "
            "but at maturity, the maggot cuts a characteristic minute circular pinhole window in the pod wall before pupation."
        ),
        safe_cultural_practices=[
            "Harvest mature pods promptly to prevent late-season maggot infestation build-up.",
            "Collect and destroy infested crop residues and chaff after threshing.",
            "Perform deep summer plowing to expose puparia in the soil to predators and sunlight.",
            "Grow early-maturing or pod fly-tolerant pigeonpea cultivars if available.",
        ],
        clarifying_observations=[
            "When opening mature pods, are seeds inside shriveled, striped, or partially hollowed?",
            "Are there small, clean circular pinhole exit windows on the dry pod walls?",
            "Did the pods appear undamaged on the outside while the grains inside were ruined?",
        ],
        source_id="src_tnau_crop_protection_pigeonpea",
    ),
    # =======================================================================
    # 2. GROUNDNUT (5 Entries)
    # =======================================================================
    KnowledgeEntry(
        entry_id="GROUNDNUT-01",
        crop="Groundnut",
        plant_part="stem",
        symptom_keywords=[
            "stem rot",
            "collar rot",
            "sclerotium",
            "white mycelium",
            "mustard seed sclerotia",
            "collar browning",
            "wilting branches",
            "shredded stem",
            "groundnut rot",
            "mungfali collar rot",
            "rot",
            "white",
            "wilt",
            "wilting",
        ],
        condition_name="Stem Rot / Collar Rot",
        scientific_name="Sclerotium rolfsii",
        category="fungal",
        description=(
            "Symptoms can be consistent with stem rot or collar rot of groundnut. Initial symptoms appear as sudden "
            "yellowing and wilting of individual branches near ground level. The collar region and lower stems develop brown "
            "necrotic lesions covered by dense, white, fan-shaped fungal mycelial growth. As the disease advances, numerous tiny, "
            "round, brown mustard seed-like sclerotia develop on the mycelial mat and surrounding soil surface."
        ),
        safe_cultural_practices=[
            "Practice crop rotation with cereal crops such as maize, sorghum, or pearl millet.",
            "Perform deep summer plowing to bury surface sclerotia below the root zone.",
            "Avoid pushing soil around the plant collar during inter-cultivation (avoid soil mounding).",
            "Remove and burn wilted plants along with attached sclerotia and debris.",
        ],
        clarifying_observations=[
            "Is there dense white fan-like fungal growth around the stem base near the soil surface?",
            "Can you see small, round brownish bodies resembling mustard seeds (sclerotia) on the mycelium?",
            "Is the stem shredded, decayed, or browned at the soil contact level?",
        ],
        source_id="src_tnau_crop_protection_groundnut",
    ),
    KnowledgeEntry(
        entry_id="GROUNDNUT-02",
        crop="Groundnut",
        plant_part="leaf",
        symptom_keywords=[
            "early leaf spot",
            "tikka",
            "tikka disease",
            "yellow halo",
            "circular brown spots",
            "reddish brown spots",
            "upper leaf surface",
            "leaf spots on groundnut",
            "mungfali tikka",
            "spot",
            "spots",
            "yellow",
            "brown",
        ],
        condition_name="Early Leaf Spot (Tikka)",
        scientific_name="Cercospora arachidicola",
        category="fungal",
        description=(
            "Symptoms may be associated with Early Leaf Spot (Tikka disease). Lesions appear on young foliage "
            "approximately 3 to 4 weeks after sowing. Spots are sub-circular to circular, reddish-brown to dark brown on "
            "the upper leaf surface, surrounded by a distinct and prominent bright yellow chlorotic halo. Spots on the lower "
            "surface are lighter brown with less distinct halos."
        ),
        safe_cultural_practices=[
            "Collect and burn crop debris after harvest to reduce overwintering conidia.",
            "Rotate groundnut with non-host graminaceous crops.",
            "Maintain recommended plant density to improve air movement and reduce leaf wetness duration.",
            "Avoid overhead irrigation that extends canopy wetness.",
        ],
        clarifying_observations=[
            "Do the brown leaf spots have a prominent bright yellow ring/halo around them?",
            "Are the spots predominantly located on the upper surface of younger leaves?",
            "Did spots start appearing in early vegetative growth (around 3–4 weeks after emergence)?",
        ],
        source_id="src_tnau_crop_protection_groundnut",
    ),
    KnowledgeEntry(
        entry_id="GROUNDNUT-03",
        crop="Groundnut",
        plant_part="leaf",
        symptom_keywords=[
            "late leaf spot",
            "tikka",
            "carbon black spots",
            "black spots",
            "defoliation",
            "premature leaf drop",
            "lower leaf surface",
            "cushion like spots",
            "late tikka",
            "leaf shedding",
            "black",
            "spot",
            "spots",
        ],
        condition_name="Late Leaf Spot",
        scientific_name="Phaeoisariopsis personata",
        category="fungal",
        description=(
            "Symptoms can indicate Late Leaf Spot. Symptoms appear later in the cropping season (around 55 to 60 "
            "days after sowing). Spots are smaller, nearly circular, and dark brown to carbon-black, appearing conspicuously "
            "on the lower surface of leaves. The yellow halo is narrow, indistinct, or completely absent. Spots have a rough, "
            "cushion-like texture due to conidial production and cause rapid, severe defoliation starting from the base upward."
        ),
        safe_cultural_practices=[
            "Remove volunteer groundnut plants and bury crop residues after harvest.",
            "Rotate with non-host cereals such as pearl millet, sorghum, or maize.",
            "Scout fields regularly starting from mid-season (around 50 days).",
            "Avoid excessive planting densities to facilitate canopy ventilation.",
        ],
        clarifying_observations=[
            "Are the leaf spots dark carbon-black and prominent on the underside of leaves?",
            "Do the spots lack a distinct yellow halo?",
            "Is severe leaf drop and defoliation progressing upward from lower leaves?",
        ],
        source_id="src_tnau_crop_protection_groundnut",
    ),
    KnowledgeEntry(
        entry_id="GROUNDNUT-04",
        crop="Groundnut",
        plant_part="leaf",
        symptom_keywords=[
            "groundnut rust",
            "rust",
            "orange pustules",
            "brown pustules",
            "uredinia",
            "powdery brown spores",
            "leaf drying",
            "retained leaves",
            "pustule on leaf underside",
            "mungfali gerui",
            "pustule",
            "brown",
            "orange",
        ],
        condition_name="Groundnut Rust",
        scientific_name="Puccinia arachidis",
        category="fungal",
        description=(
            "Symptoms may be consistent with groundnut rust. Small, orange to reddish-brown raised pustules (uredinia) "
            "form primarily on the lower surface of leaves. Pustules rupture the epidermis to expose powdery brownish-red "
            "spores. Severely affected leaves turn brown, curl, become necrotic, and dry up, but characteristically remain "
            "attached to the plant rather than dropping, giving the canopy a scorched appearance."
        ),
        safe_cultural_practices=[
            "Destroy volunteer groundnut plants and self-sown seedlings during the off-season.",
            "Grow rust-resistant or moderately resistant groundnut varieties.",
            "Maintain adequate spacing between rows to lower relative humidity in the canopy.",
            "Avoid high nitrogen applications that create dense, humid vegetative canopies.",
        ],
        clarifying_observations=[
            "When touching the underside of the leaves, do powdery reddish-brown spores rub off onto fingers?",
            "Are raised orange-brown pustules concentrated on the lower leaf surface?",
            "Do dried, necrotic leaves stay attached to stems rather than dropping to the ground?",
        ],
        source_id="src_tnau_crop_protection_groundnut",
    ),
    KnowledgeEntry(
        entry_id="GROUNDNUT-05",
        crop="Groundnut",
        plant_part="stem",
        symptom_keywords=[
            "bud necrosis",
            "groundnut bud necrosis",
            "gbnv",
            "chlorotic rings",
            "ring spot",
            "terminal bud necrosis",
            "stunting",
            "thrips",
            "bushy stunting",
            "leaf mottling",
            "mungfali bud necrosis",
            "stunt",
            "stunted",
            "spot",
        ],
        condition_name="Groundnut Bud Necrosis",
        scientific_name="Groundnut bud necrosis virus",
        category="viral",
        description=(
            "Symptoms may be associated with Groundnut bud necrosis virus (GBNV) transmitted by thrips (Frankliniella "
            "schultzei and Thrips palmi). Young quadrifoliate leaves display chlorotic ring spots, mottling, and mosaic "
            "patterns. The terminal growing point or bud develops dark brown necrosis and dies back. Early-infected plants "
            "exhibit severe stunting, proliferation of axillary shoots, and clustered, malformed leaves."
        ),
        safe_cultural_practices=[
            "Adopt optimum plant population with close spacing (30 x 10 cm) to minimize open ground and reduce thrips landing.",
            "Intercrop groundnut with fast-growing cereal barrier crops like pearl millet or sorghum (e.g. 3:1 or 4:1 ratio).",
            "Sow early synchronously at the onset of monsoon to establish canopy before peak thrips flights.",
            "Rogue out early-infected stunted plants within 30–40 days after emergence.",
        ],
        clarifying_observations=[
            "Are young leaves showing chlorotic concentric ring spots or yellow mottling?",
            "Is the terminal growing bud turning brown, dying back, or becoming necrotic?",
            "Is the plant severely stunted with clustered, small bushy leaves?",
        ],
        source_id="src_tnau_crop_protection_groundnut",
    ),
    # =======================================================================
    # 3. SOYBEAN (5 Entries)
    # =======================================================================
    KnowledgeEntry(
        entry_id="SOYBEAN-01",
        crop="Soybean",
        plant_part="leaf",
        symptom_keywords=[
            "yellow mosaic",
            "mymiv",
            "whitefly",
            "bright yellow patches",
            "yellow green mosaic",
            "mottling",
            "stunted soybean",
            "small pods",
            "shriveled seeds",
            "soyabean peela rog",
            "yellow",
            "mosaic",
            "patch",
            "stunting",
        ],
        condition_name="Yellow Mosaic Disease",
        scientific_name="Mungbean yellow mosaic India virus",
        category="viral",
        description=(
            "Symptoms can be consistent with yellow mosaic disease transmitted by whiteflies (Bemisia tabaci). "
            "Distinct, alternating bright yellow and green mosaic patches develop on trifoliate leaves. As infection "
            "progresses, newly expanding leaves become completely yellow and reduced in size. Severely affected plants show "
            "stunted growth, reduced flowering, and form fewer, undersized pods with wrinkled, discolored seeds."
        ),
        safe_cultural_practices=[
            "Grow yellow mosaic resistant or tolerant soybean varieties recommended for the zone.",
            "Rogue out infected plants during early vegetative stages to prevent vector spread within the field.",
            "Install yellow sticky traps (10–12 traps/acre) to monitor and trap adult whiteflies.",
            "Avoid planting near other susceptible pulse and legume crops that harbor whitefly populations.",
        ],
        clarifying_observations=[
            "Are leaves showing prominent irregular bright yellow patches interspersed with green tissue?",
            "Can you see tiny whiteflies fluttering on the underside of leaves when disturbed?",
            "Are pods on affected plants stunted, scarce, or producing shriveled seeds?",
        ],
        source_id="src_tnau_crop_protection_soybean",
    ),
    KnowledgeEntry(
        entry_id="SOYBEAN-02",
        crop="Soybean",
        plant_part="fruit",
        symptom_keywords=[
            "anthracnose",
            "pod blight",
            "colletotrichum",
            "sunken brown lesions",
            "black acervuli",
            "black specks",
            "blighted pods",
            "shriveled seed",
            "stem lesions",
            "soybean anthracnose",
            "pod",
            "blight",
            "spot",
            "black",
            "brown",
        ],
        condition_name="Anthracnose / Pod Blight",
        scientific_name="Colletotrichum truncatum",
        category="fungal",
        description=(
            "Symptoms may indicate anthracnose and pod blight of soybean. Stems, petioles, and pods develop brown "
            "to dark brown, sunken, elongated lesions. Infected pods show numerous tiny, black pinhead-like fruiting bodies "
            "(acervuli) scattered over the diseased surface, often bearing minute setae visible under magnification. Pods fail "
            "to fill normally, resulting in blank pods or shriveled, moldy seeds."
        ),
        safe_cultural_practices=[
            "Use certified disease-free seed from healthy mother crops.",
            "Practice crop rotation with non-legume crops like maize, sorghum, or wheat.",
            "Perform deep summer plowing to bury crop residues and reduce inoculum survival.",
            "Ensure proper row spacing to promote canopy ventilation and reduce humidity during pod development.",
        ],
        clarifying_observations=[
            "Do pods have sunken brown patches covered with tiny black pinhead-like specks (acervuli)?",
            "Are pods failing to fill properly, containing shriveled or aborted seeds?",
            "Do stems and leaf petioles also exhibit elongated dark brown lesions?",
        ],
        source_id="src_tnau_crop_protection_soybean",
    ),
    KnowledgeEntry(
        entry_id="SOYBEAN-03",
        crop="Soybean",
        plant_part="stem",
        symptom_keywords=[
            "girdle beetle",
            "obereopsis",
            "ring cuts",
            "girdling",
            "drooping leaves",
            "wilting shoot",
            "pith tunnel",
            "petiole girdling",
            "soyabean ring beetle",
            "girdle",
            "beetle",
            "ring",
            "cuts",
            "droop",
            "drooping",
            "wilt",
            "wilting",
        ],
        condition_name="Girdle Beetle",
        scientific_name="Obereopsis brevis",
        category="pest_damage",
        description=(
            "Symptoms can indicate damage caused by the soybean girdle beetle. The female beetle cuts two characteristic "
            "parallel circular rings (girdles) around the stem, branch, or petiole, laying an egg between the rings. The portion "
            "of the plant above the girdle wilts, droops, turns brown, and dries up. The newly hatched larva tunnels downward "
            "through the central pith of the stem."
        ),
        safe_cultural_practices=[
            "Hand-pick and clip girdled petioles or plant tips containing eggs/young larvae during early infestation stages.",
            "Maintain clean field borders and destroy wild legume weeds that host girdle beetles.",
            "Avoid excessive nitrogenous fertilizer application that results in overly succulent stems.",
            "Deep summer plowing to expose diapausing larvae in the soil.",
        ],
        clarifying_observations=[
            "Do you see two distinct parallel ring cuts around the stem or leaf petiole?",
            "Is the portion of the plant or branch above the cut rings wilting and drying up?",
            "When splitting the stem, is there a larva tunneling internally through the central pith?",
        ],
        source_id="src_tnau_crop_protection_soybean",
    ),
    KnowledgeEntry(
        entry_id="SOYBEAN-04",
        crop="Soybean",
        plant_part="stem",
        symptom_keywords=[
            "stem fly",
            "melanagromyza",
            "stem maggot",
            "reddish tunnel",
            "pith tunnel",
            "seedling mortality",
            "stem borer fly",
            "petiole entry puncture",
            "stunting",
            "soybean stem fly",
            "stem",
            "tunnel",
            "wilt",
        ],
        condition_name="Stem Fly",
        scientific_name="Melanagromyza sojae",
        category="pest_damage",
        description=(
            "Symptoms may be associated with stem fly infestation. The maggot enters through the petiole and tunnels "
            "down into the main stem pith. Splitting the stem longitudinally reveals a characteristic continuous zig-zag "
            "reddish-brown to dark tunnel in the center. In young seedlings (up to 3–4 weeks), infestation causes wilting "
            "and death, while in older plants it results in stunted growth and fewer branches."
        ),
        safe_cultural_practices=[
            "Sow immediately with the onset of monsoon rains to avoid peak fly activity.",
            "Slightly increase seed rate (by 10–15%) to maintain optimum plant population despite seedling mortality.",
            "Remove and destroy wilting, infested seedlings during early inter-cultivation and weeding.",
            "Deep plowing after harvest to bury and destroy overwintering puparia.",
        ],
        clarifying_observations=[
            "Does splitting the stem lengthwise show a reddish-brown zig-zag tunnel through the central pith?",
            "Are young seedlings wilting and drying up without obvious external chewing damage?",
            "Are there minute oviposition punctures visible on the upper leaf surface near the petiole base?",
        ],
        source_id="src_tnau_crop_protection_soybean",
    ),
    KnowledgeEntry(
        entry_id="SOYBEAN-05",
        crop="Soybean",
        plant_part="leaf",
        symptom_keywords=[
            "rhizoctonia aerial blight",
            "aerial blight",
            "web blight",
            "water soaked lesions",
            "cobweb mycelium",
            "leaf blighting",
            "defoliation",
            "humid weather blight",
            "soybean web blight",
            "blight",
            "web",
            "lesion",
        ],
        condition_name="Rhizoctonia Aerial Blight",
        scientific_name="Rhizoctonia solani",
        category="fungal",
        description=(
            "Symptoms can be consistent with Rhizoctonia aerial blight (web blight), which flares during periods "
            "of high humidity and frequent monsoon rains. Lower leaves develop water-soaked, greenish-brown lesions that "
            "rapidly expand and coalesce into large irregular blighted patches. Fine, cobweb-like fungal mycelial threads "
            "spread across the canopy, sticking adjacent leaves together and causing rapid foliage blighting and severe leaf drop."
        ),
        safe_cultural_practices=[
            "Avoid dense sowing and maintain recommended spacing to facilitate sunlight penetration and canopy aeration.",
            "Ensure effective field drainage to avoid prolonged high humidity in the lower crop canopy.",
            "Practice crop rotation with non-host cereal crops such as maize or sorghum.",
            "Destroy and bury crop residue after harvest to reduce soilborne sclerotia.",
        ],
        clarifying_observations=[
            "Are neighboring blighted leaves stuck together by fine, web-like fungal threads?",
            "Are there large, water-soaked greenish-brown irregular patches on lower and middle leaves?",
            "Did the blighting spread rapidly during continuous cloudy, rainy, or highly humid weather?",
        ],
        source_id="src_tnau_crop_protection_soybean",
    ),
    # =======================================================================
    # 4. COTTON (4 Entries)
    # =======================================================================
    KnowledgeEntry(
        entry_id="COTTON-01",
        crop="Cotton",
        plant_part="fruit",
        symptom_keywords=[
            "pink bollworm",
            "pectinophora",
            "rosetted flower",
            "boll borer",
            "caterpillar in boll",
            "stained lint",
            "premature boll opening",
            "damaged seed",
            "kapas pink bollworm",
            "gulabi sundi",
            "गुलाबी सुंडी",
            "गुलाबी",
            "सुंडी",
            "boll",
            "caterpillar",
            "hole",
            "flower",
            "pink",
            "rosette",
        ],
        condition_name="Pink Bollworm",
        scientific_name="Pectinophora gossypiella",
        category="pest_damage",
        description=(
            "Symptoms can indicate pink bollworm infestation. In young flower buds, larval feeding causes petals "
            "to twist and web together into a characteristic rosette shape ('rosetted flower'). Larvae bore into developing "
            "bolls through minute holes that soon heal; inside, the pinkish caterpillar feeds on developing seeds, severing "
            "fibers, causing stained, discolored lint, and leading to premature, defective boll opening ('locule damage')."
        ),
        safe_cultural_practices=[
            "Install pheromone traps (such as gossyplure traps, 5 traps/acre) to monitor adult moth activity.",
            "Manually collect and destroy rosetted flowers and shed squares/bolls in early stages.",
            "Terminate the cotton crop within the recommended seasonal window to prevent extended off-season carryover.",
            "Promptly shred and plow under cotton stalks after final picking rather than stacking stalks near fields.",
        ],
        clarifying_observations=[
            "Do you see unopened flowers with petals twisted together in a rosette shape?",
            "When opening green bolls, are there pinkish caterpillars feeding inside the seeds and lint?",
            "Do opened bolls have stained, discolored fiber and hollowed-out seeds?",
        ],
        source_id="src_tnau_crop_protection_cotton",
    ),
    KnowledgeEntry(
        entry_id="COTTON-02",
        crop="Cotton",
        plant_part="leaf",
        symptom_keywords=[
            "cotton jassid",
            "leafhopper",
            "amrasca",
            "hopperburn",
            "downward curling",
            "leaf yellowing",
            "brick red margin",
            "bronzing",
            "crinkling",
            "kapas jassid",
            "curl",
            "curling",
            "yellow",
            "red",
        ],
        condition_name="Cotton Jassid / Leafhopper",
        scientific_name="Amrasca biguttula biguttula",
        category="pest_damage",
        description=(
            "Symptoms may be associated with cotton jassid (leafhopper) feeding. Nymphs and adults suck sap from "
            "the lower leaf surface, injecting toxic saliva. Initial symptoms include downward curling of leaf margins "
            "and chlorotic yellowing of leaf borders. In severe infestations, leaf margins turn brick-red or bronze-brown "
            "(hopper burn), with leaves becoming brittle, crinkled, and shedding prematurely."
        ),
        safe_cultural_practices=[
            "Grow jassid-tolerant cotton cultivars with hairy leaf surfaces (pilose/pubescent leaves).",
            "Avoid excessive application of nitrogenous fertilizers that promote succulent leaf growth.",
            "Install yellow sticky traps to monitor and catch adult leafhopper populations.",
            "Conserve beneficial natural predators such as ladybird beetles, green lacewings, and spiders.",
        ],
        clarifying_observations=[
            "Are small, wedge-shaped greenish leafhoppers seen moving sideways on the underside of leaves?",
            "Are leaf margins curled downwards with yellow borders turning brick-red (hopper burn)?",
            "Are the upper leaves becoming brittle, crinkled, and cupped downwards?",
        ],
        source_id="src_tnau_crop_protection_cotton",
    ),
    KnowledgeEntry(
        entry_id="COTTON-03",
        crop="Cotton",
        plant_part="leaf",
        symptom_keywords=[
            "bacterial blight",
            "angular leaf spot",
            "xanthomonas",
            "black arm",
            "water soaked angular spots",
            "vein bounded lesions",
            "boll rot spots",
            "kapas bacterial blight",
            "angular",
            "spot",
            "spots",
            "black",
            "blight",
        ],
        condition_name="Bacterial Blight / Angular Leaf Spot",
        scientific_name="Xanthomonas citri pv. malvacearum",
        category="bacterial",
        description=(
            "Symptoms can be consistent with bacterial blight (angular leaf spot / black arm phase). On leaves, "
            "small, water-soaked angular spots appear, strictly bounded by leaf veinlets, which later turn dark brown to black. "
            "On stems and branches, elongated black sunken lesions develop ('black arm'), weakening branches so they easily break "
            "under wind or fruit load. On bolls, round, water-soaked, dark sunken spots develop."
        ),
        safe_cultural_practices=[
            "Use certified disease-free, acid-delinted cotton seeds.",
            "Collect and burn infected crop residues after harvest to eliminate overwintering bacterial inoculum.",
            "Maintain wider row spacing to improve canopy ventilation and accelerate leaf drying.",
            "Practice crop rotation with non-host crops such as cereals or pulses.",
        ],
        clarifying_observations=[
            "Are leaf spots sharply angular and strictly delimited by the small leaf veins?",
            "Are branches or stems developing elongated black girdling lesions (black arm phase)?",
            "Are bolls showing circular, water-soaked sunken dark spots?",
        ],
        source_id="src_tnau_crop_protection_cotton",
    ),
    KnowledgeEntry(
        entry_id="COTTON-04",
        crop="Cotton",
        plant_part="fruit",
        symptom_keywords=[
            "cotton boll rot",
            "boll rot",
            "boll rotting",
            "water soaked boll",
            "moldy boll",
            "black boll",
            "matted lint",
            "decayed lint",
            "rotting bolls in rain",
            "boll",
            "rot",
            "rotting",
            "decay",
        ],
        condition_name="Cotton Boll Rot",
        scientific_name="Colletotrichum / Fusarium / Rhizoctonia complex",
        category="fungal",
        description=(
            "Symptoms may indicate cotton boll rot, caused by a complex of fungal and bacterial pathogens following "
            "insect punctures or high canopy humidity. Bolls develop water-soaked, dark brown to black rotting lesions starting "
            "near the bracts or insect entry holes. The internal locules, developing seeds, and lint decay into a brownish, moldy, "
            "discolored mass. Infected bolls fail to open or open prematurely with matted, stained, unharvestable lint."
        ),
        safe_cultural_practices=[
            "Manage sucking pests and caterpillars whose feeding punctures provide infection courts for boll rot fungi.",
            "Avoid dense vegetative growth by regulating nitrogen application and performing timely topping.",
            "Ensure proper field drainage and adopt wider spacing to improve light penetration and air movement in the lower canopy.",
            "Collect and destroy rotted bolls to limit fungal sporulation in the field.",
        ],
        clarifying_observations=[
            "Are green bolls turning brown or black and rotting from the base or insect puncture sites?",
            "When cutting open rotting bolls, is the internal lint moldy, stained, or slimy?",
            "Is the boll rot more severe in the dense, shaded lower canopy during humid or rainy weather?",
        ],
        source_id="src_tnau_crop_protection_cotton",
    ),
    # =======================================================================
    # 5. SUGARCANE (4 Entries)
    # =======================================================================
    KnowledgeEntry(
        entry_id="SUGARCANE-01",
        crop="Sugarcane",
        plant_part="stem",
        symptom_keywords=[
            "red rot",
            "colletotrichum falcatum",
            "red internal tissue",
            "transverse white patches",
            "white bands",
            "alcoholic smell",
            "sour odor",
            "drying crown",
            "midrib lesions",
            "ganna red rot",
            "लाल",
            "सफेद",
            "सफ़ेद",
            "पट्टियां",
            "red",
            "rot",
            "sour",
            "white",
            "dry",
        ],
        condition_name="Red Rot",
        scientific_name="Colletotrichum falcatum",
        category="fungal",
        description=(
            "Symptoms can be consistent with red rot of sugarcane. Earliest foliar signs include yellowing and drying "
            "of the 3rd and 4th leaves from the spindle, followed by complete drying of the cane crown. When diseased stalks "
            "are split longitudinally, the internal pith tissue shows bright red discoloration interspersed with diagnostic "
            "transverse white patches or bands across the red area, emitting a distinct sour, alcoholic smell."
        ),
        safe_cultural_practices=[
            "Use certified disease-free seed setts obtained from disease-free seed nurseries.",
            "Discard seed setts displaying red discoloration at the cut ends or internal tissue.",
            "Rogue out and destroy entire infected cane clumps along with root systems.",
            "Avoid ratooning severely red rot-affected fields.",
            "Ensure proper surface drainage and avoid letting irrigation water flow from diseased to healthy fields.",
        ],
        clarifying_observations=[
            "Does splitting the cane stalk lengthwise reveal bright red internal tissue with transverse white patches?",
            "Does the split diseased cane give off a sour, alcoholic or fermenting smell?",
            "Are there red lesions with straw-colored centers visible on the midrib of upper leaves?",
        ],
        source_id="src_tnau_crop_protection_sugarcane",
    ),
    KnowledgeEntry(
        entry_id="SUGARCANE-02",
        crop="Sugarcane",
        plant_part="stem",
        symptom_keywords=[
            "sugarcane smut",
            "smut",
            "sporisorium",
            "black whip",
            "smut whip",
            "sooty spores",
            "terminal whip",
            "grassy tillers",
            "thin canes",
            "ganna kandwa",
            "whip",
            "black",
            "spores",
        ],
        condition_name="Sugarcane Smut",
        scientific_name="Sporisorium scitamineum",
        category="fungal",
        description=(
            "Symptoms may be associated with sugarcane smut. The diagnostic symptom is the emergence of a long, "
            "unbranched, curved whip-like structure from the central terminal shoot spindle. The whip, which can reach several "
            "feet in length, is initially enveloped in a silvery membrane that ruptures to release millions of powdery, "
            "black sooty fungal spores (teliospores). Affected clumps produce numerous thin, grassy, stunted shoots with narrow leaves."
        ),
        safe_cultural_practices=[
            "Carefully rogue out smutted whips by covering them with a cloth or plastic bag before cutting to prevent spore dissemination, then destroy them by burning.",
            "Use disease-free seed setts from certified nurseries.",
            "Avoid ratooning smut-infested crop stands.",
            "Plant smut-resistant or tolerant sugarcane cultivars adapted to the region.",
        ],
        clarifying_observations=[
            "Is there a prominent black, curved, whip-like structure emerging from the top shoot spindle?",
            "Is the whip shedding powdery, black sooty spores when disturbed?",
            "Is the clump producing numerous thin, stunted, grassy shoots?",
        ],
        source_id="src_tnau_crop_protection_sugarcane",
    ),
    KnowledgeEntry(
        entry_id="SUGARCANE-03",
        crop="Sugarcane",
        plant_part="leaf",
        symptom_keywords=[
            "yellow leaf disease",
            "yld",
            "scylv",
            "yellow midrib",
            "midrib yellowing",
            "leaf lamina chlorosis",
            "pinkish midrib",
            "aphid vector",
            "spindle leaf green",
            "ganna yld",
            "yellow",
            "midrib",
            "leaf",
        ],
        condition_name="Yellow Leaf Disease (YLD)",
        scientific_name="Sugarcane yellow leaf virus",
        category="viral",
        description=(
            "Symptoms can be consistent with Yellow Leaf Disease (YLD) of sugarcane, transmitted by the sugarcane "
            "aphid (Melanaphis sacchari). Conspicuous yellowing develops along the central midrib on the lower surface of mature "
            "leaves (3rd to 5th leaves from the spindle). The yellowing gradually diffuses outward across the leaf blade while "
            "younger top leaves remain green. In severe cases, the midrib develops a reddish-pink discoloration on the upper surface."
        ),
        safe_cultural_practices=[
            "Use certified virus-free seed setts produced through tissue culture or disease-free nurseries.",
            "Maintain regular field sanitation and weed management to eliminate alternate aphid hosts.",
            "Provide balanced crop nutrition and avoid drought stress which intensifies symptom severity.",
            "Rogue out severely affected, stunted clumps in plant crops.",
        ],
        clarifying_observations=[
            "Is there prominent bright yellowing along the midrib of mature leaves (3rd to 5th leaf from top)?",
            "Is the yellowing spreading from the midrib into the leaf blade while young spindle leaves remain green?",
            "Do the yellowed midribs show reddish-pink discoloration on the upper leaf surface?",
        ],
        source_id="src_tnau_crop_protection_sugarcane",
    ),
    KnowledgeEntry(
        entry_id="SUGARCANE-04",
        crop="Sugarcane",
        plant_part="stem",
        symptom_keywords=[
            "early shoot borer",
            "chilo infuscatellus",
            "dead heart",
            "foul smell dead heart",
            "easily pulled dead heart",
            "borer entry hole at ground",
            "young shoot borer",
            "ganna shoot borer",
            "shoot",
            "dead",
            "borer",
            "hole",
        ],
        condition_name="Early Shoot Borer",
        scientific_name="Chilo infuscatellus",
        category="pest_damage",
        description=(
            "Symptoms can indicate damage by the early shoot borer during early vegetative growth (1 to 3 months "
            "after planting). The caterpillar enters the shoot near ground level and bores into the central growing point, "
            "killing the shoot and producing a dried 'dead heart'. The dead central shoot can be pulled out effortlessly by hand "
            "and gives off an offensive, rotting foul odor at its decaying severed base. Small bored entrance holes are visible near the soil level."
        ),
        safe_cultural_practices=[
            "Plant seed setts in deep trenches or furrows with light earthing-up at 30–45 days to cover borer entrance points.",
            "Apply sugarcane trash mulching (10–15 cm thick) along furrows to conserve soil moisture and suppress borer population.",
            "Install pheromone traps (4–5 traps/acre) to monitor adult moth activity.",
            "Remove dead hearts and destroy infesting caterpillars during early weeding operations.",
        ],
        clarifying_observations=[
            "Can the dried central shoot (dead heart) be pulled out easily with a foul rotting smell at the base?",
            "Are there small entrance holes bored into the shoot base near the ground level?",
            "Did symptoms appear during early shoot tillering (within first 1 to 3 months of planting)?",
        ],
        source_id="src_tnau_crop_protection_sugarcane",
    ),
]
