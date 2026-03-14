"""Blob text extraction for indexing file content in Typesense.

Extracts text from PDF, DOCX, and other file types stored as
NamedBlobFile fields on Plone content objects. The extraction is
optional -- if extraction libraries are not installed, it falls back
gracefully to returning empty text.

The primary strategy is to use Plone's portal_transforms tool which
already supports many content types. As a fallback for PDF files,
PyPDF2/pypdf is attempted. Plain text and HTML are handled natively.
"""

import re

from plone import api
from plone.dexterity.utils import iterSchemata
from plone.namedfile.interfaces import INamedBlobFileField
from zope.schema import getFields

from plone.typesense import log


# Optional imports for direct extraction fallbacks
try:
    from pypdf import PdfReader

    HAS_PYPDF = True
except ImportError:
    try:
        from PyPDF2 import PdfReader

        HAS_PYPDF = True
    except ImportError:
        HAS_PYPDF = False

try:
    import docx

    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False


def extract_text_from_blob(blob_field_value):
    """Extract text from a NamedBlobFile value.

    Tries multiple strategies in order:
    1. portal_transforms (Plone's built-in transform machinery)
    2. Direct extraction using pypdf/python-docx for known types
    3. Decode as UTF-8 for plain text content types

    Returns an empty string if extraction fails or is not possible.

    @param blob_field_value: A NamedBlobFile instance
    @return: Extracted text as a string
    """
    if blob_field_value is None:
        return ""

    content_type = getattr(blob_field_value, "contentType", "") or ""
    data = blob_field_value.data
    if not data:
        return ""

    # Try portal_transforms first (best integration with Plone)
    text = _extract_via_portal_transforms(data, content_type)
    if text:
        return text

    # Fallback: direct extraction by content type
    text = _extract_directly(data, content_type, blob_field_value)
    return text


def _extract_via_portal_transforms(data, content_type):
    """Use Plone's portal_transforms to convert data to text.

    @param data: Raw file bytes
    @param content_type: MIME type string
    @return: Extracted text or empty string
    """
    try:
        pt = api.portal.get_tool("portal_transforms")
    except Exception:
        return ""

    if not pt:
        return ""

    try:
        result = pt.convertTo(
            "text/plain",
            data,
            mimetype=content_type,
        )
        if result:
            text = result.getData()
            if isinstance(text, bytes):
                text = text.decode("utf-8", "ignore")
            return _clean_text(text)
    except Exception as exc:
        log.debug(
            f"portal_transforms could not convert {content_type}: {exc}"
        )

    return ""


def _extract_directly(data, content_type, blob_field_value):
    """Direct text extraction as fallback when portal_transforms fails.

    @param data: Raw file bytes
    @param content_type: MIME type string
    @param blob_field_value: The original blob field value
    @return: Extracted text or empty string
    """
    # Plain text
    if content_type.startswith("text/plain"):
        if isinstance(data, bytes):
            return data.decode("utf-8", "ignore")
        return str(data)

    # HTML
    if content_type in ("text/html", "application/xhtml+xml"):
        return _strip_html_tags(data)

    # PDF
    if content_type == "application/pdf":
        return _extract_pdf(data)

    # DOCX
    if content_type in (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ):
        return _extract_docx(data)

    log.debug(f"No text extractor available for content type: {content_type}")
    return ""


def _extract_pdf(data):
    """Extract text from PDF data using pypdf/PyPDF2.

    @param data: Raw PDF bytes
    @return: Extracted text or empty string
    """
    if not HAS_PYPDF:
        log.debug("pypdf/PyPDF2 not installed, cannot extract PDF text")
        return ""

    try:
        import io

        reader = PdfReader(io.BytesIO(data))
        pages_text = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages_text.append(text)
        return _clean_text("\n".join(pages_text))
    except Exception as exc:
        log.warning(f"Failed to extract text from PDF: {exc}")
        return ""


def _extract_docx(data):
    """Extract text from DOCX data using python-docx.

    @param data: Raw DOCX bytes
    @return: Extracted text or empty string
    """
    if not HAS_DOCX:
        log.debug("python-docx not installed, cannot extract DOCX text")
        return ""

    try:
        import io

        doc = docx.Document(io.BytesIO(data))
        paragraphs = [p.text for p in doc.paragraphs if p.text]
        return _clean_text("\n".join(paragraphs))
    except Exception as exc:
        log.warning(f"Failed to extract text from DOCX: {exc}")
        return ""


def _strip_html_tags(data):
    """Remove HTML tags and return plain text.

    @param data: HTML content as bytes or string
    @return: Plain text string
    """
    if isinstance(data, bytes):
        data = data.decode("utf-8", "ignore")
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", " ", data)
    return _clean_text(text)


def _clean_text(text):
    """Clean extracted text by normalizing whitespace.

    @param text: Raw text string
    @return: Cleaned text string
    """
    if not text:
        return ""
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_blob_texts(obj):
    """Extract text from all blob fields on a content object.

    Iterates over all schemata of the object, finds NamedBlobFile fields,
    and extracts text from each one.

    @param obj: A Dexterity content object
    @return: Dict mapping field name to extracted text
    """
    extracted = {}
    try:
        schemata = list(iterSchemata(obj))
    except Exception:
        return extracted

    for schema in schemata:
        for name, field in getFields(schema).items():
            if INamedBlobFileField.providedBy(field):
                blob_value = field.get(obj)
                if blob_value:
                    text = extract_text_from_blob(blob_value)
                    if text:
                        extracted[name] = text
    return extracted


def get_searchable_blob_text(obj):
    """Get combined searchable text from all blob fields.

    This is intended to be appended to SearchableText for full-text search.

    @param obj: A Dexterity content object
    @return: Combined text from all blobs, space-separated
    """
    texts = extract_blob_texts(obj)
    if texts:
        return " ".join(texts.values())
    return ""
