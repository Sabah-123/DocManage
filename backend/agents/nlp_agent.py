import re
from typing import List, Tuple
from core.database import NamedEntity

import threading

# Chargement paresseux de spaCy
_nlp = None
_nlp_lock = threading.Lock()


def _get_nlp():
    global _nlp
    if _nlp is None:
        with _nlp_lock:
            if _nlp is None:
                import spacy
                try:
                    _nlp = spacy.load("fr_core_news_md")
                except OSError:
                    # Fallback vers le petit modèle
                    try:
                        _nlp = spacy.load("fr_core_news_sm")
                    except OSError:
                        raise RuntimeError(
                            "Modèle spaCy non trouvé. Exécuter : python -m spacy download fr_core_news_md"
                        )
    return _nlp


# Labels spaCy → labels lisibles
LABEL_MAP = {
    "PER": "Personne",
    "ORG": "Organisation",
    "LOC": "Lieu",
    "DATE": "Date",
    "MISC": "Divers",
    "MONEY": "Montant",
    "TIME": "Temps",
    "PERCENT": "Pourcentage",
    "CARDINAL": "Nombre",
}


def extract_entities(text: str) -> List[Tuple[str, str]]:
    """
    Retourne une liste de (texte_entité, label)
    """
    nlp = _get_nlp()

    # Traiter par chunks de 100k caractères max (limite spaCy)
    max_length = 90000
    all_entities = []
    seen = set()

    for start in range(0, len(text), max_length):
        chunk = text[start:start + max_length]
        doc = nlp(chunk)

        for ent in doc.ents:
            label = LABEL_MAP.get(ent.label_, ent.label_)
            entity_text = ent.text.strip()

            # Filtrer les entités trop courtes ou dupliquées
            if len(entity_text) < 2:
                continue
            key = (entity_text.lower(), label)
            if key in seen:
                continue
            seen.add(key)

            all_entities.append((entity_text, label))

    # Compléter avec des regex pour les formules mathématiques et montants
    math_patterns = re.findall(r"\$\$[^$]+\$\$|\$[^$]+\$", text)
    for formula in math_patterns[:10]:
        key = (formula[:50], "Formule")
        if key not in seen:
            all_entities.append((formula[:255], "Formule"))
            seen.add(key)

    amount_patterns = re.findall(r"\d+[.,]\d+\s*(?:€|EUR|MAD|USD|\$)", text)
    for amount in amount_patterns[:10]:
        key = (amount, "Montant")
        if key not in seen:
            all_entities.append((amount, "Montant"))
            seen.add(key)

    return all_entities[:100]


def entities_to_db_objects(document_id: int, entities: List[Tuple[str, str]]) -> List[NamedEntity]:
    return [
        NamedEntity(
            document_id=document_id,
            entity_text=text,
            entity_label=label
        )
        for text, label in entities
    ]
