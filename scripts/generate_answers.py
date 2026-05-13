#!/usr/bin/env python3
"""Generate answer_<id>.json files for every patient.

For each patient in sythetic-patient/patients/*.json:
- Identify the requested test (WES/WGS/CMA/BRCA1/2) and the insurer (BCBS_FEP / UHC / Cigna).
- Select the matching policy in policy-documents/policy_789/ and apply structured
  policy criteria derived directly from the policy PDFs (see policy_criteria below).
- Answer Q0-Q8 from question.json and write QA-results/answer_<id>.json.
"""

import json
import os
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PATIENT_DIR = REPO_ROOT / "sythetic-patient" / "patients"
OUT_DIR = REPO_ROOT / "QA-results"
OUT_DIR.mkdir(exist_ok=True, parents=True)

# md5 hashes from `md5sum` of each policy PDF in policy-documents/policy_789/
POLICY = {
    ("BCBS_FEP", "WES"): {
        "file": "BCBS_FEP_204102 Whole Exome and.pdf",
        "md5": "d5e9701c13de1dca302ad0ce45524039",
    },
    ("BCBS_FEP", "WGS"): {
        "file": "BCBS_FEP_204102 Whole Exome and.pdf",
        "md5": "d5e9701c13de1dca302ad0ce45524039",
    },
    ("BCBS_FEP", "CMA"): {
        "file": "BCBS_FEP_20459 Genetic Testing for Developmental.pdf",
        "md5": "8340e5b0ce4959eccfb2cb295edb47f3",
    },
    ("BCBS_FEP", "BRCA1/2"): {
        "file": "BCBS_FEP_20402 Germline Genetic Testing for.pdf",
        "md5": "c5c2b854957d06467835e88a963d0c82",
    },
    ("UHC", "WES"): {
        "file": "United Healthcare_whole-exome-and-whole-genome-sequencing.pdf",
        "md5": "4fadf6b3ca9d4d08131cb31365e3aa7d",
    },
    ("UHC", "WGS"): {
        "file": "United Healthcare_whole-exome-and-whole-genome-sequencing.pdf",
        "md5": "4fadf6b3ca9d4d08131cb31365e3aa7d",
    },
    ("UHC", "CMA"): {
        "file": "United Healthcare_chromosome-microarray-testing.pdf",
        "md5": "8a7d5f974648c666b635eae9e03277e7",
    },
    ("UHC", "BRCA1/2"): {
        "file": "United Healthcare_genetic-testing-hereditary-cancer.pdf",
        "md5": "c69485372670ce1d12aa8f61d83a06fd",
    },
    ("Cigna", "WES"): {
        "file": "Cigna_MOL.TS_.235.C_Whole_Exome_Sequencing_Cigna_eff01.01.2025_pub09.20.2024.pdf",
        "md5": "ad2eb3a750b767e32ff847032f0e8e03",
    },
    ("Cigna", "WGS"): {
        "file": "Cigna_MOL.TS_.306.C_Whole_Genome_Sequencing_Cigna_eff01.01.2025_pub09.10.2024.pdf",
        "md5": "36bb5264dda1b2027dcdfdd32a714204",
    },
    ("Cigna", "CMA"): {
        "file": "Cigna_MOL.TS_.150A_CMA_for_Developmental_Disorders_and_Prenatal_Diagnosis_eff01.01.2025_pub09.10.2024_1.pdf",
        "md5": "dd74cd39fca15b7b0888b16ce1da2014",
    },
    ("Cigna", "BRCA1/2"): {
        "file": "Cigna_MOL.TS_.238.A_BRCA_Analysis_eff01.01.2025_pub09.10.2024_1.pdf",
        "md5": "626eac4d60df057ea93ece78f8cc3dfc",
    },
}

CPT_MAP = {
    "WES": "81415",
    "WGS": "81425",
    "CMA": "81228",
    "BRCA1/2": "81162",
}


def detect_insurer(info: str) -> str:
    low = info.lower()
    if "bcbs_fep" in low or "federal employee program" in low:
        return "BCBS_FEP"
    if "uhc" in low:
        return "UHC"
    if "cigna" in low:
        return "Cigna"
    if "bcbs" in low or "blue cross blue shield" in low:
        return "BCBS_FEP"
    return "BCBS_FEP"  # default when not stated (single such case)


def detect_test(info: str) -> str:
    if re.search(r"BRCA", info, re.I):
        return "BRCA1/2"
    if re.search(r"\bWES\b|whole exome", info):
        return "WES"
    if re.search(r"\bWGS\b|whole genome", info):
        return "WGS"
    if re.search(r"\bCMA\b|chromosomal microarray|chromosome microarray", info):
        return "CMA"
    return "WES"


# Age extraction: returns age in years (float), or None
AGE_PATTERNS = [
    (re.compile(r"(\d+)\s*-?\s*week-?\s*old", re.I), lambda m: int(m.group(1)) / 52.0),
    (re.compile(r"(\d+)\s*-?\s*month-?\s*old", re.I), lambda m: int(m.group(1)) / 12.0),
    (re.compile(r"(\d+)\s*-?\s*year-?\s*old", re.I), lambda m: float(m.group(1))),
    (re.compile(r"\btwo-year-old\b", re.I), lambda m: 2.0),
    (re.compile(r"\bone-year-old\b", re.I), lambda m: 1.0),
    (re.compile(r"\b(infant|newborn|neonate)\b", re.I), lambda m: 0.5),
    (re.compile(r"\badolescent\b", re.I), lambda m: 15.0),
    (re.compile(r"\bchild\b", re.I), lambda m: 8.0),
    (re.compile(r"\badult\b", re.I), lambda m: 40.0),
]


def extract_age_years(info: str):
    for pat, fn in AGE_PATTERNS:
        m = pat.search(info)
        if m:
            return fn(m)
    return None


# Provider extraction
PROVIDER_PATTERNS = [
    (r"\bmedical geneticist\b", "medical geneticist"),
    (r"\bdevelopmental pediatrician\b", "developmental pediatrician"),
    (r"\bneonatologist\b", "neonatologist"),
    (r"\bneurologist\b", "neurologist"),
    (r"\bneurology\b", "neurologist"),
    (r"\boncologist\b", "oncologist"),
    (r"\boncology\b", "oncologist"),
    (r"\bobstetrician\b", "obstetrician"),
    (r"\bgynecologist\b", "gynecologist"),
    (r"\bcardiologist\b", "cardiologist"),
    (r"\bgeneral practitioner\b", "general practitioner"),
    (r"\bgeneral pediatrician\b", "general pediatrician"),
    (r"\bfamily medicine\b", "family medicine"),
    (r"\bprimary care\b", "primary care"),
    (r"\bnurse practitioner\b", "nurse practitioner"),
    (r"\bgenetic counselor\b", "genetic counselor"),
    (r"\bclinician with expertise in clinical genetics\b", "medical geneticist"),
    (r"\bmaternal-fetal medicine\b", "maternal-fetal medicine"),
]


def extract_provider(info: str):
    """Return the provider who ORDERED the test."""
    low = info.lower()
    # Order priority: explicit "ordered by" phrasing first, then "referred by", then any specialist mention
    order_patterns = [
        r"order(?:ed)?\s+by\s+(?:the\s+|her\s+|his\s+|a\s+|an\s+)?([^.,;]+)",
        r"placed\s+the\s+order",
        r"at\s+the\s+request\s+of\s+(?:her\s+|his\s+|a\s+|an\s+|the\s+)?([^.,;]+)",
        r"referred\s+by\s+(?:the\s+|her\s+|his\s+|a\s+|an\s+|child's\s+)?([^.,;]+)",
        r"requested\s+by\s+(?:the\s+|her\s+|his\s+|a\s+|an\s+)?([^.,;]+)",
        r"being\s+referred\s+by\s+(?:her|his)?\s*([^.,;]+)",
    ]
    found = None
    for op in order_patterns:
        m = re.search(op, info, re.I)
        if m:
            captured = m.group(0).lower()
            for pat, name in PROVIDER_PATTERNS:
                if re.search(pat, captured):
                    return name
    # Fallback: any mention of a specialist
    for pat, name in PROVIDER_PATTERNS:
        if re.search(pat, low):
            return name
    return None


def has_counseling(info: str):
    """Return one of: 'meets' (pre+post documented), 'partial', 'none'."""
    low = info.lower()
    has_pre = bool(
        re.search(
            r"pre[-\s]?test\s+(genetic\s+)?counseling\s+(?:was|has been|is|will be)\s+(complete|completed|conducted|performed)",
            low,
        )
        or re.search(r"pre[-\s]?test\s+counseling\s+(was|has been)\s+complete", low)
        or re.search(r"pre[-\s]?test\s+genetic\s+counseling\s+(?:has\s+been|was)\s+complete", low)
        or re.search(r"completed\s+pre[-\s]?test\s+(genetic\s+)?counseling", low)
        or re.search(r"(?:multiple|several)\s+pre[-\s]?test\s+counseling", low)
        or re.search(r"seen\s+(by|a)\s+(a\s+)?genetic\s+counselor.*pre[-\s]?test", low)
        or re.search(r"genetic\s+counselor\b.*pre[-\s]?test\s+counseling\s+is\s+complete", low)
        or re.search(r"pre[-\s]?test\s+(genetic\s+)?counseling\s+is\s+complete", low)
    )
    has_post = bool(
        re.search(r"post[-\s]?test\s+(counseling|follow[-\s]?up|counselling)", low)
        or re.search(r"plans?\s+for\s+post[-\s]?test", low)
    )
    no_counsel = bool(
        re.search(
            r"no\s+(documentation\s+of\s+)?(prior\s+|pre[-\s]?test\s+)?genetic\s+counseling",
            low,
        )
        or re.search(r"no\s+pre[-\s]?test\s+genetic\s+counseling", low)
        or re.search(r"pre[-\s]?test\s+genetic\s+counseling\s+was\s+not\s+(completed|conducted)", low)
        or re.search(r"pre[-\s]?test\s+counseling\s+was\s+not\s+complete", low)
    )
    if no_counsel:
        return "none"
    if has_pre and has_post:
        return "meets"
    if has_pre or has_post:
        return "partial"
    return "none"


def prior_tests(info: str):
    """Return dict of which prior tests the patient has documented as performed."""
    low = info.lower()
    out = {
        "cma": bool(re.search(r"chromosomal microarray|chromosome microarray|\bcma\b", low))
        and "prior" in low
        or bool(re.search(r"prior\s+(chromosomal microarray|chromosome microarray|cma)", low)),
        "fish": bool(re.search(r"prior.*\bfish\b|fluorescence in situ hybridization", low)),
        "karyotype": bool(re.search(r"prior\s+karyotype|karyotype\s+testing\s+was", low)),
        "fragile_x": bool(re.search(r"fragile\s+x", low)),
        "none": bool(
            re.search(r"no\s+prior\s+genetic\s+testing", low)
            or re.search(r"there\s+is\s+no\s+prior\s+genetic\s+testing", low)
            or re.search(r"no\s+prior\s+(genetic\s+testing|testing)\s+(has\s+been|on\s+record)", low)
        ),
    }
    # If the requested test is CMA itself, "prior cma" only counts if explicitly stated as PRIOR
    out["cma_done"] = bool(
        re.search(
            r"prior\s+chromosomal microarray.*nondiagnostic|chromosomal microarray.*previously.*nondiagnostic|chromosomal microarray\s*\(?cma\)?\s*testing\s+was\s+nondiagnostic|prior\s+(chromosomal microarray|cma).*nondiag",
            low,
        )
        or bool(re.search(r"\bcma\b\s+testing\s+was\s+previously\s+performed", low))
        or bool(re.search(r"\bcma\b\s+(was|has been)\s+previously\s+performed", low))
        or bool(re.search(r"prior\s+cma", low))
        or bool(re.search(r"chromosomal microarray\s+\(?cma\)?\s+testing\s+was\s+previously\s+performed", low))
    )
    out["any_prior"] = any([out["fish"], out["karyotype"], out["fragile_x"], out["cma_done"]])
    return out


def has_family_history(info: str):
    """Family history of any condition or consanguinity."""
    low = info.lower()
    return bool(
        re.search(r"family\s+history", low)
        or re.search(r"consanguineou", low)
        or re.search(r"consanguinity", low)
        or re.search(r"maternal\s+(aunt|uncle|grandmother)", low)
        or re.search(r"paternal\s+(aunt|uncle|grandfather)", low)
        or re.search(r"sibling", low)
        or re.search(r"\bmother\b.*(cancer|disorder)", low)
        or re.search(r"\bfather\b.*(cancer|disorder)", low)
        or re.search(r"\bbrother\b.*(cancer|died)", low)
        or re.search(r"\bsister\b.*(cancer|disorder)", low)
    )


# ============================================================================
# Per-policy answer functions
# ============================================================================


def explanation(text: str) -> str:
    return text.strip()


def answer_bcbs_fep_wes(info, age_y, provider, prior, fam_hx, counsel, test):
    """BCBS_FEP policy 2.04.102 - WES (or WGS).

    Standard WES criteria require: clinician with expertise in clinical genetics,
    counseling, and prior genetic testing (e.g., CMA) failed to yield a diagnosis,
    OR previous testing failed and invasive procedures pending.
    WGS is investigational outside of rapid sequencing for critically ill infants.
    """
    a = {}

    # Q1 age - policy doesn't impose strict numeric age cutoff for standard WES
    a["Q1"] = "Not Specified"
    a["Q1_explanation"] = "BCBS FEP 2.04.102 sets no explicit numeric patient-age cutoff for standard WES/WGS; rapid sequencing is restricted to critically ill infants in NICU/PICU."

    # Q2 provider - "clinician with expertise in clinical genetics"
    genetic_providers = {"medical geneticist", "developmental pediatrician", "neonatologist", "neurologist"}
    if provider in genetic_providers or provider == "genetic counselor":
        a["Q2"] = "Yes"
        a["Q2_explanation"] = f"Policy requires evaluation by a clinician with expertise in clinical genetics; ordered by {provider}."
    elif provider in {"general practitioner", "general pediatrician", "family medicine", "primary care", "obstetrician", "gynecologist", "cardiologist", "oncologist", "nurse practitioner"}:
        a["Q2"] = "No"
        a["Q2_explanation"] = f"Policy requires a clinician with expertise in clinical genetics; ordered by {provider}, which does not meet that requirement."
    else:
        a["Q2"] = "Not Answerable"
        a["Q2_explanation"] = "Ordering provider type cannot be determined from the patient information."

    # Q3 medical indication - unexplained congenital or neurodevelopmental disorders in children
    low = info.lower()
    indication_match = any(
        re.search(p, low)
        for p in [
            r"developmental delay",
            r"intellectual disability",
            r"congenital anomal",
            r"hypotonia",
            r"epileptic encephalopathy",
            r"epilepsy",
            r"autism",
            r"hearing|visual impairment",
            r"meconium ileus",
            r"choanal atresia",
            r"hirschsprung",
            r"coloboma",
            r"dysmorphic",
            r"hypertonia",
            r"neurodevelopmental",
            r"brue|brief resolved unexplained event",
            r"developmental regression",
            r"growth abnormality|failure to thrive|short stature|microcephaly|macrocephaly",
            r"immunologic or hematologic disorder",
            r"inborn error of metabolism",
            r"global developmental delay",
        ]
    )
    if indication_match:
        a["Q3"] = "Yes"
        a["Q3_explanation"] = "Patient presents with an unexplained congenital or neurodevelopmental indication that the policy lists as a covered phenotype."
    else:
        a["Q3"] = "No"
        a["Q3_explanation"] = "Patient does not present with a congenital or neurodevelopmental indication enumerated in policy 2.04.102."

    # Q4 prior tests - policy requires previous testing (CMA or targeted single-gene) failed to yield diagnosis
    if prior.get("cma_done"):
        a["Q4"] = "Yes"
        a["Q4_explanation"] = "Policy requires prior genetic testing (e.g., CMA) that was nondiagnostic; patient had prior CMA that was nondiagnostic."
    elif prior.get("any_prior"):
        a["Q4"] = "No"
        a["Q4_explanation"] = "Policy requires prior genetic testing such as CMA or targeted single-gene testing; patient had non-CMA prior testing (e.g., FISH/karyotype), which does not satisfy the policy requirement."
    else:
        a["Q4"] = "No"
        a["Q4_explanation"] = "Policy requires prior genetic testing (e.g., CMA) before WES; no qualifying prior testing is documented for this patient."

    # Q5 family history - specified (family history of inborn errors, BRUE features, etc. listed in policy)
    if fam_hx:
        a["Q5"] = "Yes"
        a["Q5_explanation"] = "Policy lists family history features (e.g., inborn error of metabolism, developmental delay) supporting WES; patient has a relevant family history."
    else:
        a["Q5"] = "No"
        a["Q5_explanation"] = "Policy describes family history features supporting WES eligibility; patient has no relevant family history documented."

    # Q6 counseling
    if counsel == "meets":
        a["Q6"] = "Yes"
        a["Q6_explanation"] = "Policy requires counseling about potential risks of genetic testing; documented pre-test counseling with plans for post-test follow-up."
    elif counsel == "partial":
        a["Q6"] = "Yes"
        a["Q6_explanation"] = "Policy requires counseling about potential risks of genetic testing; counseling has been at least partially completed."
    else:
        a["Q6"] = "No"
        a["Q6_explanation"] = "Policy requires counseling about potential risks of genetic testing; no genetic counseling is documented for this patient."

    # Q7 CPT
    a["Q7"] = CPT_MAP[test]
    a["Q7_explanation"] = f"CPT {a['Q7']} corresponds to {test} sequencing of the proband."

    return a


def answer_bcbs_fep_cma(info, age_y, provider, prior, fam_hx, counsel, test):
    """BCBS_FEP policy 2.04.59 - CMA for DD/ID/ASD/congenital anomalies."""
    a = {}
    a["Q1"] = "Not Specified"
    a["Q1_explanation"] = "BCBS FEP 2.04.59 does not specify a patient-age cutoff; CMA is first-line postnatal testing."

    a["Q2"] = "Not Specified"
    a["Q2_explanation"] = "Policy 2.04.59 does not specify required ordering-provider specialty."

    low = info.lower()
    if any(
        re.search(p, low)
        for p in [
            r"developmental delay",
            r"intellectual disability",
            r"autism",
            r"multiple congenital anomal",
            r"congenital anomal",
        ]
    ):
        a["Q3"] = "Yes"
        a["Q3_explanation"] = "Policy covers CMA as first-line testing for nonsyndromic developmental delay/ID, ASD, or multiple congenital anomalies; patient has a qualifying indication."
    else:
        a["Q3"] = "No"
        a["Q3_explanation"] = "Patient's indication is not among the conditions (DD/ID, ASD, multiple congenital anomalies) for which CMA is considered medically necessary."

    a["Q4"] = "Not Specified"
    a["Q4_explanation"] = "CMA is intended as first-line testing; the policy does not require completion of prior tests."

    a["Q5"] = "Not Specified"
    a["Q5_explanation"] = "Policy 2.04.59 does not list family history as an eligibility criterion."

    a["Q6"] = "Not Specified"
    a["Q6_explanation"] = "Policy 2.04.59 does not require specific genetic counseling as a coverage criterion."

    a["Q7"] = CPT_MAP[test]
    a["Q7_explanation"] = f"CPT {a['Q7']} corresponds to cytogenomic constitutional microarray analysis (CMA)."
    return a


def answer_bcbs_fep_brca(info, age_y, provider, prior, fam_hx, counsel, test):
    """BCBS_FEP policy 2.04.02 - germline BRCA1/2/PALB2 testing."""
    a = {}
    if age_y is not None:
        if age_y >= 18:
            a["Q1"] = "Yes"
            a["Q1_explanation"] = "Policy considers BRCA testing in minors investigational (age ≥18 required); patient is an adult."
        else:
            a["Q1"] = "No"
            a["Q1_explanation"] = "Policy considers BRCA testing in minors investigational; patient is under 18."
    else:
        a["Q1"] = "Not Answerable"
        a["Q1_explanation"] = "Patient age cannot be determined."

    a["Q2"] = "Yes"
    a["Q2_explanation"] = "Policy requires testing in a setting with suitably trained providers offering pre- and post-test counseling; provider type is not further restricted."

    low = info.lower()
    # Personal cancer history
    has_breast = bool(re.search(r"breast cancer|breast carcinoma|malignant phyllodes|primary breast", low))
    has_ovarian = bool(re.search(r"ovarian carcinoma|ovarian cancer|fallopian tube|peritoneal cancer", low))
    has_pancreatic = bool(re.search(r"pancreatic cancer", low))
    has_prostate = bool(re.search(r"prostate cancer", low))
    personal_cancer = has_breast or has_ovarian or has_pancreatic or has_prostate
    # Relevant family history (cancers)
    cancer_fhx = bool(
        re.search(
            r"family history.*(breast|ovarian|pancreatic|prostate|cancer)|"
            r"(mother|father|sister|brother|aunt|uncle).*(breast|ovarian|pancreatic|prostate) cancer|"
            r"(maternal|paternal).*(breast|ovarian|pancreatic|prostate) cancer|"
            r"close blood relative.*(breast|ovarian|pancreatic|prostate)|"
            r"brca[12]?\s+(pathogenic|variant)|known brca",
            low,
        )
    )
    if personal_cancer or cancer_fhx:
        a["Q3"] = "Yes"
        a["Q3_explanation"] = "Patient meets a covered indication (personal or relevant family cancer history) under policy 2.04.02."
    else:
        a["Q3"] = "No"
        a["Q3_explanation"] = "Patient lacks a personal cancer history or qualifying family cancer history per policy 2.04.02."

    a["Q4"] = "Not Specified"
    a["Q4_explanation"] = "Policy 2.04.02 does not require prior genetic testing before BRCA1/2/PALB2 testing."

    if cancer_fhx:
        a["Q5"] = "Yes"
        a["Q5_explanation"] = "Policy lists family history of breast/ovarian/pancreatic/prostate cancer or BRCA variants as eligibility criteria; patient has such a family history."
    else:
        a["Q5"] = "No"
        a["Q5_explanation"] = "Policy lists family history of relevant cancers as eligibility criteria; patient does not have such a family history."

    if counsel == "meets" or counsel == "partial":
        a["Q6"] = "Yes"
        a["Q6_explanation"] = "Policy requires pre- and post-test genetic counseling; patient has documented counseling."
    else:
        a["Q6"] = "No"
        a["Q6_explanation"] = "Policy requires pre- and post-test genetic counseling; patient lacks documented genetic counseling."

    a["Q7"] = CPT_MAP[test]
    a["Q7_explanation"] = f"CPT {a['Q7']} corresponds to BRCA1 and BRCA2 full sequence + del/dup analysis."
    return a


def answer_uhc_wes(info, age_y, provider, prior, fam_hx, counsel, test):
    """UHC Whole Exome/Whole Genome Sequencing policy."""
    a = {}
    a["Q1"] = "Not Specified"
    a["Q1_explanation"] = "UHC policy does not set a strict patient-age cutoff for WES/WGS; age qualifiers apply to specific feature criteria (e.g., ID diagnosed by 18 yrs)."

    allowed = {"medical geneticist", "neonatologist", "neurologist", "developmental pediatrician"}
    if provider in allowed:
        a["Q2"] = "Yes"
        a["Q2_explanation"] = f"Policy requires WES/WGS to be ordered by a medical geneticist, neonatologist, neurologist, or developmental pediatrician; ordered by {provider}."
    elif provider is None:
        a["Q2"] = "Not Answerable"
        a["Q2_explanation"] = "Ordering provider cannot be determined."
    else:
        a["Q2"] = "No"
        a["Q2_explanation"] = f"Policy restricts ordering to medical geneticist, neonatologist, neurologist, or developmental pediatrician; ordered by {provider}."

    low = info.lower()
    # Category A: any one of (multiple congenital anomalies, mod-severe-profound ID, GDD, epileptic enceph)
    cat_a_terms = [
        (r"multiple congenital anomal", "multiple congenital anomalies"),
        (r"(moderate|severe|profound)\s*(to\s*(moderate|severe|profound))?\s*intellectual disability", "moderate-severe-profound ID"),
        (r"global developmental delay", "global developmental delay"),
        (r"epileptic encephalopathy", "epileptic encephalopathy"),
    ]
    cat_a = any(re.search(p, low) for p, _ in cat_a_terms)
    # Category B: need 2 of these features
    cat_b_terms = [
        (r"congenital (anomaly|cardiac anomaly|choanal|coloboma|hirschsprung|meconium)", "congenital anomaly"),
        (r"(hearing|visual) impairment", "hearing/visual impairment"),
        (r"inborn error of metabolism", "IEM lab abnormalities"),
        (r"autism", "autism"),
        (r"bipolar|schizophrenia|obsessive[-\s]?compulsive|neuropsychiatric", "neuropsychiatric"),
        (r"hypotonia|hypertonia", "hypotonia/hypertonia"),
        (r"dystonia|ataxia|hemiplegia|neuromuscular|movement disorder", "neurologic disorder"),
        (r"developmental regression", "developmental regression"),
        (r"growth abnormal|failure to thrive|short stature|microcephaly|macrocephaly|overgrowth", "growth abnormality"),
        (r"immunologic|hematologic disorder", "immunologic/hematologic disorder"),
        (r"dysmorphic", "dysmorphic features"),
        (r"consanguin", "consanguinity"),
        (r"(sibling|brother|sister|first[- ]degree|second[- ]degree).*(similar|same|developmental delay|disorder)|family member.*similar", "family history of similar features"),
    ]
    cat_b_hits = sum(1 for p, _ in cat_b_terms if re.search(p, low))
    if cat_a or cat_b_hits >= 2:
        a["Q3"] = "Yes"
        a["Q3_explanation"] = "Patient meets the UHC clinical feature criteria for WES/WGS (one Category A or ≥2 Category B features)."
    else:
        a["Q3"] = "No"
        a["Q3_explanation"] = "Patient does not satisfy the UHC clinical feature criteria (no Category A feature and <2 Category B features)."

    # Q4 prior tests
    # WES policy: if a specific genetic syndrome is suspected, single gene or targeted gene panel should be performed prior.
    # WGS policy: Neither CMA nor WES previously performed.
    if test == "WGS":
        # Q4 for WGS: Neither CMA nor WES performed (a "negative" requirement). If CMA was done, fails this criterion.
        if prior.get("cma_done"):
            a["Q4"] = "No"
            a["Q4_explanation"] = "WGS criterion requires that neither CMA nor WES has been performed; patient has had CMA, which is not consistent with this criterion."
        else:
            a["Q4"] = "Yes"
            a["Q4_explanation"] = "WGS criterion requires that neither CMA nor WES has been performed; patient has not had CMA or WES."
    else:
        # WES: conditional. Most patients here have nonspecific presentations so prior is not absolutely required.
        a["Q4"] = "Not Specified"
        a["Q4_explanation"] = "UHC policy only requires prior single-gene or targeted panel testing IF a specific syndrome is suspected; the policy does not impose an absolute prior-testing requirement otherwise."

    if fam_hx:
        a["Q5"] = "Yes"
        a["Q5_explanation"] = "Family history of similar features or consanguinity is one of the policy's clinical feature criteria; patient has a relevant family history."
    else:
        a["Q5"] = "No"
        a["Q5_explanation"] = "Family history or consanguinity is one of the policy's clinical feature criteria; patient has none documented."

    if counsel in ("meets", "partial"):
        a["Q6"] = "Yes"
        a["Q6_explanation"] = "Policy strongly recommends pre-test genetic counseling; patient has documented counseling."
    else:
        a["Q6"] = "No"
        a["Q6_explanation"] = "Policy strongly recommends pre-test genetic counseling; no counseling is documented."

    a["Q7"] = CPT_MAP[test]
    a["Q7_explanation"] = f"CPT {a['Q7']} corresponds to {test} sequencing of the proband."
    return a


def answer_uhc_cma(info, age_y, provider, prior, fam_hx, counsel, test):
    a = {}
    a["Q1"] = "Not Specified"
    a["Q1_explanation"] = "UHC CMA policy does not specify a strict patient-age cutoff."

    a["Q2"] = "Not Specified"
    a["Q2_explanation"] = "UHC CMA policy does not specify a required ordering-provider specialty."

    low = info.lower()
    if any(
        re.search(p, low)
        for p in [
            r"autism",
            r"isolated severe congenital heart|congenital heart",
            r"multiple anomal|congenital anomal",
            r"developmental delay|intellectual disability",
        ]
    ):
        a["Q3"] = "Yes"
        a["Q3_explanation"] = "Patient meets a covered indication (ASD, severe congenital heart disease, multiple anomalies, or DD/ID without a suspected specific syndrome)."
    else:
        a["Q3"] = "No"
        a["Q3_explanation"] = "Patient's indication is not among ASD, congenital heart disease, multiple anomalies, or DD/ID."

    a["Q4"] = "Not Specified"
    a["Q4_explanation"] = "UHC CMA policy does not require prior testing."

    a["Q5"] = "Not Specified"
    a["Q5_explanation"] = "UHC CMA policy does not list family history as an eligibility criterion."

    if counsel in ("meets", "partial"):
        a["Q6"] = "Yes"
        a["Q6_explanation"] = "Policy strongly recommends pre-test genetic counseling; patient has documented counseling."
    else:
        a["Q6"] = "No"
        a["Q6_explanation"] = "Policy strongly recommends pre-test genetic counseling; none documented."

    a["Q7"] = CPT_MAP[test]
    a["Q7_explanation"] = f"CPT {a['Q7']} corresponds to constitutional cytogenomic microarray analysis."
    return a


def answer_uhc_brca(info, age_y, provider, prior, fam_hx, counsel, test):
    a = {}
    a["Q1"] = "Not Specified"
    a["Q1_explanation"] = "UHC hereditary cancer policy ties age criteria to diagnosis context (e.g., breast cancer diagnosed ≤50 or ≤65); it does not set a strict patient-age cutoff."

    a["Q2"] = "Not Specified"
    a["Q2_explanation"] = "UHC policy does not specify a required ordering-provider specialty."

    low = info.lower()
    has_breast = bool(re.search(r"breast cancer|malignant phyllodes", low))
    has_ovarian = bool(re.search(r"ovarian (cancer|carcinoma)|fallopian tube|peritoneal cancer", low))
    has_pancreatic = bool(re.search(r"pancreatic cancer", low))
    has_prostate = bool(re.search(r"prostate cancer", low))
    personal_solid_tumor = has_breast or has_ovarian or has_pancreatic or has_prostate or bool(
        re.search(r"primary solid tumor|primary tumor", low)
    )
    # Family history of relevant cancers
    fhx_cancer = bool(
        re.search(
            r"family history.*(breast|ovarian|pancreatic|prostate|cancer)|"
            r"(mother|father|sister|brother|maternal|paternal|sibling).*(breast|ovarian|pancreatic|prostate) cancer|"
            r"close blood relative.*(breast|ovarian|pancreatic|prostate)|"
            r"brca[12]?\s+(pathogenic|variant)",
            low,
        )
    )
    if personal_solid_tumor or fhx_cancer:
        a["Q3"] = "Yes"
        a["Q3_explanation"] = "Patient has a personal or qualifying family history of breast/ovarian/pancreatic/prostate cancer that the policy covers."
    else:
        a["Q3"] = "No"
        a["Q3_explanation"] = "Patient lacks a personal solid tumor history or qualifying family cancer history under the UHC hereditary cancer policy."

    a["Q4"] = "Not Specified"
    a["Q4_explanation"] = "UHC hereditary cancer policy does not require prior genetic testing."

    if fhx_cancer:
        a["Q5"] = "Yes"
        a["Q5_explanation"] = "Family history of relevant cancers is an eligibility pathway; patient has such a family history."
    else:
        a["Q5"] = "No"
        a["Q5_explanation"] = "Family history of relevant cancers is an eligibility pathway; patient does not have such a family history."

    if counsel in ("meets", "partial"):
        a["Q6"] = "Yes"
        a["Q6_explanation"] = "Pre-test counseling is strongly recommended; patient has documented counseling."
    else:
        a["Q6"] = "No"
        a["Q6_explanation"] = "Pre-test counseling is strongly recommended; none documented."

    a["Q7"] = CPT_MAP[test]
    a["Q7_explanation"] = f"CPT {a['Q7']} corresponds to BRCA1 and BRCA2 full sequence and deletion/duplication analysis (combined)."
    return a


def answer_cigna_wes(info, age_y, provider, prior, fam_hx, counsel, test):
    a = {}
    if age_y is not None:
        if age_y < 21:
            a["Q1"] = "Yes"
            a["Q1_explanation"] = "Cigna exome policy restricts coverage to members <21 years; patient meets that age criterion."
        else:
            a["Q1"] = "No"
            a["Q1_explanation"] = "Cigna exome policy restricts coverage to members <21 years; patient is ≥21."
    else:
        a["Q1"] = "Not Answerable"
        a["Q1_explanation"] = "Patient age cannot be determined."

    a["Q2"] = "Not Specified"
    a["Q2_explanation"] = "Cigna exome policy does not specify a required ordering-provider specialty."

    low = info.lower()
    cat_a = any(
        re.search(p, low)
        for p in [
            r"global developmental delay",
            r"(moderate|severe|profound)\s*(to\s*(moderate|severe|profound))?\s*intellectual disability",
            r"multiple congenital",
            r"epileptic encephalopathy",
        ]
    )
    cat_b_hits = sum(
        1
        for p in [
            r"major abnormality affecting at minimum a single organ system|major congenital cardiac anomaly|congenital cardiac anomaly|major.*organ",
            r"autism",
            r"complex neurodevelopmental|self-injurious|reverse sleep|dystonia|ataxia|hemiplegia|neuromuscular",
            r"schizophrenia|bipolar|tourette|neuropsychiatric",
            r"developmental regression",
            r"inborn error of metabolism",
        ]
        if re.search(p, low)
    )
    if cat_a or cat_b_hits >= 2:
        a["Q3"] = "Yes"
        a["Q3_explanation"] = "Patient meets the Cigna clinical-feature criteria for exome sequencing."
    else:
        a["Q3"] = "No"
        a["Q3_explanation"] = "Patient does not satisfy the Cigna clinical-feature criteria for exome sequencing."

    a["Q4"] = "Not Specified"
    a["Q4_explanation"] = "Cigna exome policy specifies absence of prior exome or genome sequencing as a criterion, not completion of specific prior tests."

    if fam_hx:
        a["Q5"] = "Yes"
        a["Q5_explanation"] = "Policy requires appropriate genetic and family history evaluation; consanguinity is also listed; patient has relevant family history."
    else:
        a["Q5"] = "No"
        a["Q5_explanation"] = "Policy expects appropriate family history evaluation; patient has no relevant family history documented."

    if counsel in ("meets", "partial"):
        a["Q6"] = "Yes"
        a["Q6_explanation"] = "Policy requires appropriate genetic and family history evaluation (counseling); patient has documented counseling."
    else:
        a["Q6"] = "No"
        a["Q6_explanation"] = "Policy requires appropriate genetic counseling/evaluation; none documented."

    a["Q7"] = CPT_MAP[test]
    a["Q7_explanation"] = f"CPT {a['Q7']} corresponds to exome sequencing of the proband."
    return a


def answer_cigna_wgs(info, age_y, provider, prior, fam_hx, counsel, test):
    a = answer_cigna_wes(info, age_y, provider, prior, fam_hx, counsel, test)
    a["Q1_explanation"] = (
        "Cigna genome policy restricts standard genome sequencing coverage to members <21 years."
        + (" Patient meets that criterion." if age_y is not None and age_y < 21 else " Patient is ≥21." if age_y is not None else "")
    )
    a["Q7"] = CPT_MAP[test]
    a["Q7_explanation"] = f"CPT {a['Q7']} corresponds to genome sequencing of the proband."
    return a


def answer_cigna_cma(info, age_y, provider, prior, fam_hx, counsel, test):
    a = {}
    a["Q1"] = "Not Specified"
    a["Q1_explanation"] = "Cigna CMA policy does not specify a patient-age cutoff (postnatal CMA is first-tier)."

    a["Q2"] = "Not Specified"
    a["Q2_explanation"] = "Cigna CMA policy does not specify a required ordering-provider specialty."

    low = info.lower()
    if any(
        re.search(p, low)
        for p in [
            r"developmental delay|intellectual disability",
            r"autism",
            r"major congenital cardiac|congenital cardiac",
            r"multiple congenital",
        ]
    ):
        a["Q3"] = "Yes"
        a["Q3_explanation"] = "Patient meets a covered indication (DD/ID, ASD, major congenital cardiac anomaly, or multiple congenital anomalies)."
    else:
        a["Q3"] = "No"
        a["Q3_explanation"] = "Patient's indication is not among DD/ID, ASD, cardiac anomaly, or multiple congenital anomalies."

    a["Q4"] = "Not Specified"
    a["Q4_explanation"] = "Cigna CMA policy specifies no prior CMA testing as a criterion, not completion of prior tests."

    a["Q5"] = "Not Specified"
    a["Q5_explanation"] = "Cigna CMA policy does not list family history as an eligibility criterion."

    if counsel in ("meets", "partial"):
        a["Q6"] = "Yes"
        a["Q6_explanation"] = "Policy requires pre- and post-test genetic counseling; patient has documented counseling."
    else:
        a["Q6"] = "No"
        a["Q6_explanation"] = "Policy requires pre- and post-test genetic counseling; none documented."

    a["Q7"] = CPT_MAP[test]
    a["Q7_explanation"] = f"CPT {a['Q7']} corresponds to constitutional cytogenomic microarray analysis."
    return a


def answer_cigna_brca(info, age_y, provider, prior, fam_hx, counsel, test):
    a = {}
    if age_y is not None:
        if age_y >= 18:
            a["Q1"] = "Yes"
            a["Q1_explanation"] = "Cigna BRCA policy requires age ≥18; patient is an adult."
        else:
            a["Q1"] = "No"
            a["Q1_explanation"] = "Cigna BRCA policy requires age ≥18; patient is under 18."
    else:
        a["Q1"] = "Not Answerable"
        a["Q1_explanation"] = "Patient age cannot be determined."

    a["Q2"] = "Not Specified"
    a["Q2_explanation"] = "Cigna BRCA policy does not specify an ordering-provider specialty (only that counseling be by an appropriate provider)."

    low = info.lower()
    has_personal = bool(re.search(r"breast cancer|ovarian (cancer|carcinoma)|fallopian tube|peritoneal cancer|pancreatic cancer|prostate cancer", low))
    fhx_cancer = bool(re.search(r"family history.*(breast|ovarian|pancreatic|prostate)|(mother|father|sister|brother|aunt|uncle).*(breast|ovarian|pancreatic|prostate) cancer|known brca|brca[12]?\s+(pathogenic|variant)", low))
    if has_personal or fhx_cancer:
        a["Q3"] = "Yes"
        a["Q3_explanation"] = "Patient meets a Cigna BRCA covered indication (personal or qualifying family cancer history)."
    else:
        a["Q3"] = "No"
        a["Q3_explanation"] = "Patient lacks a covered indication under the Cigna BRCA policy."

    a["Q4"] = "Not Specified"
    a["Q4_explanation"] = "Cigna BRCA policy specifies no prior BRCA full sequencing; it does not require completion of other prior tests."

    if fhx_cancer:
        a["Q5"] = "Yes"
        a["Q5_explanation"] = "Family history of relevant cancers is one of the eligibility pathways; patient has such a family history."
    else:
        a["Q5"] = "No"
        a["Q5_explanation"] = "Family history of relevant cancers is one of the eligibility pathways; patient does not have such a family history."

    if counsel in ("meets", "partial"):
        a["Q6"] = "Yes"
        a["Q6_explanation"] = "Policy requires pre- and post-test genetic counseling; patient has documented counseling."
    else:
        a["Q6"] = "No"
        a["Q6_explanation"] = "Policy requires pre- and post-test genetic counseling; none documented."

    a["Q7"] = CPT_MAP[test]
    a["Q7_explanation"] = f"CPT {a['Q7']} corresponds to BRCA1 and BRCA2 full sequence and del/dup analysis (combined)."
    return a


ANSWERERS = {
    ("BCBS_FEP", "WES"): answer_bcbs_fep_wes,
    ("BCBS_FEP", "WGS"): answer_bcbs_fep_wes,
    ("BCBS_FEP", "CMA"): answer_bcbs_fep_cma,
    ("BCBS_FEP", "BRCA1/2"): answer_bcbs_fep_brca,
    ("UHC", "WES"): answer_uhc_wes,
    ("UHC", "WGS"): answer_uhc_wes,
    ("UHC", "CMA"): answer_uhc_cma,
    ("UHC", "BRCA1/2"): answer_uhc_brca,
    ("Cigna", "WES"): answer_cigna_wes,
    ("Cigna", "WGS"): answer_cigna_wgs,
    ("Cigna", "CMA"): answer_cigna_cma,
    ("Cigna", "BRCA1/2"): answer_cigna_brca,
}


def overall_coverage(a: dict, test: str, insurer: str) -> str:
    """Determine Q8 - is the test covered?

    A test is covered only if all binding criteria are met. Specifically:
    - If any Q with a "No" answer represents a binding criterion violation, coverage is No.
    - "Not Specified" or "Yes" answers are OK.
    """
    binding_no = False
    for q in ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6"]:
        if a[q] == "No":
            binding_no = True
            break
    return "No" if binding_no else "Yes"


def main():
    patients = sorted(PATIENT_DIR.glob("Case*.json"))
    print(f"Processing {len(patients)} patients")
    for pf in patients:
        with open(pf) as f:
            data = json.load(f)
        cid = data["id"]
        info = data["patient_info"]
        insurer = detect_insurer(info)
        test = detect_test(info)
        policy = POLICY[(insurer, test)]
        age = extract_age_years(info)
        provider = extract_provider(info)
        prior = prior_tests(info)
        fam_hx = has_family_history(info)
        counsel = has_counseling(info)
        answerer = ANSWERERS[(insurer, test)]
        ans = answerer(info, age, provider, prior, fam_hx, counsel, test)

        result = {
            cid: {
                "Q0": test,
                "Q0_explanation": f"Patient information explicitly references {test} as the requested test.",
                "Q1": ans["Q1"],
                "Q1_explanation": ans["Q1_explanation"],
                "Q2": ans["Q2"],
                "Q2_explanation": ans["Q2_explanation"],
                "Q3": ans["Q3"],
                "Q3_explanation": ans["Q3_explanation"],
                "Q4": ans["Q4"],
                "Q4_explanation": ans["Q4_explanation"],
                "Q5": ans["Q5"],
                "Q5_explanation": ans["Q5_explanation"],
                "Q6": ans["Q6"],
                "Q6_explanation": ans["Q6_explanation"],
                "Q7": ans["Q7"],
                "Q7_explanation": ans["Q7_explanation"],
                "Q8": overall_coverage(ans, test, insurer),
                "Q8_explanation": "All applicable policy criteria are satisfied." if overall_coverage(ans, test, insurer) == "Yes"
                else "At least one binding policy criterion is not satisfied (see Q1-Q6).",
                "identified_md5": policy["md5"],
            }
        }

        out = OUT_DIR / f"answer_{cid}.json"
        with open(out, "w") as f:
            json.dump(result, f, indent=2)
    print(f"Wrote {len(patients)} answer files to {OUT_DIR}")


if __name__ == "__main__":
    main()
