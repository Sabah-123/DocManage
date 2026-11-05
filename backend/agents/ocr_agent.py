import os
import re
import tempfile
import numpy as np
from pathlib import Path
from typing import Tuple
from PIL import Image
import pytesseract
import cv2

from core.config import settings

pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd

import threading

# Chargement paresseux des modèles lourds
_paddle_ocr = None
_paddle_lock = threading.Lock()

_pix2tex_model = None
_pix2tex_lock = threading.Lock()


def _get_paddle():
    global _paddle_ocr
    if _paddle_ocr is None:
        with _paddle_lock:
            if _paddle_ocr is None:
                from paddleocr import PaddleOCR
                _paddle_ocr = PaddleOCR(
                    use_angle_cls=True,
                    lang="fr",
                    use_gpu=settings.paddle_use_gpu,
                    show_log=False
                )
    return _paddle_ocr


def _get_pix2tex():
    global _pix2tex_model
    if _pix2tex_model is None:
        with _pix2tex_lock:
            if _pix2tex_model is None:
                from pix2tex.cli import LatexOCR
                _pix2tex_model = LatexOCR()
    return _pix2tex_model


def _load_image(image_input) -> np.ndarray:
    if isinstance(image_input, (str, Path)):
        return cv2.imread(str(image_input))
    if isinstance(image_input, Image.Image):
        return cv2.cvtColor(np.array(image_input), cv2.COLOR_RGB2BGR)
    if isinstance(image_input, bytes):
        arr = np.frombuffer(image_input, np.uint8)
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return image_input


def _is_formula_region(region: np.ndarray) -> bool:
    gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    density = np.sum(binary > 0) / binary.size

    # Formules mathématiques : densité de pixels modérée + contours fragmentés
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if len(contours) == 0:
        return False

    avg_area = np.mean([cv2.contourArea(c) for c in contours])
    is_formula = (0.03 < density < 0.35) and (avg_area < 150) and (len(contours) > 5)
    return bool(is_formula)


def _is_handwritten(region: np.ndarray) -> bool:
    gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    # Texte manuscrit : variance de gradient plus élevée, contours irréguliers
    return laplacian_var > 800


def _ocr_tesseract(region: np.ndarray) -> str:
    pil_img = Image.fromarray(cv2.cvtColor(region, cv2.COLOR_BGR2RGB))
    config = "--oem 3 --psm 6 -l fra"
    text = pytesseract.image_to_string(pil_img, config=config)
    return text.strip()


def _ocr_paddle(region: np.ndarray) -> str:
    paddle = _get_paddle()
    try:
        # PaddleOCR accepte directement les arrays numpy, pas besoin de fichier temporaire
        result = paddle.ocr(region, cls=True)
        if not result or not result[0]:
            return ""
        lines = [line[1][0] for line in result[0] if line and line[1]]
        return "\n".join(lines)
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception("Erreur PaddleOCR")
        return ""


def _ocr_formula(region: np.ndarray) -> str:
    pix2tex = _get_pix2tex()
    pil_img = Image.fromarray(cv2.cvtColor(region, cv2.COLOR_BGR2RGB))
    try:
        latex = pix2tex(pil_img)
        return f"$${latex}$$"
    except Exception:
        return _ocr_tesseract(region)


def _split_regions(image: np.ndarray) -> list:
    # Optimisation: On garde cette fonction au cas où, mais pour la vitesse on va éviter de l'utiliser sur toute une page
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (20, 3))
    dilated = cv2.dilate(binary, kernel, iterations=2)
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    regions = []
    for cnt in sorted(contours, key=lambda c: cv2.boundingRect(c)[1]):
        x, y, w, h = cv2.boundingRect(cnt)
        if w > 20 and h > 8:
            regions.append((y, image[y:y+h, x:x+w]))

    return regions if regions else [(0, image)]


def ocr_image(image_input) -> Tuple[str, str]:
    """
    Retourne (texte_extrait, moteur_utilisé)
    """
    image = _load_image(image_input)
    if image is None:
        return "", "error"

    # PaddleOCR sur toute l'image est infiniment plus rapide et précis
    text = _ocr_paddle(image)
    if text.strip():
        return text, "paddle"
    
    # Fallback sur tesseract si Paddle ne trouve rien
    return _ocr_tesseract(image), "tesseract"


def ocr_pdf(pdf_bytes: bytes) -> Tuple[str, str]:
    """OCR complet d'un PDF page par page"""
    import fitz
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    all_text = []
    engines_used = set()

    for page_num, page in enumerate(doc):
        # Tenter extraction texte natif d'abord
        native_text = page.get_text().strip()
        if len(native_text) > 50:
            all_text.append(f"[Page {page_num + 1}]\n{native_text}")
            engines_used.add("native")
            continue

        # Sinon rasteriser et OCR
        mat = fitz.Matrix(2.0, 2.0)
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")
        text, engine = ocr_image(img_bytes)
        all_text.append(f"[Page {page_num + 1}]\n{text}")
        engines_used.add(engine)

    doc.close()
    engine_label = "mixed" if len(engines_used) > 1 else (engines_used.pop() if engines_used else "tesseract")
    return "\n\n".join(all_text), engine_label


def ocr_docx(docx_bytes: bytes) -> Tuple[str, str]:
    """Extraction texte d'un fichier DOCX"""
    import io
    from docx import Document
    doc = Document(io.BytesIO(docx_bytes))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n\n".join(paragraphs), "native"


def extract_text(file_bytes: bytes, file_ext: str) -> Tuple[str, str]:
    """Point d'entrée principal selon l'extension"""
    ext = file_ext.lower().lstrip(".")

    if ext == "pdf":
        return ocr_pdf(file_bytes)
    elif ext in ("jpg", "jpeg", "png", "bmp", "tiff", "webp"):
        return ocr_image(file_bytes)
    elif ext == "docx":
        return ocr_docx(file_bytes)
    elif ext == "txt":
        return file_bytes.decode("utf-8", errors="replace"), "native"
    elif ext == "eml":
        import email
        msg = email.message_from_bytes(file_bytes)
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    body += part.get_payload(decode=True).decode("utf-8", errors="replace")
        else:
            body = msg.get_payload(decode=True).decode("utf-8", errors="replace")
        return body, "native"
    else:
        return "", "unsupported"
