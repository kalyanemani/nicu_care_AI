"""
Clinical Query Normalizer & Text Sanitizer:
Normalizes user queries for spelling mistakes, grammatical errors, and colloquial synonyms
while strictly preserving clinical context, negations, antonyms, numerical quantities, and intent.
"""

import re
import difflib
from typing import Dict, Any, List, Tuple, Set, Optional


class ClinicalQueryNormalizer:
    """
    Normalizes maternal queries by fixing typos, standardizing synonyms,
    and repairing broken grammar without mutating clinical meaning or inverting negations.
    """

    # Strict Negation & Polarity Tokens (MUST BE PRESERVED AT ALL COSTS)
    NEGATION_TOKENS = {
        "not", "never", "no", "cannot", "can't", "cant", "dont", "don't",
        "doesnt", "doesn't", "wont", "won't", "shouldnt", "shouldn't",
        "without", "stop", "stopped", "hardly", "barely", "refusing", "refused"
    }

    # Clinical Antonym Pairs (Ensures an antonym replacement never inverts meaning)
    ANTONYM_PAIRS = {
        "safe": "unsafe", "unsafe": "safe",
        "hot": "cold", "cold": "hot",
        "fever": "hypothermia", "hypothermia": "fever",
        "more": "less", "less": "more",
        "high": "low", "low": "high",
        "gain": "loss", "loss": "gain",
        "stop": "continue", "continue": "stop",
        "increase": "decrease", "decrease": "increase",
    }

    # High-Frequency Pediatric & Neonatal Typo Correction Map
    CLINICAL_TYPO_MAP = {
        # Kangaroo Care & Sleep
        "kangroo": "kangaroo",
        "kangeroo": "kangaroo",
        "kangaroe": "kangaroo",
        "kangaro": "kangaroo",
        "skintoskin": "skin-to-skin",
        "skintskin": "skin-to-skin",
        "sllep": "sleep",
        "slepp": "sleep",
        "crb": "crib",
        "bassinet": "bassinet",
        "basinet": "bassinet",
        "matress": "mattress",
        "blanquet": "blanket",
        "blankett": "blanket",

        # Feeding & Digestion
        "breat": "breast",
        "brest": "breast",
        "breastmilk": "breast milk",
        "formla": "formula",
        "formulaa": "formula",
        "fourmula": "formula",
        "fedding": "feeding",
        "feedng": "feeding",
        "feading": "feeding",
        "fead": "feed",
        "drankk": "drank",
        "drnk": "drank",
        "latchh": "latch",
        "lacting": "latching",
        "lach": "latch",
        "spiting": "spitting",
        "spittingg": "spitting",
        "spitup": "spit up",
        "vomit": "vomit",
        "vomitting": "vomiting",
        "vomitedd": "vomited",
        "puke": "vomit",
        "puking": "vomiting",
        "hicups": "hiccups",
        "hiccough": "hiccups",
        "hicup": "hiccup",
        "burpingg": "burping",
        "burp": "burp",
        "colick": "colic",
        "refluxx": "reflux",

        # Vitals & Danger Signs
        "temprature": "temperature",
        "tempreature": "temperature",
        "temprater": "temperature",
        "temparature": "temperature",
        "fevr": "fever",
        "feever": "fever",
        "retractions": "retractions",
        "retraction": "retractions",
        "retacting": "retracting",
        "retact": "retract",
        "cyanosis": "cyanosis",
        "syanosis": "cyanosis",
        "apnea": "apnea",
        "apnoea": "apnea",
        "breathingg": "breathing",
        "breating": "breathing",
        "duskey": "dusky",
        "lethargic": "lethargic",
        "lethargy": "lethargy",
        "lethargick": "lethargic",
        "bilious": "bilious",
        "biliuos": "bilious",

        # Diapers & Elimination
        "diper": "diaper",
        "dipher": "diaper",
        "daipar": "diaper",
        "diapper": "diaper",
        "stoll": "stool",
        "stols": "stools",
        "poop": "stool",
        "pooped": "stooled",
        "pooping": "stooling",
        "urin": "urine",
        "urinate": "urinate",

        # Growth & Math
        "wieght": "weight",
        "weigth": "weight",
        "wight": "weight",
        "wait": "weight",  # in context like 'check liam wait'
        "gramms": "grams",
        "fenton": "Fenton",
        "fentons": "Fenton",
        "percentil": "percentile",

        # Medication & Medical Professionals
        "medecine": "medicine",
        "medcine": "medicine",
        "medicationn": "medication",
        "siringe": "syringe",
        "syring": "syringe",
        "vitmin": "vitamin",
        "vitamins": "vitamins",
        "vitamind": "vitamin D",
        "pediatrician": "pediatrician",
        "pediatrition": "pediatrician",
        "peadiatrician": "pediatrician",
        "peadiatrics": "pediatrics",
        "neonatologist": "neonatologist",
        "neonatalogist": "neonatologist",
        "neonate": "neonate",
        "preemie": "preterm infant",
        "premie": "preterm infant",
        "preme": "preterm infant",

        # Hygiene
        "steralize": "sterilize",
        "steralise": "sterilize",
        "sterlize": "sterilize",
        "sterilisation": "sterilization",
        "sanitise": "sanitize",
    }

    # Clinical Synonym Standardizations (Replaces informal slang with canonical clinical terminology)
    CLINICAL_SYNONYM_REPLACEMENTS = [
        # Skin-to-skin terminology
        (r'\bskin\s*to\s*skin\b', "skin-to-skin"),
        (r'\bchest\s*to\s*chest\b', "skin-to-skin kangaroo care"),
        (r'\bkmc\b', "Kangaroo Mother Care (KMC)"),

        # Milk and nutrition
        (r"\bmom'?s\s*milk\b", "breast milk"),
        (r"\bmother'?s\s*milk\b", "breast milk"),
        (r'\bebm\b', "expressed breast milk"),
        (r'\bbm\b', "breast milk"),

        # Elimination
        (r'\bwet\s*nappy\b', "wet diaper"),
        (r'\bdirty\s*nappy\b', "soiled diaper"),
        (r'\bdirty\s*diaper\b', "soiled diaper"),
        (r'\bpotty\b', "stool"),
        (r'\bpee\s*diaper\b', "wet diaper"),

        # Body parts
        (r'\btummy\b', "stomach"),
        (r'\bbelly\b', "stomach"),

        # Gastrointestinal symptoms
        (r'\bthrowing\s*up\b', "vomiting"),
        (r'\bthrow\s*up\b', "vomit"),
        (r'\bpuking\b', "vomiting"),
    ]

    @classmethod
    def extract_negations(cls, text: str) -> Set[str]:
        """Extracts all negation tokens present in the text."""
        words = set(re.findall(r"\b[a-zA-Z']+\b", text.lower()))
        return words.intersection(cls.NEGATION_TOKENS)

    @classmethod
    def normalize_query(cls, query: str, preserve_exact_numbers: bool = True) -> Dict[str, Any]:
        """
        Normalizes spelling, grammar, and synonyms while strictly maintaining clinical context.
        """
        raw_text = query.strip()
        original_negations = cls.extract_negations(raw_text)
        corrections: List[Dict[str, str]] = []

        working_text = raw_text

        # ── 1. Spacing and Repetitive Character Cleaning ──────────────────────
        # Collapse multiple punctuation (e.g. '????' -> '?', '!!!!' -> '!')
        working_text = re.sub(r'\?{2,}', '?', working_text)
        working_text = re.sub(r'!{2,}', '!', working_text)
        # Collapse duplicate characters exceeding 2 (e.g. 'sooooo' -> 'soo', 'heeeelp' -> 'help')
        working_text = re.sub(r'([a-zA-Z])\1{2,}', r'\1\1', working_text)

        # ── 2. Unit and Number Standardization ────────────────────────────────
        # Normalize unit spacing: '50ml' -> '50 mL', '2400g' -> '2400 g', '37.7c' -> '37.7 °C'
        if preserve_exact_numbers:
            working_text = re.sub(r'(\d+(?:\.\d+)?)\s*(?:ml|milliliters?)\b', r'\1 mL', working_text, flags=re.IGNORECASE)
            working_text = re.sub(r'(\d+(?:\.\d+)?)\s*(?:g|grams?)\b', r'\1 g', working_text, flags=re.IGNORECASE)
            working_text = re.sub(r'(\d+(?:\.\d+)?)\s*(?:kg|kilograms?)\b', r'\1 kg', working_text, flags=re.IGNORECASE)
            working_text = re.sub(r'(\d{2}(?:\.\d)?)\s*(?:c|deg|degrees|celsius)\b', r'\1 °C', working_text, flags=re.IGNORECASE)

        # ── 3. Clinical Typo & Spelling Correction ────────────────────────────
        words = re.findall(r"\b[a-zA-Z'-]+\b", working_text)
        canonical_vocab = [
            "temperature", "kangaroo", "formula", "breastfeeding", "retractions",
            "cyanosis", "apnea", "fever", "diaper", "mattress", "bassinet", "blanket",
            "pacifier", "swaddling", "sterilization", "weight", "growth", "preterm",
            "minimum", "maximum", "ambient", "hypothermia", "celsius", "fahrenheit",
            "degrees", "unsettled", "respiratory", "jaundice", "bilirubin", "vitamins"
        ]
        for w in words:
            w_lower = w.lower()
            replacement = None
            if w_lower in cls.CLINICAL_TYPO_MAP:
                replacement = cls.CLINICAL_TYPO_MAP[w_lower]
            elif len(w_lower) >= 5 and w_lower not in canonical_vocab:
                # Dynamic phonetic/Levenshtein fuzzy matching against canonical clinical vocabulary
                matches = difflib.get_close_matches(w_lower, canonical_vocab, n=1, cutoff=0.70)
                if matches:
                    replacement = matches[0]

            if replacement and replacement != w_lower:
                # Preserve capitalization
                if w.istitle():
                    replacement = replacement.capitalize()
                pattern = r'\b' + re.escape(w) + r'\b'
                working_text = re.sub(pattern, replacement, working_text, count=1)
                corrections.append({
                    "original": w,
                    "corrected": replacement,
                    "type": "spelling_typo"
                })

        # ── 4. Synonym Standardization & Canonical Phrasing ───────────────────
        for syn_pattern, syn_replacement in cls.CLINICAL_SYNONYM_REPLACEMENTS:
            if re.search(syn_pattern, working_text, flags=re.IGNORECASE):
                working_text = re.sub(syn_pattern, syn_replacement, working_text, flags=re.IGNORECASE)
                corrections.append({
                    "pattern": syn_pattern,
                    "canonical": syn_replacement,
                    "type": "synonym_canonicalization"
                })

        # ── 5. Grammar & Punctuation Clean-up ──────────────────────────────────
        # Ensure proper spacing around punctuation
        working_text = re.sub(r'\s+([?,.!])', r'\1', working_text)
        working_text = re.sub(r'\s+', ' ', working_text).strip()

        # If interrogative without question mark, append question mark
        interrogative_starters = ["is", "can", "should", "how", "what", "why", "when", "does", "are", "do", "would", "could"]
        first_word = working_text.split()[0].lower() if working_text else ""
        if first_word in interrogative_starters and not working_text.endswith("?"):
            working_text += "?"

        # Capitalize first letter
        if working_text and working_text[0].islower():
            working_text = working_text[0].upper() + working_text[1:]

        # ── 6. Negation & Antonym Context Verification Guard ──────────────────
        # Validate that no negation was lost or flipped
        new_negations = cls.extract_negations(working_text)
        if original_negations != new_negations:
            # If any original negation was dropped, restore it to prevent clinical polarity inversion
            missing_negations = original_negations - new_negations
            if missing_negations:
                # Fall back to raw text with basic whitespace cleanup if negation was compromised
                working_text = raw_text

        # Verify antonym preservation
        for term, antonym in cls.ANTONYM_PAIRS.items():
            if term in raw_text.lower() and antonym in working_text.lower():
                # Inversion detected! Revert to original term
                working_text = re.sub(r'\b' + re.escape(antonym) + r'\b', term, working_text, flags=re.IGNORECASE)

        return {
            "original_query": raw_text,
            "normalized_query": working_text,
            "corrections_applied": corrections,
            "negations_preserved": list(original_negations),
            "has_modifications": (raw_text != working_text),
        }


# Global Singleton Normalizer
clinical_normalizer = ClinicalQueryNormalizer()
