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
"""Phase 5D Batch 1 Verified Production Agricultural Knowledge Data.

Provides verified reference records for the first 5 validation crops:
1. Rice (6 entries)
2. Wheat (5 entries - WHEAT-06 removed)
3. Maize (6 entries - MAIZE-06 corrected to Sorghum Downy Mildew)
4. Chickpea (6 entries)
5. Mustard (6 entries)

Total: 29 verified entries across 5 verified institutional sources.

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
# Batch 1 Verified Source Provenance Records (5 Verified TNAU Extension Portals)
# ---------------------------------------------------------------------------

BATCH1_SOURCES: dict[str, KnowledgeSourceProvenance] = {
    "src_tnau_crop_protection_rice": KnowledgeSourceProvenance(
        source_id="src_tnau_crop_protection_rice",
        organization="Tamil Nadu Agricultural University (TNAU)",
        document_title="TNAU Agritech Portal: Crop Protection — Rice Diseases and Insect Pests",
        version_or_year="2024",
        source_url="https://agritech.tnau.ac.in/crop_protection/crop_prot.html",
        license_or_usage_terms="State Agricultural University open agricultural extension portal; factual symptom and cultural IPM extraction with institutional attribution",
        retrieval_date="2026-09-28",
        crops_covered=["Rice"],
        disease_topics=[
            "Yellow Stem Borer",
            "Rice Leaf Folder",
            "Rice Blast",
            "Rice Brown Spot",
            "Bacterial Leaf Blight",
            "Rice Sheath Blight",
        ],
        attribution_requirement="Tamil Nadu Agricultural University (TNAU) Agritech Portal, Coimbatore",
        redistribution_status="bundled_permitted",
    ),
    "src_tnau_crop_protection_wheat": KnowledgeSourceProvenance(
        source_id="src_tnau_crop_protection_wheat",
        organization="Tamil Nadu Agricultural University (TNAU)",
        document_title="TNAU Agritech Portal: Crop Protection — Wheat Diseases (Cereals)",
        version_or_year="2024",
        source_url="https://agritech.tnau.ac.in/crop_protection/crop_prot.html",
        license_or_usage_terms="State Agricultural University open agricultural extension portal; factual symptom extraction with institutional attribution",
        retrieval_date="2026-09-28",
        crops_covered=["Wheat"],
        disease_topics=[
            "Brown Rust",
            "Yellow Rust",
            "Stem Rust",
            "Loose Smut",
            "Powdery Mildew",
        ],
        attribution_requirement="Tamil Nadu Agricultural University (TNAU) Agritech Portal, Coimbatore",
        redistribution_status="bundled_permitted",
    ),
    "src_tnau_crop_protection_maize": KnowledgeSourceProvenance(
        source_id="src_tnau_crop_protection_maize",
        organization="Tamil Nadu Agricultural University (TNAU)",
        document_title="TNAU Agritech Portal: Crop Protection — Maize Diseases and Pests (Cereals)",
        version_or_year="2024",
        source_url="https://agritech.tnau.ac.in/crop_protection/crop_prot.html",
        license_or_usage_terms="State Agricultural University open agricultural extension portal; factual symptom and cultural IPM extraction with institutional attribution",
        retrieval_date="2026-09-28",
        crops_covered=["Maize"],
        disease_topics=[
            "Fall Armyworm",
            "Maize Stem Borer",
            "Maize Shoot Fly",
            "Turcicum Leaf Blight",
            "Sorghum Downy Mildew",
            "Maize Stalk Rot",
        ],
        attribution_requirement="Tamil Nadu Agricultural University (TNAU) Agritech Portal, Coimbatore",
        redistribution_status="bundled_permitted",
    ),
    "src_tnau_crop_protection_bengalgram": KnowledgeSourceProvenance(
        source_id="src_tnau_crop_protection_bengalgram",
        organization="Tamil Nadu Agricultural University (TNAU)",
        document_title="TNAU Agritech Portal: Crop Protection — Bengalgram / Chickpea Diseases and Pests (Pulses)",
        version_or_year="2024",
        source_url="https://agritech.tnau.ac.in/crop_protection/crop_prot.html",
        license_or_usage_terms="State Agricultural University open agricultural extension portal; factual symptom and cultural IPM extraction with institutional attribution",
        retrieval_date="2026-09-28",
        crops_covered=["Chickpea"],
        disease_topics=[
            "Gram Pod Borer",
            "Fusarium Wilt",
            "Ascochyta Blight",
            "Dry Root Rot",
            "Botrytis Gray Mold",
            "Powdery Mildew",
        ],
        attribution_requirement="Tamil Nadu Agricultural University (TNAU) Agritech Portal, Coimbatore",
        redistribution_status="bundled_permitted",
    ),
    "src_tnau_crop_protection_mustard": KnowledgeSourceProvenance(
        source_id="src_tnau_crop_protection_mustard",
        organization="Tamil Nadu Agricultural University (TNAU)",
        document_title="TNAU Agritech Portal: Crop Protection — Mustard Diseases and Pests (Oilseeds)",
        version_or_year="2024",
        source_url="https://agritech.tnau.ac.in/crop_protection/crop_prot.html",
        license_or_usage_terms="State Agricultural University open agricultural extension portal; factual symptom and cultural IPM extraction with institutional attribution",
        retrieval_date="2026-09-28",
        crops_covered=["Mustard"],
        disease_topics=[
            "Mustard Aphid",
            "Diamondback Moth",
            "Mustard Leaf Miner",
            "White Rust",
            "Alternaria Blight",
            "Downy Mildew",
        ],
        attribution_requirement="Tamil Nadu Agricultural University (TNAU) Agritech Portal, Coimbatore",
        redistribution_status="bundled_permitted",
    ),
}

# ---------------------------------------------------------------------------
# Batch 1 Verified Knowledge Entries (29 Records across 5 crops)
# ---------------------------------------------------------------------------

BATCH1_ENTRIES: list[KnowledgeEntry] = [
    # =======================================================================
    # 1. RICE (6 Entries)
    # =======================================================================
    KnowledgeEntry(
        entry_id="RICE-01",
        crop="Rice",
        plant_part="stem",
        symptom_keywords=[
            "dead heart",
            "dead-heart",
            "white ear",
            "whitehead",
            "stem",
            "borer",
            "larva",
            "drying central shoot",
            "empty panicle",
            "chaffy panicle",
            "dry",
            "shoot",
            "panicle",
        ],
        condition_name="Yellow Stem Borer",
        scientific_name="Scirpophaga incertulas",
        category="pest_damage",
        description=(
            "Symptoms are consistent with Yellow Stem Borer infestation. In the vegetative crop stage, "
            "caterpillar feeding inside the stem causes the central shoot to dry and die, producing a 'dead heart'. "
            "In the reproductive/heading stage, larval stem damage prevents grain filling, resulting in erect, "
            "chaffy, whitish empty panicles known as 'white ear'."
        ),
        safe_cultural_practices=[
            "Monitor field regularly for egg masses on leaf tips and white moths.",
            "Clip seedling leaf tips before transplanting if egg masses are observed.",
            "Harvest crop close to the ground level and plow under stubbles to destroy overwintering larvae.",
            "Encourage natural predators such as dragonflies and spiders by avoiding broad-spectrum chemical sprays.",
        ],
        clarifying_observations=[
            "Is the crop currently in the vegetative stage with dying central shoots, or in the heading stage with whitish empty panicles?",
            "Can the dried central shoot be easily pulled out by hand?",
        ],
        source_id="src_tnau_crop_protection_rice",
    ),
    KnowledgeEntry(
        entry_id="RICE-02",
        crop="Rice",
        plant_part="leaf",
        symptom_keywords=[
            "folded leaves",
            "rolled leaves",
            "leaf folder",
            "leaf roller",
            "longitudinal fold",
            "white dry patches",
            "white streaks",
            "scraped leaf",
            "feeding streaks",
            "fold",
            "rolled",
            "folded",
            "dry",
            "streak",
            "white",
        ],
        condition_name="Rice Leaf Folder",
        scientific_name="Cnaphalocrocis medinalis",
        category="pest_damage",
        description=(
            "Symptoms may indicate Rice Leaf Folder damage. Larvae roll or fold leaf blades longitudinally "
            "and fasten leaf edges with silk threads, feeding on green chlorophyll inside the fold. "
            "This creates longitudinal whitish, papery, dry feeding streaks and scorched-looking patches across the foliage."
        ),
        safe_cultural_practices=[
            "Scout for folded leaves and adult moths during tillering and panicle initiation stages.",
            "Avoid excessive application of nitrogen fertilizers, which promotes lush succulent growth favorable to leaf folders.",
            "Conserve natural biological control agents such as predatory beetles and larval parasitoids.",
        ],
        clarifying_observations=[
            "Are the leaf edges folded or rolled together with visible white feeding streaks inside?",
            "Do you see green larvae or frass inside the folded leaf tubes?",
        ],
        source_id="src_tnau_crop_protection_rice",
    ),
    KnowledgeEntry(
        entry_id="RICE-03",
        crop="Rice",
        plant_part="leaf",
        symptom_keywords=[
            "spindle-shaped lesions",
            "spindle",
            "diamond-shaped spots",
            "grey center",
            "gray center",
            "brown margin",
            "blast",
            "leaf blast",
            "neck blast",
            "node blast",
            "spot",
            "spots",
            "lesion",
            "lesions",
            "oval",
        ],
        condition_name="Rice Blast",
        scientific_name="Magnaporthe oryzae",
        category="fungal",
        description=(
            "Symptoms are consistent with Rice Blast. On leaves, initial lesions appear as small bluish-green "
            "flecks that enlarge into characteristic spindle-shaped or diamond-shaped spots with grey or whitish "
            "centers and dark brown to reddish-brown margins. Severe foliar blast can cause leaf drying and "
            "coalescing blight, and infection may also affect leaf collars, stem nodes, or the panicle neck."
        ),
        safe_cultural_practices=[
            "Avoid excessive or single heavy applications of nitrogen fertilizer; apply nitrogen in split doses based on crop demand.",
            "Ensure proper spacing during transplanting to facilitate canopy aeration and reduce relative humidity.",
            "Maintain field sanitation by removing crop residues and destroying infected weed hosts around bunds.",
            "Use certified clean seeds from disease-free fields.",
        ],
        clarifying_observations=[
            "Are the lesions spindle-shaped (pointed at both ends) with a grey center and darker brown border?",
            "Do you observe blackening or lesions at the stem nodes or neck of the panicle?",
        ],
        source_id="src_tnau_crop_protection_rice",
    ),
    KnowledgeEntry(
        entry_id="RICE-04",
        crop="Rice",
        plant_part="leaf",
        symptom_keywords=[
            "brown spot",
            "oval lesions",
            "circular brown spots",
            "yellow halo",
            "yellowish halo",
            "sesame shaped",
            "seedling blight",
            "brown spots",
            "brown",
            "spot",
            "spots",
            "oval",
        ],
        condition_name="Rice Brown Spot",
        scientific_name="Bipolaris oryzae",
        category="fungal",
        description=(
            "Symptoms may be associated with Rice Brown Spot. Leaf lesions are typically circular to oval "
            "or sesame-seed shaped, dark brown with a distinct yellowish halo surrounding the spot. Centers of older "
            "spots may turn light brown or greyish. In severe infections, numerous spots coalesce leading to "
            "extensive leaf discoloration and drying."
        ),
        safe_cultural_practices=[
            "Ensure balanced soil nutrition including adequate potassium and micronutrients, as brown spot is often aggravated by nutrient-deficient soils.",
            "Provide proper water management to prevent prolonged soil moisture stress or drought in upland/rainfed plots.",
            "Use certified disease-free seed and clean field bunds of collateral grass weed hosts.",
        ],
        clarifying_observations=[
            "Are the spots small, oval to circular with a prominent yellowish halo around the brown center?",
            "Is the field experiencing soil moisture stress or suspected nutrient deficiency?",
        ],
        source_id="src_tnau_crop_protection_rice",
    ),
    KnowledgeEntry(
        entry_id="RICE-05",
        crop="Rice",
        plant_part="leaf",
        symptom_keywords=[
            "bacterial leaf blight",
            "water-soaked lesions",
            "yellowing leaf margins",
            "wavy margin",
            "kresek",
            "bacterial blight",
            "leaf drying",
            "straw-colored leaves",
            "yellow",
            "blight",
            "dry",
            "water-soaked",
        ],
        condition_name="Bacterial Leaf Blight",
        scientific_name="Xanthomonas oryzae pv. oryzae",
        category="bacterial",
        description=(
            "Symptoms are consistent with Bacterial Leaf Blight. Early symptoms appear as water-soaked "
            "translucent stripes along leaf margins near the leaf tip. Lesions enlarge and turn yellowish-orange "
            "with wavy margins, progressively advancing down the blade and turning straw-colored to greyish-white "
            "as leaves dry out. In young seedlings, systemic wilting ('kresek') may occur."
        ),
        safe_cultural_practices=[
            "Avoid clipping seedling tips if bacterial blight is endemic in the locality.",
            "Drain excess water from the field temporarily if safe for the crop, as stagnant water and splashing rain accelerate bacterial spread.",
            "Avoid heavy or late applications of nitrogenous fertilizers.",
            "Ensure field sanitation by removing stubbles and wild host grasses on field embankments.",
        ],
        clarifying_observations=[
            "Did the lesions begin at the leaf tip or margins and progress downwards with wavy edges?",
            "Do the affected leaf areas turn dry, pale yellow to straw-white?",
        ],
        source_id="src_tnau_crop_protection_rice",
    ),
    KnowledgeEntry(
        entry_id="RICE-06",
        crop="Rice",
        plant_part="stem",
        symptom_keywords=[
            "sheath blight",
            "water level lesions",
            "greenish-grey lesions",
            "irregular spots",
            "banded appearance",
            "sheath lesions",
            "snake skin pattern",
            "sheath",
            "blight",
            "spot",
            "spots",
        ],
        condition_name="Rice Sheath Blight",
        scientific_name="Rhizoctonia solani",
        category="fungal",
        description=(
            "Symptoms may indicate Rice Sheath Blight. Infection typically initiates on the leaf sheath near the "
            "water or soil line as oval or oblong water-soaked greenish-grey lesions. As lesions enlarge, they develop "
            "irregular margins with dark reddish-brown borders and greyish-white centers, creating a banded or "
            "'snake skin' pattern that progresses upwards onto upper leaf sheaths and blades under dense canopy conditions."
        ),
        safe_cultural_practices=[
            "Maintain optimal plant spacing during transplanting to avoid overly dense canopies that trap high humidity.",
            "Avoid excessive nitrogen fertilization that creates dense foliage.",
            "Drain excess standing water periodically to facilitate soil surface aeration where feasible.",
            "Remove infected weed hosts and clean field bunds before the season.",
        ],
        clarifying_observations=[
            "Did the lesions start on the lower leaf sheath near the water line and move upwards?",
            "Do the spots display an irregular banded pattern with grey centers and brown borders?",
        ],
        source_id="src_tnau_crop_protection_rice",
    ),
    # =======================================================================
    # 2. WHEAT (5 Entries - WHEAT-06 Removed)
    # =======================================================================
    KnowledgeEntry(
        entry_id="WHEAT-01",
        crop="Wheat",
        plant_part="leaf",
        symptom_keywords=[
            "brown rust",
            "leaf rust",
            "orange pustules",
            "brown pustules",
            "circular pustules",
            "scattered pustules",
            "orange-brown spots",
            "powder on leaf",
            "brown",
            "rust",
            "spot",
            "spots",
            "orange",
        ],
        condition_name="Brown Rust / Leaf Rust",
        scientific_name="Puccinia triticina",
        category="fungal",
        description=(
            "Symptoms are consistent with Brown / Leaf Rust of wheat. Circular to elliptical, small, bright "
            "orange to orange-brown pustules (uredinia) appear scattered irregularly over the upper surface of leaf blades. "
            "Pustules erupt through the leaf epidermis to release powdery orange spores, and affected leaves may dry "
            "prematurely in severe infections."
        ),
        safe_cultural_practices=[
            "Grow recommended rust-resistant wheat varieties suited to the agro-ecological zone.",
            "Avoid late sowing to minimize exposure to peak ambient temperatures and spore dispersal.",
            "Maintain regular crop scouting, especially on early-sown border rows.",
            "Follow balanced fertilization and avoid excessive vegetative nitrogen push.",
        ],
        clarifying_observations=[
            "Are the orange-brown pustules scattered randomly across the leaf surface rather than in distinct straight lines?",
            "Does an orange-brown powder rub off onto fingers or paper when touching the leaf?",
        ],
        source_id="src_tnau_crop_protection_wheat",
    ),
    KnowledgeEntry(
        entry_id="WHEAT-02",
        crop="Wheat",
        plant_part="leaf",
        symptom_keywords=[
            "yellow rust",
            "stripe rust",
            "yellow stripes",
            "linear pustules",
            "narrow stripes",
            "yellow pustules",
            "beaded stripes",
            "parallel stripes",
            "yellow",
            "rust",
            "stripe",
            "stripes",
            "streak",
        ],
        condition_name="Yellow Rust / Stripe Rust",
        scientific_name="Puccinia striiformis",
        category="fungal",
        description=(
            "Symptoms are consistent with Yellow / Stripe Rust of wheat. Bright yellow to orange-yellow pustules "
            "develop in characteristic long, narrow, parallel linear stripes along the veins of leaf blades, resembling "
            "rows of beads. Under cool, humid conditions, stripes can also develop on leaf sheaths, stems, and glumes."
        ),
        safe_cultural_practices=[
            "Sow certified stripe-rust-resistant varieties recommended for cool northern and northwestern plains zones.",
            "Scout fields early in the season (December–February) for initial yellow focal patches.",
            "Avoid excessive nitrogen application that produces lush, dense canopies.",
            "Ensure balanced irrigation and avoid water stagnation.",
        ],
        clarifying_observations=[
            "Are the yellow pustules arranged in distinct, narrow parallel stripes along the leaf veins?",
            "Are symptoms appearing in localized patches during cool weather?",
        ],
        source_id="src_tnau_crop_protection_wheat",
    ),
    KnowledgeEntry(
        entry_id="WHEAT-03",
        crop="Wheat",
        plant_part="stem",
        symptom_keywords=[
            "black rust",
            "stem rust",
            "dark brown pustules",
            "reddish-brown pustules",
            "stem pustules",
            "torn epidermis",
            "spikes",
            "dark lesions stem",
            "black",
            "rust",
            "stem",
        ],
        condition_name="Stem Rust / Black Rust",
        scientific_name="Puccinia graminis f. sp. tritici",
        category="fungal",
        description=(
            "Symptoms may indicate Stem / Black Rust of wheat. Large, elongated, reddish-brown to dark brown "
            "pustules appear primarily on the stems, leaf sheaths, and to a lesser extent on leaf blades and spikes. "
            "The pustules erupt through the epidermis leaving prominent ragged, torn tissue margins, turning blackish as the crop matures."
        ),
        safe_cultural_practices=[
            "Plant recommended stem-rust-resistant cultivars suited to central and peninsular India.",
            "Adopt timely sowing to escape late-season warming and rust development.",
            "Scout stems and leaf sheaths regularly as temperatures begin to rise.",
        ],
        clarifying_observations=[
            "Are the elongated dark pustules primarily located on the stems and leaf sheaths with torn epidermis edges?",
            "Do the pustules turn dark blackish-brown as the plant matures?",
        ],
        source_id="src_tnau_crop_protection_wheat",
    ),
    KnowledgeEntry(
        entry_id="WHEAT-04",
        crop="Wheat",
        plant_part="panicle",
        symptom_keywords=[
            "loose smut",
            "black spores",
            "smutted earhead",
            "sooty head",
            "bare rachis",
            "black powder ear",
            "damaged inflorescence",
            "earhead",
            "black",
            "spores",
            "smut",
            "head",
            "sooty",
        ],
        condition_name="Loose Smut",
        scientific_name="Ustilago tritici",
        category="fungal",
        description=(
            "Symptoms are consistent with Loose Smut of wheat. The normal earhead/inflorescence is completely "
            "transformed into a loose, dark brown to powdery black mass of smut spores. The spores are initially "
            "covered by a thin silvery membrane that ruptures before ear emergence, causing the black powdery mass "
            "to blow away in the wind and leaving only a bare central floral axis (rachis)."
        ),
        safe_cultural_practices=[
            "Use certified disease-free seed sourced from certified agencies.",
            "Rogue out and destroy affected smutted heads by enclosing them carefully in paper bags before spores blow away.",
            "Practice solar heat treatment of seeds in summer where recommended by extension services.",
        ],
        clarifying_observations=[
            "Has the entire earhead been replaced by a dark sooty mass of black powder?",
            "Is only the bare central stalk (rachis) left after the black powder blows off?",
        ],
        source_id="src_tnau_crop_protection_wheat",
    ),
    KnowledgeEntry(
        entry_id="WHEAT-05",
        crop="Wheat",
        plant_part="leaf",
        symptom_keywords=[
            "powdery mildew",
            "white powdery growth",
            "greyish white powder",
            "powdery patches",
            "cottony growth",
            "mildew",
            "white patches",
            "powdery",
            "powder",
            "white",
        ],
        condition_name="Powdery Mildew",
        scientific_name="Blumeria graminis f. sp. tritici",
        category="fungal",
        description=(
            "Symptoms may indicate Powdery Mildew of wheat. Superficial, fluffy, white to greyish-white powdery "
            "patches develop on the upper surface of leaves, leaf sheaths, and sometimes on stems and floral parts. "
            "As the crop matures, the powdery growth turns dull grey to brownish and may develop tiny black fruiting bodies "
            "(cleistothecia), causing underlying leaf tissue to yellow and senesce early."
        ),
        safe_cultural_practices=[
            "Avoid overly dense crop canopies and excessive nitrogenous fertilization.",
            "Ensure proper crop spacing to promote air movement and lower canopy relative humidity.",
            "Monitor lower leaves in dense, shaded areas of the field during cool, cloudy periods.",
        ],
        clarifying_observations=[
            "Is there a white to greyish powdery, cottony coating visible on the leaf surface?",
            "Can the powdery layer be rubbed off with your fingers leaving yellowed tissue underneath?",
        ],
        source_id="src_tnau_crop_protection_wheat",
    ),
    # =======================================================================
    # 3. MAIZE (6 Entries - MAIZE-06 corrected to Sorghum Downy Mildew)
    # =======================================================================
    KnowledgeEntry(
        entry_id="MAIZE-01",
        crop="Maize",
        plant_part="leaf",
        symptom_keywords=[
            "fall armyworm",
            "central whorl feeding",
            "leaf scraping",
            "whorl damage",
            "caterpillar in whorl",
            "frass in whorl",
            "tassel damage",
            "cob feeding",
            "ragged holes",
            "whorl",
            "caterpillar",
            "hole",
            "holes",
            "frass",
            "scraping",
        ],
        condition_name="Fall Armyworm",
        scientific_name="Spodoptera frugiperda",
        category="pest_damage",
        description=(
            "Symptoms are consistent with Fall Armyworm infestation. Young larvae cause windowpane-like feeding "
            "scratches and pinholes on leaves. As larvae mature, they feed voraciously deep inside the central leaf whorl, "
            "producing large ragged holes, chewed leaf margins, and copious sawdust-like fecal matter (frass). "
            "Later stages may also damage emerging tassels, silk, and ear cobs."
        ),
        safe_cultural_practices=[
            "Scout fields weekly from seedling emergence, inspecting the central whorls for early pinholes and frass.",
            "Apply clean river sand or wood ash into the leaf whorls of affected plants to physically deter caterpillars.",
            "Install pheromone traps (5 traps/acre) for monitoring adult moth flight activity.",
            "Adopt intercropping with non-host pulses (e.g., cowpea) and maintain deep summer plowing.",
        ],
        clarifying_observations=[
            "Do you see ragged chewed holes and sawdust-like frass inside the central leaf whorl?",
            "Is there an active caterpillar with an inverted 'Y' mark on the head visible in the whorl?",
        ],
        source_id="src_tnau_crop_protection_maize",
    ),
    KnowledgeEntry(
        entry_id="MAIZE-02",
        crop="Maize",
        plant_part="stem",
        symptom_keywords=[
            "stem borer",
            "dead heart maize",
            "shot holes",
            "pin holes in lines",
            "stem boring",
            "tunnelling",
            "caterpillar borer",
            "transverse holes",
            "stem",
            "borer",
            "hole",
            "holes",
            "dead heart",
        ],
        condition_name="Maize Stem Borer",
        scientific_name="Chilo partellus",
        category="pest_damage",
        description=(
            "Symptoms may indicate Maize Stem Borer damage. Young larvae feed inside the unfolded whorl leaves, "
            "producing characteristic horizontal lines of circular 'shot holes' across expanded leaves. Larvae then bore into "
            "the stem, causing central shoot drying known as 'dead heart' in young plants (up to 30 days old) and internal stem tunneling in older plants."
        ),
        safe_cultural_practices=[
            "Destroy and burn or compost stubbles and crop residues after harvest to kill diapausing larvae.",
            "Remove and destroy plants showing typical dead hearts during early crop growth.",
            "Intercrop maize with cowpea or lablab to reduce borer incidence.",
            "Avoid delayed or staggered sowings in neighboring fields.",
        ],
        clarifying_observations=[
            "Do the expanded leaves show transverse rows of small circular shot-holes?",
            "Is the central growing point dried up into a dead heart in young seedlings?",
        ],
        source_id="src_tnau_crop_protection_maize",
    ),
    KnowledgeEntry(
        entry_id="MAIZE-03",
        crop="Maize",
        plant_part="stem",
        symptom_keywords=[
            "shoot fly",
            "seedling dead heart",
            "young shoot damage",
            "maggot in shoot",
            "rotted growing point",
            "foul odor shoot",
            "seedling drying",
            "shoot",
            "dead heart",
            "rot",
            "dry",
            "maggot",
        ],
        condition_name="Maize Shoot Fly",
        scientific_name="Atherigona soccata",
        category="pest_damage",
        description=(
            "Symptoms are consistent with Shoot Fly damage on young maize seedlings (first 2–4 weeks after germination). "
            "Maggots enter through the leaf sheath and feed on the apical growing point, causing the central leaf to "
            "wither, dry, and rot, producing a dead heart. A foul odor may be detected from the decaying shoot base, "
            "and affected seedlings often produce unproductive side tillers."
        ),
        safe_cultural_practices=[
            "Sow crop early immediately after the onset of monsoon to avoid peak shoot fly activity.",
            "Increase seed rate slightly (by 10–15%) and rogue out dead-heart seedlings during thinning at 2 weeks.",
            "Maintain proper field sanitation and optimal early crop vigor.",
        ],
        clarifying_observations=[
            "Is the damage occurring on very young seedlings within 2 to 4 weeks of germination?",
            "Does pulling the dried central shoot release a soft, decaying base with an offensive odor?",
        ],
        source_id="src_tnau_crop_protection_maize",
    ),
    KnowledgeEntry(
        entry_id="MAIZE-04",
        crop="Maize",
        plant_part="leaf",
        symptom_keywords=[
            "turcicum leaf blight",
            "cigar shaped lesions",
            "long elliptical lesions",
            "tan lesions",
            "grey-green lesions",
            "leaf blight",
            "lower leaf lesions",
            "cigar lesions",
            "blight",
            "oval",
            "cigar",
            "lesion",
            "lesions",
        ],
        condition_name="Turcicum Leaf Blight / Northern Corn Leaf Blight",
        scientific_name="Exserohilum turcicum",
        category="fungal",
        description=(
            "Symptoms are consistent with Turcicum Leaf Blight. Characteristic symptoms are long, elliptical "
            "or cigar-shaped lesions (2.5 to 15 cm long) with grey-green to tan or straw coloration. Lesions typically "
            "appear first on lower leaves and progress upwards. In severe infections, lesions coalesce, causing extensive foliar "
            "scorching and premature drying of the canopy."
        ),
        safe_cultural_practices=[
            "Plant resistant or tolerant maize hybrids recommended for the region.",
            "Plow under infected crop residues and maintain field sanitation after harvest.",
            "Avoid excessive plant densities and ensure balanced application of nitrogen and potash.",
            "Practice crop rotation with non-cereal crops.",
        ],
        clarifying_observations=[
            "Are the leaf lesions distinctly large, elongated, and cigar-shaped with greyish-tan centers?",
            "Did the blight symptoms start on lower leaves and spread upward through the canopy?",
        ],
        source_id="src_tnau_crop_protection_maize",
    ),
    KnowledgeEntry(
        entry_id="MAIZE-06",
        crop="Maize",
        plant_part="leaf",
        symptom_keywords=[
            "sorghum downy mildew",
            "downy mildew",
            "chlorosis",
            "chlorotic striping",
            "narrow erect leaves",
            "white downy growth",
            "poorly developed cobs",
            "stunting",
            "missing cobs",
            "mildew",
            "yellow",
            "stunt",
            "downy",
            "white",
        ],
        condition_name="Sorghum Downy Mildew",
        scientific_name="Peronosclerospora sorghi",
        category="fungal",
        description=(
            "Symptoms may indicate Sorghum Downy Mildew of maize. Characterized by systemic chlorosis and "
            "yellowish-white striping on young leaves, which become narrow, erect, and leathery. Under cool, humid "
            "morning conditions, a delicate white downy fungal growth appears on the lower leaf surface. Severely "
            "infected plants are stunted and produce poorly developed or absent cobs."
        ),
        safe_cultural_practices=[
            "Rogue out and destroy systemically infected, chlorotic plants within 30 days of sowing to prevent secondary spore spread.",
            "Ensure good field drainage and avoid water stagnation.",
            "Grow downy-mildew-resistant maize cultivars in endemic areas.",
            "Follow crop rotation for at least three years with non-host crops.",
        ],
        clarifying_observations=[
            "Are leaves showing yellow-white stripes with a white downy coating on the underside under high morning humidity?",
            "Are the infected plants stunted with poorly formed or missing cobs?",
        ],
        source_id="src_tnau_crop_protection_maize",
    ),
    KnowledgeEntry(
        entry_id="MAIZE-07",
        crop="Maize",
        plant_part="stem",
        symptom_keywords=[
            "stalk rot",
            "charcoal rot",
            "fusarium stalk rot",
            "water-soaked stalk",
            "brown basal stalk",
            "lodging",
            "internal stalk discoloration",
            "shredded pith",
            "soft stem",
            "stalk",
            "rot",
            "stem",
            "brown",
        ],
        condition_name="Maize Stalk Rot",
        scientific_name="Fusarium verticillioides",
        category="fungal",
        description=(
            "Symptoms are consistent with Stalk Rot of maize. Symptoms typically appear after flowering as "
            "water-soaked, dark brown to blackish lesions on the lower internodes of the stalk. Affected stalks become "
            "soft, spongy, and prone to lodging. Splitting the stalk reveals discolored, shredded internal pith "
            "with pinkish, brownish, or charcoal-black fungal growth."
        ),
        safe_cultural_practices=[
            "Maintain balanced soil fertility, avoiding excessive nitrogen and ensuring adequate potassium.",
            "Avoid post-flowering moisture stress by scheduling irrigation appropriately during grain filling.",
            "Ensure proper plant spacing to prevent crop overcrowding.",
            "Destroy infected crop residues and rotate with non-graminaceous crops.",
        ],
        clarifying_observations=[
            "Are the lower stalk internodes soft, discolored brown, and prone to breaking or lodging?",
            "Does splitting the lower stalk reveal shredded, discolored internal pith?",
        ],
        source_id="src_tnau_crop_protection_maize",
    ),
    # =======================================================================
    # 4. CHICKPEA (6 Entries)
    # =======================================================================
    KnowledgeEntry(
        entry_id="CHICKPEA-01",
        crop="Chickpea",
        plant_part="fruit",
        symptom_keywords=[
            "gram pod borer",
            "pod borer",
            "caterpillar",
            "holes in pods",
            "circular holes",
            "defoliation",
            "flower feeding",
            "green caterpillar",
            "chewed pod",
            "pod",
            "hole",
            "holes",
            "caterpillar",
            "borer",
        ],
        condition_name="Gram Pod Borer",
        scientific_name="Helicoverpa armigera",
        category="pest_damage",
        description=(
            "Symptoms are consistent with Gram Pod Borer infestation. Early instar larvae feed on young leaves, "
            "tender shoots, and flowers. Later instars bore neat circular entry holes into developing green pods "
            "and feed on the seeds inside while keeping the rear part of their body outside the pod."
        ),
        safe_cultural_practices=[
            "Install bird perches (T-shaped wooden perches, 15–20/acre) across the field to encourage predatory insectivorous birds.",
            "Set up pheromone traps (4–5 traps/acre) to monitor adult moth population dynamics.",
            "Intercrop chickpea with coriander, mustard, or linseed to enhance natural enemy diversity.",
            "Hand-pick and destroy visible caterpillars and damaged pods during early morning hours in small holdings.",
        ],
        clarifying_observations=[
            "Do you see neat circular entry holes bored into the developing green pods?",
            "Are there greenish-brown striped caterpillars feeding on flowers, leaves, or pods?",
        ],
        source_id="src_tnau_crop_protection_bengalgram",
    ),
    KnowledgeEntry(
        entry_id="CHICKPEA-02",
        crop="Chickpea",
        plant_part="whole_plant",
        symptom_keywords=[
            "fusarium wilt",
            "chickpea wilt",
            "wilting in patches",
            "drooping petioles",
            "seedling collapse",
            "vascular browning",
            "internal root browning",
            "drying in patches",
            "wilt",
            "wilting",
            "root browning",
            "dry",
        ],
        condition_name="Fusarium Wilt",
        scientific_name="Fusarium oxysporum f. sp. ciceris",
        category="fungal",
        description=(
            "Symptoms are consistent with Fusarium Wilt of chickpea. Can occur at seedling stage (sudden plant "
            "collapse) or flowering/podding stage (gradual drooping of upper petioles and leaflets, dull greenish "
            "discoloration, followed by drying). Wilting typically occurs in patches. Splitting the taproot and lower "
            "stem vertically reveals characteristic dark brown to blackish internal vascular discoloration."
        ),
        safe_cultural_practices=[
            "Grow certified wilt-resistant or tolerant chickpea cultivars.",
            "Follow long crop rotations (3–4 years) with non-host crops such as sorghum, wheat, or mustard.",
            "Avoid early sowing in warm soils; practice timely sowing when soil temperatures cool down.",
            "Deep summer plowing to expose fungal inoculum to solar radiation.",
        ],
        clarifying_observations=[
            "Are plants wilting and dying in localized patches across the field?",
            "Does splitting the main root lengthwise show a dark brown/black line inside the central vascular tissue?",
        ],
        source_id="src_tnau_crop_protection_bengalgram",
    ),
    KnowledgeEntry(
        entry_id="CHICKPEA-03",
        crop="Chickpea",
        plant_part="leaf",
        symptom_keywords=[
            "ascochyta blight",
            "water-soaked lesions",
            "circular brown spots",
            "concentric rings on leaves",
            "stem lesions",
            "girdling",
            "plant drying",
            "pycnidia",
            "blight spots",
            "blight",
            "spot",
            "spots",
            "brown",
            "dry",
        ],
        condition_name="Ascochyta Blight",
        scientific_name="Ascochyta rabiei",
        category="fungal",
        description=(
            "Symptoms may indicate Ascochyta Blight of chickpea. Circular to oval brown spots appear on leaves, "
            "stems, and pods, often with concentric rings and tiny black dots (pycnidia) arranged in circles within lesions. "
            "Stem lesions can girdle the branch, causing the portion above the lesion to break over and die. Under cool, "
            "overcast, rainy conditions, the blight spreads rapidly causing widespread canopy scorching."
        ),
        safe_cultural_practices=[
            "Use certified disease-free seeds from reputable sources.",
            "Destroy and bury crop residues after harvest to reduce primary inoculum.",
            "Intercrop with cereals like wheat or barley to slow canopy disease spread.",
            "Avoid sprinkler irrigation or excessive surface water accumulation during cool cloudy weather.",
        ],
        clarifying_observations=[
            "Do the brown leaf and pod spots have concentric rings containing tiny dark dots (pycnidia)?",
            "Are stems showing elongated dark lesions that cause upper branches to snap or droop?",
        ],
        source_id="src_tnau_crop_protection_bengalgram",
    ),
    KnowledgeEntry(
        entry_id="CHICKPEA-04",
        crop="Chickpea",
        plant_part="root",
        symptom_keywords=[
            "dry root rot",
            "scattered dried plants",
            "flowering stage drying",
            "straw-colored foliage",
            "brittle roots",
            "dark sclerotia",
            "root rot",
            "bark shredding",
            "dry",
            "rot",
            "root",
            "drying",
        ],
        condition_name="Dry Root Rot",
        scientific_name="Rhizoctonia bataticola",
        category="fungal",
        description=(
            "Symptoms are consistent with Dry Root Rot of chickpea. Typically appears during post-flowering "
            "and podding stages under high ambient temperature (above 30°C) and moisture stress. Plants dry up suddenly "
            "with leaves and stems turning straw-colored, with leaves remaining attached to the dried plant. "
            "The taproot becomes dark, dry, and brittle, with the bark shredding easily and tiny black dots (sclerotia) "
            "visible under the bark."
        ),
        safe_cultural_practices=[
            "Avoid severe soil moisture stress during flowering and pod development stages.",
            "Practice timely sowing to ensure pod filling before extreme summer heat.",
            "Ensure deep summer plowing and crop rotation with non-hosts.",
            "Maintain organic soil amendments to enhance soil moisture-holding capacity.",
        ],
        clarifying_observations=[
            "Is the drying occurring scattered across the field during warm, dry weather at flowering/podding?",
            "Are the roots dry and brittle with shredded bark and tiny black specks underneath?",
        ],
        source_id="src_tnau_crop_protection_bengalgram",
    ),
    KnowledgeEntry(
        entry_id="CHICKPEA-05",
        crop="Chickpea",
        plant_part="flower",
        symptom_keywords=[
            "botrytis gray mold",
            "poor pod setting",
            "flower shedding",
            "grey spore masses",
            "water-soaked pod lesions",
            "gray mold",
            "stem lesions",
            "rotting flowers",
            "mold",
            "rot",
            "grey",
            "flower shedding",
        ],
        condition_name="Botrytis Gray Mold",
        scientific_name="Botrytis cinerea",
        category="fungal",
        description=(
            "Symptoms may indicate Botrytis Gray Mold of chickpea. Characterized by poor pod setting and "
            "severe shedding of flowers and foliage. Under cool, humid conditions, affected tender stems, flowers, "
            "and pods exhibit water-soaked lesions covered with dense, fuzzy grey-colored fungal spore masses, causing "
            "affected branches to rot and break."
        ),
        safe_cultural_practices=[
            "Maintain wider row-to-row spacing (45 cm or wider) to improve canopy aeration and reduce microclimatic humidity.",
            "Avoid excessive vegetative growth caused by over-irrigation or high nitrogen.",
            "Ensure field drainage to prevent prolonged leaf wetness.",
            "Plant erect, open-canopy chickpea varieties.",
        ],
        clarifying_observations=[
            "Do you see fuzzy grey mold growth on decaying flowers, stems, or pods during cool, damp weather?",
            "Is there extensive shedding of flowers leading to empty podless branches?",
        ],
        source_id="src_tnau_crop_protection_bengalgram",
    ),
    KnowledgeEntry(
        entry_id="CHICKPEA-06",
        crop="Chickpea",
        plant_part="leaf",
        symptom_keywords=[
            "powdery mildew",
            "white powdery patches",
            "leaf powder",
            "white powder on chickpea",
            "foliar powder",
            "mildew on pods",
            "white dust leaf",
            "powdery",
            "powder",
            "mildew",
            "white",
        ],
        condition_name="Powdery Mildew",
        scientific_name="Leveillula taurica",
        category="fungal",
        description=(
            "Symptoms may indicate Powdery Mildew on chickpea. Small, whitish powdery patches appear initially "
            "on leaves and gradually spread to cover stems, young shoots, and developing pods. Severely infected leaves "
            "turn yellow, curl, and shed prematurely, leading to reduced pod development and seed shriveling."
        ),
        safe_cultural_practices=[
            "Avoid dense crop stands by maintaining appropriate plant spacing.",
            "Scout lower canopy leaves regularly during warm, dry days following humid nights.",
            "Destroy infected plant debris after harvest.",
        ],
        clarifying_observations=[
            "Are there visible white powdery patches on the surface of leaves and stems?",
            "Are the affected leaves turning yellow and shedding prematurely?",
        ],
        source_id="src_tnau_crop_protection_bengalgram",
    ),
    # =======================================================================
    # 5. MUSTARD (6 Entries)
    # =======================================================================
    KnowledgeEntry(
        entry_id="MUSTARD-01",
        crop="Mustard",
        plant_part="leaf",
        symptom_keywords=[
            "mustard aphid",
            "aphid",
            "leaf curling",
            "stunting",
            "sooty mould",
            "wilting",
            "sap sucking",
            "curling shoot",
            "inflorescence aphids",
            "curled leaves",
            "curl",
            "curling",
            "stunt",
            "stunted",
            "honeydew",
            "wilt",
        ],
        condition_name="Mustard Aphid",
        scientific_name="Lipaphis erysimi",
        category="pest_damage",
        description=(
            "Symptoms are consistent with Mustard Aphid infestation. Large colonies of small, greenish to "
            "brownish-yellow aphids cluster on tender shoots, inflorescences, leaves, and developing pods to suck plant sap. "
            "This causes leaf curling, yellowing, severe plant stunting, and failure of pod setting. Aphids excrete honeydew "
            "that fosters black sooty mold growth on foliage."
        ),
        safe_cultural_practices=[
            "Practice early sowing (before mid-October in northern India) to escape peak aphid population build-up in January–February.",
            "Scout fields regularly starting from flowering stage, monitoring top 10 cm of twigs.",
            "Clip and destroy aphid-infested apical twigs in the initial focal patches.",
            "Conserve natural predators such as ladybird beetles, hoverfly larvae, and lacewings.",
        ],
        clarifying_observations=[
            "Do you see dense clusters of small greenish-yellow soft insects on tender shoots and flower clusters?",
            "Is there sticky honeydew or black sooty mold covering the curled leaves?",
        ],
        source_id="src_tnau_crop_protection_mustard",
    ),
    KnowledgeEntry(
        entry_id="MUSTARD-02",
        crop="Mustard",
        plant_part="leaf",
        symptom_keywords=[
            "diamondback moth",
            "caterpillar",
            "whitish scraped patches",
            "holes in leaves",
            "defoliation",
            "pod damage",
            "chewed leaves",
            "windowpane feeding",
            "hole",
            "holes",
            "caterpillar",
            "scraped",
        ],
        condition_name="Diamondback Moth",
        scientific_name="Plutella xylostella",
        category="pest_damage",
        description=(
            "Symptoms may indicate Diamondback Moth damage. Young pale green larvae feed on the lower leaf surface, "
            "leaving the upper epidermis intact and creating transparent, whitish 'window' patches. Older larvae chew "
            "irregular holes right through the leaves, causing severe skeletonization, defoliation, and surface feeding on young siliquae (pods)."
        ),
        safe_cultural_practices=[
            "Plant Indian mustard with trap crops (e.g., paired rows of cabbage/mustard) where recommended.",
            "Install pheromone traps (5 traps/acre) for monitoring adult moth populations.",
            "Conserve natural parasitoid wasps (e.g., Cotesia plutellae) by avoiding unnecessary chemical applications.",
            "Remove and destroy crop residues and cruciferous weed hosts.",
        ],
        clarifying_observations=[
            "Are there whitish scraped transparent patches and irregular holes chewed through the leaves?",
            "Do small green caterpillars wriggle backwards or drop on a silk thread when disturbed?",
        ],
        source_id="src_tnau_crop_protection_mustard",
    ),
    KnowledgeEntry(
        entry_id="MUSTARD-03",
        crop="Mustard",
        plant_part="leaf",
        symptom_keywords=[
            "mustard leaf miner",
            "leaf miner",
            "zig-zag galleries",
            "winding tunnels",
            "white serpentine mines",
            "mined leaf",
            "leaf tunnels",
            "serpentine lines",
            "zig zag tunnels",
            "miner",
            "tunnels",
            "galleries",
            "mine",
        ],
        condition_name="Mustard Leaf Miner",
        scientific_name="Chromatomyia horticola",
        category="pest_damage",
        description=(
            "Symptoms are consistent with Mustard Leaf Miner infestation. The tiny maggot feeds within the "
            "mesophyll between the upper and lower leaf epidermises, creating prominent white, winding, zig-zag "
            "serpentine tunnels or galleries across the leaf blade. Severely mined leaves turn yellow, dry up, and drop prematurely."
        ),
        safe_cultural_practices=[
            "Collect and destroy heavily mined lower leaves in the early stages of infestation in small plots.",
            "Maintain clean cultivation by eliminating wild cruciferous host weeds around field borders.",
            "Conserve larval endoparasitoids that naturally keep leaf miner populations below economic injury thresholds.",
        ],
        clarifying_observations=[
            "Do you see distinct white or pale zig-zag serpentine tunnels winding inside the leaf blade?",
            "Are the lower leaves showing yellowing and drying along the tunnel paths?",
        ],
        source_id="src_tnau_crop_protection_mustard",
    ),
    KnowledgeEntry(
        entry_id="MUSTARD-04",
        crop="Mustard",
        plant_part="leaf",
        symptom_keywords=[
            "white rust",
            "white pustules",
            "creamy pustules under leaf",
            "yellow spots upper leaf",
            "staghead",
            "malformed flowers",
            "swollen inflorescence",
            "white blisters",
            "rust",
            "white",
            "pustule",
            "pustules",
            "staghead",
            "yellow",
        ],
        condition_name="White Rust",
        scientific_name="Albugo candida",
        category="fungal",
        description=(
            "Symptoms are consistent with White Rust of mustard. Prominent white or creamy-yellow raised pustules "
            "(blisters) appear on the lower surface of leaves, with corresponding light yellow patches on the upper surface. "
            "Systemic floral infection causes dramatic hypertrophy and distortion of the inflorescence into a swollen, "
            "sterile, green malformation known as a 'staghead'."
        ),
        safe_cultural_practices=[
            "Use certified seeds of white-rust-resistant mustard cultivars.",
            "Practice timely sowing in October to avoid favorable cool, humid weather during flowering.",
            "Clip and destroy staghead malformed inflorescences as soon as they appear to prevent oospore formation.",
            "Follow crop rotation with non-cruciferous crops and maintain clean field sanitation.",
        ],
        clarifying_observations=[
            "Are there raised white/creamy pustules on the leaf underside with matching yellow spots on top?",
            "Is the flower head malformed, swollen, and sterile (staghead)?",
        ],
        source_id="src_tnau_crop_protection_mustard",
    ),
    KnowledgeEntry(
        entry_id="MUSTARD-05",
        crop="Mustard",
        plant_part="leaf",
        symptom_keywords=[
            "alternaria blight",
            "concentric rings",
            "circular black spots",
            "target spots",
            "pod spots",
            "black spot mustard",
            "leaf blight mustard",
            "target board",
            "black",
            "spot",
            "spots",
            "blight",
        ],
        condition_name="Alternaria Blight",
        scientific_name="Alternaria brassicae",
        category="fungal",
        description=(
            "Symptoms are consistent with Alternaria Blight of mustard. Characteristic symptoms are circular, "
            "light-brown to dark-brown or blackish spots with prominent concentric rings producing a 'target-board' "
            "pattern on leaves. Lesions enlarge and coalesce, causing extensive foliar blight. Sunken black spots also "
            "develop on stems and siliquae (pods), leading to premature pod shattering and seed shriveling."
        ),
        safe_cultural_practices=[
            "Use clean, healthy seeds collected from disease-free crop stands.",
            "Adopt timely sowing (early to mid-October) to escape late-season epidemic blight development.",
            "Destroy infected crop residues and volunteer cruciferous plants after harvest.",
            "Ensure proper spacing and avoid overhead or excessive surface irrigation.",
        ],
        clarifying_observations=[
            "Do the circular dark brown/black leaf spots have clear concentric rings ('target-board' pattern)?",
            "Are there sunken black spots appearing on the developing mustard pods?",
        ],
        source_id="src_tnau_crop_protection_mustard",
    ),
    KnowledgeEntry(
        entry_id="MUSTARD-06",
        crop="Mustard",
        plant_part="leaf",
        symptom_keywords=[
            "downy mildew",
            "angular spots",
            "translucent leaf spots",
            "grey-white growth underneath",
            "swollen flower stems",
            "necrotic patches",
            "mildew mustard",
            "mildew",
            "downy",
            "white",
            "spot",
            "spots",
        ],
        condition_name="Downy Mildew",
        scientific_name="Hyaloperonospora brassicae",
        category="fungal",
        description=(
            "Symptoms may indicate Downy Mildew of mustard. Small, angular, light-green to translucent yellowish "
            "spots develop on the upper leaf surface, later turning necrotic brown. Under cool, humid weather, a white "
            "to greyish-white downy fungal growth appears on the lower leaf surface corresponding to the spots. Infection "
            "on flowering stems causes swelling and distortion, often occurring in complex with white rust."
        ),
        safe_cultural_practices=[
            "Grow downy-mildew-tolerant mustard varieties.",
            "Ensure good field drainage and avoid water stagnation.",
            "Maintain optimal plant density for sunlight penetration and airflow.",
            "Destroy infected crop debris and practice crop rotation.",
        ],
        clarifying_observations=[
            "Is there a white to greyish downy growth on the underside of the yellowed/translucent leaf spots?",
            "Are weather conditions cool and humid with heavy morning dews?",
        ],
        source_id="src_tnau_crop_protection_mustard",
    ),
]
