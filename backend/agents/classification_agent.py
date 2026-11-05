import json
import logging
import re
import threading
import langdetect
from groq import Groq
from groq import APIConnectionError as GroqAPIConnectionError

from core.config import settings
from models.schemas import ClassificationResult

logger = logging.getLogger(__name__)

_groq_client = None
_groq_lock = threading.Lock()

def _get_groq():
    global _groq_client
    if _groq_client is None:
        with _groq_lock:
            if _groq_client is None:
                _groq_client = Groq(api_key=settings.groq_api_key)
    return _groq_client

SUBJECTS = ["Mathématiques", "Physique", "Informatique", "Chimie", "Histoire", "Langues", "Économie", "Biologie", "Autre"]
DOC_TYPES = ["Cours", "Exercice", "Examen", "Rapport", "Résumé", "Formulaire", "Facture", "Contrat", "Autre"]

CLASSIFICATION_PROMPT = """Tu es un assistant de classification de documents académiques et professionnels.

Analyse le texte suivant et retourne UNIQUEMENT un objet JSON valide avec ces champs :
- subject : la matière ou domaine parmi {subjects}
- doc_type : le type de document parmi {types}
- title_suggested : un titre court suggéré (max 60 caractères)
- language : la langue principale (fr / en / ar)
- confidence : ton niveau de confiance entre 0.0 et 1.0

Texte à analyser (500 premiers tokens) :
{text}

Réponds UNIQUEMENT avec le JSON, sans explication ni balise markdown."""


def detect_language(text: str) -> str:
    try:
        lang = langdetect.detect(text[:500])
        mapping = {"fr": "fr", "en": "en", "ar": "ar"}
        return mapping.get(lang, "fr")
    except Exception:
        return "fr"


def classify_document(text: str) -> ClassificationResult:
    # Tronquer aux 500 premiers tokens environ
    text_sample = text[:2000].strip()

    if not text_sample:
        return ClassificationResult(
            subject="Autre",
            doc_type="Autre",
            title_suggested="Document sans contenu",
            language="fr",
            confidence=0.0
        )

    language = detect_language(text_sample)

    prompt = CLASSIFICATION_PROMPT.format(
        subjects=", ".join(SUBJECTS),
        types=", ".join(DOC_TYPES),
        text=text_sample
    )
    try:
        client = _get_groq()
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=settings.groq_model,
            temperature=0.1,
            max_tokens=200,
        )
        raw = chat_completion.choices[0].message.content.strip()

        # Nettoyer les éventuels blocs markdown
        raw = re.sub(r"```json\s*|\s*```", "", raw).strip()

        data = json.loads(raw)

        # Valider et sécuriser les champs
        subject = data.get("subject", "Autre")
        if subject not in SUBJECTS:
            subject = "Autre"

        doc_type = data.get("doc_type", "Autre")
        if doc_type not in DOC_TYPES:
            doc_type = "Autre"

        confidence = float(data.get("confidence", 0.5))
        confidence = max(0.0, min(1.0, confidence))

        return ClassificationResult(
            subject=subject,
            doc_type=doc_type,
            title_suggested=str(data.get("title_suggested", "Document"))[:255],
            language=language,
            confidence=confidence
        )

    except GroqAPIConnectionError:
        logger.warning("classify_document: Groq injoignable (pas d'internet), fallback mots-clés")
        return _keyword_classify(text_sample, language)
    except (json.JSONDecodeError, KeyError, ValueError):
        # Fallback : classification basique par mots-clés
        return _keyword_classify(text_sample, language)


def _keyword_classify(text: str, language: str) -> ClassificationResult:
    text_lower = text.lower()

    subject_keywords = {
        "Mathématiques": ["théorème", "dérivée", "intégrale", "équation", "vecteur", "matrice", "limite"],
        "Physique": ["force", "énergie", "vitesse", "accélération", "thermodynamique", "optique"],
        "Informatique": ["algorithme", "fonction", "variable", "python", "java", "code", "programme"],
        "Chimie": ["molécule", "réaction", "atome", "liaison", "oxydation", "acide"],
        "Histoire": ["guerre", "révolution", "empire", "siècle", "traité", "civilisation"],
        "Biologie": ["cellule", "adn", "protéine", "organisme", "évolution", "écosystème"],
    }

    type_keywords = {
        "Cours": ["cours", "chapitre", "définition", "propriété", "théorème", "introduction"],
        "Exercice": ["exercice", "problème", "solution", "résoudre", "calculer", "td", "tp"],
        "Examen": ["examen", "contrôle", "durée", "barème", "note", "devoir"],
        "Rapport": ["rapport", "introduction", "conclusion", "objectif", "résultat", "analyse"],
        "Résumé": ["résumé", "synthèse", "fiche", "points clés", "bilan"],
    }

    best_subject, best_subject_score = "Autre", 0
    for subj, keywords in subject_keywords.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > best_subject_score:
            best_subject, best_subject_score = subj, score

    best_type, best_type_score = "Autre", 0
    for dtype, keywords in type_keywords.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > best_type_score:
            best_type, best_type_score = dtype, score

    confidence = min(0.6, 0.2 + (best_subject_score + best_type_score) * 0.05)

    return ClassificationResult(
        subject=best_subject,
        doc_type=best_type,
        title_suggested="Document classifié automatiquement",
        language=language,
        confidence=confidence
    )


def classify_document_for_user(
    text: str,
    user_subjects: list[str],
) -> ClassificationResult:
    """
    Variante contextualisée de classify_document() qui utilise la liste
    de matières personnalisées de l'utilisateur (issues de UserSubject.name).

    Règles :
    - user_subjects vide → délègue à classify_document() (fallback)
    - Garantit que le sujet retourné est dans user_subjects
    - Fonctions existantes non modifiées
    """
    if not user_subjects:
        logger.warning("classify_document_for_user: liste vide, fallback classify_document()")
        return classify_document(text)

    text_sample = text[:2000].strip()
    if not text_sample:
        fallback_subject = next(
            (s for s in user_subjects if s.lower() == "autre"), user_subjects[-1]
        )
        return ClassificationResult(
            subject=fallback_subject,
            doc_type="Autre",
            title_suggested="Document sans contenu",
            language="fr",
            confidence=0.0,
        )

    language = detect_language(text_sample)

    prompt = CLASSIFICATION_PROMPT.format(
        subjects=", ".join(user_subjects),
        types=", ".join(DOC_TYPES),
        text=text_sample,
    )

    try:
        client = _get_groq()
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=settings.groq_model,
            temperature=0.1,
            max_tokens=200,
        )
        raw = chat_completion.choices[0].message.content.strip()
        raw = re.sub(r"```json\s*|\s*```", "", raw).strip()
        data = json.loads(raw)

        subject = data.get("subject", "")
        # Validation stricte : le sujet doit appartenir à la liste utilisateur
        if subject not in user_subjects:
            # Tentative de correspondance insensible à la casse
            lower_map = {s.lower(): s for s in user_subjects}
            subject = lower_map.get(subject.lower(), "")
        if not subject:
            subject = next(
                (s for s in user_subjects if s.lower() == "autre"), user_subjects[-1]
            )

        doc_type = data.get("doc_type", "Autre")
        if doc_type not in DOC_TYPES:
            doc_type = "Autre"

        confidence = float(data.get("confidence", 0.5))
        confidence = max(0.0, min(1.0, confidence))

        return ClassificationResult(
            subject=subject,
            doc_type=doc_type,
            title_suggested=str(data.get("title_suggested", "Document"))[:255],
            language=language,
            confidence=confidence,
        )

    except GroqAPIConnectionError:
        logger.warning("classify_document_for_user: Groq injoignable (pas d'internet), fallback mots-clés")
        result = _keyword_classify(text_sample, language)
        if result.subject not in user_subjects:
            lower_map = {s.lower(): s for s in user_subjects}
            mapped = lower_map.get(result.subject.lower(), "")
            result = ClassificationResult(
                subject=mapped or next(
                    (s for s in user_subjects if s.lower() == "autre"), user_subjects[-1]
                ),
                doc_type=result.doc_type,
                title_suggested=result.title_suggested,
                language=result.language,
                confidence=result.confidence,
            )
        return result
    except (json.JSONDecodeError, KeyError, ValueError):
        logger.warning("classify_document_for_user: JSON invalide, fallback keyword pour user")
        result = _keyword_classify(text_sample, language)
        # Remapper le subject vers la liste utilisateur
        if result.subject not in user_subjects:
            lower_map = {s.lower(): s for s in user_subjects}
            mapped = lower_map.get(result.subject.lower(), "")
            result = ClassificationResult(
                subject=mapped or next(
                    (s for s in user_subjects if s.lower() == "autre"), user_subjects[-1]
                ),
                doc_type=result.doc_type,
                title_suggested=result.title_suggested,
                language=result.language,
                confidence=result.confidence,
            )
        return result
    except Exception:
        logger.exception("classify_document_for_user: erreur inattendue")
        return classify_document(text)
