"""Tests for blob text extraction module."""

import unittest
from unittest.mock import MagicMock, patch, PropertyMock


class TestCleanText(unittest.TestCase):
    """Test the _clean_text helper."""

    def test_normalizes_whitespace(self):
        from plone.typesense.blob_extraction import _clean_text

        result = _clean_text("hello   world\n\nfoo\tbar")
        self.assertEqual(result, "hello world foo bar")

    def test_strips_leading_trailing(self):
        from plone.typesense.blob_extraction import _clean_text

        result = _clean_text("  hello world  ")
        self.assertEqual(result, "hello world")

    def test_empty_string(self):
        from plone.typesense.blob_extraction import _clean_text

        self.assertEqual(_clean_text(""), "")

    def test_none(self):
        from plone.typesense.blob_extraction import _clean_text

        self.assertEqual(_clean_text(None), "")


class TestStripHtmlTags(unittest.TestCase):
    """Test HTML tag stripping."""

    def test_basic_html(self):
        from plone.typesense.blob_extraction import _strip_html_tags

        result = _strip_html_tags("<p>Hello <b>world</b></p>")
        self.assertEqual(result, "Hello world")

    def test_complex_html(self):
        from plone.typesense.blob_extraction import _strip_html_tags

        html = '<div class="foo"><h1>Title</h1><p>Content here</p></div>'
        result = _strip_html_tags(html)
        self.assertIn("Title", result)
        self.assertIn("Content here", result)

    def test_bytes_input(self):
        from plone.typesense.blob_extraction import _strip_html_tags

        result = _strip_html_tags(b"<p>Hello</p>")
        self.assertEqual(result, "Hello")


class TestExtractTextFromBlob(unittest.TestCase):
    """Test the main extract_text_from_blob function."""

    def test_none_blob_returns_empty(self):
        from plone.typesense.blob_extraction import extract_text_from_blob

        self.assertEqual(extract_text_from_blob(None), "")

    def test_empty_data_returns_empty(self):
        from plone.typesense.blob_extraction import extract_text_from_blob

        blob = MagicMock()
        blob.data = b""
        blob.contentType = "application/pdf"
        self.assertEqual(extract_text_from_blob(blob), "")

    @patch("plone.typesense.blob_extraction._extract_via_portal_transforms")
    def test_uses_portal_transforms_first(self, mock_pt):
        from plone.typesense.blob_extraction import extract_text_from_blob

        mock_pt.return_value = "extracted via transforms"
        blob = MagicMock()
        blob.data = b"some data"
        blob.contentType = "application/pdf"

        result = extract_text_from_blob(blob)
        self.assertEqual(result, "extracted via transforms")
        mock_pt.assert_called_once()

    @patch("plone.typesense.blob_extraction._extract_via_portal_transforms")
    @patch("plone.typesense.blob_extraction._extract_directly")
    def test_falls_back_to_direct_extraction(self, mock_direct, mock_pt):
        from plone.typesense.blob_extraction import extract_text_from_blob

        mock_pt.return_value = ""  # portal_transforms fails
        mock_direct.return_value = "extracted directly"
        blob = MagicMock()
        blob.data = b"some data"
        blob.contentType = "application/pdf"

        result = extract_text_from_blob(blob)
        self.assertEqual(result, "extracted directly")

    def test_plain_text_extraction(self):
        from plone.typesense.blob_extraction import _extract_directly

        result = _extract_directly(
            b"Hello plain text", "text/plain", None
        )
        self.assertEqual(result, "Hello plain text")

    def test_html_extraction(self):
        from plone.typesense.blob_extraction import _extract_directly

        result = _extract_directly(
            b"<p>Hello HTML</p>", "text/html", None
        )
        self.assertIn("Hello HTML", result)

    def test_unknown_type_returns_empty(self):
        from plone.typesense.blob_extraction import _extract_directly

        result = _extract_directly(
            b"\x00\x01\x02", "application/octet-stream", None
        )
        self.assertEqual(result, "")


class TestExtractPdf(unittest.TestCase):
    """Test PDF extraction."""

    def test_no_pypdf_returns_empty(self):
        from plone.typesense.blob_extraction import _extract_pdf

        with patch("plone.typesense.blob_extraction.HAS_PYPDF", False):
            result = _extract_pdf(b"fake pdf data")
            self.assertEqual(result, "")

    def test_invalid_pdf_returns_empty(self):
        from plone.typesense.blob_extraction import _extract_pdf, HAS_PYPDF

        if not HAS_PYPDF:
            self.skipTest("pypdf/PyPDF2 not installed")
        result = _extract_pdf(b"not a real pdf")
        self.assertEqual(result, "")


class TestExtractDocx(unittest.TestCase):
    """Test DOCX extraction."""

    def test_no_docx_lib_returns_empty(self):
        from plone.typesense.blob_extraction import _extract_docx

        with patch("plone.typesense.blob_extraction.HAS_DOCX", False):
            result = _extract_docx(b"fake docx data")
            self.assertEqual(result, "")


class TestExtractBlobTexts(unittest.TestCase):
    """Test extract_blob_texts on content objects."""

    @patch("plone.typesense.blob_extraction.iterSchemata")
    @patch("plone.typesense.blob_extraction.getFields")
    @patch("plone.typesense.blob_extraction.extract_text_from_blob")
    def test_extracts_from_blob_fields(
        self, mock_extract, mock_get_fields, mock_schemata
    ):
        from plone.typesense.blob_extraction import extract_blob_texts
        from plone.namedfile.interfaces import INamedBlobFileField

        obj = MagicMock()
        schema = MagicMock()
        mock_schemata.return_value = [schema]

        blob_field = MagicMock()
        blob_field_value = MagicMock()
        blob_field.get.return_value = blob_field_value

        # Make INamedBlobFileField.providedBy return True
        with patch.object(
            INamedBlobFileField, "providedBy", return_value=True
        ):
            mock_get_fields.return_value = {"file": blob_field}
            mock_extract.return_value = "extracted text"

            result = extract_blob_texts(obj)

            self.assertEqual(result, {"file": "extracted text"})
            mock_extract.assert_called_once_with(blob_field_value)

    @patch("plone.typesense.blob_extraction.iterSchemata")
    def test_handles_non_dexterity_objects(self, mock_schemata):
        from plone.typesense.blob_extraction import extract_blob_texts

        mock_schemata.side_effect = Exception("Not a dexterity object")
        obj = MagicMock()

        result = extract_blob_texts(obj)
        self.assertEqual(result, {})


class TestGetSearchableBlobText(unittest.TestCase):
    """Test get_searchable_blob_text."""

    @patch("plone.typesense.blob_extraction.extract_blob_texts")
    def test_combines_texts(self, mock_extract):
        from plone.typesense.blob_extraction import get_searchable_blob_text

        mock_extract.return_value = {
            "file1": "hello world",
            "file2": "foo bar",
        }
        obj = MagicMock()
        result = get_searchable_blob_text(obj)
        self.assertIn("hello world", result)
        self.assertIn("foo bar", result)

    @patch("plone.typesense.blob_extraction.extract_blob_texts")
    def test_empty_when_no_blobs(self, mock_extract):
        from plone.typesense.blob_extraction import get_searchable_blob_text

        mock_extract.return_value = {}
        obj = MagicMock()
        result = get_searchable_blob_text(obj)
        self.assertEqual(result, "")


class TestEnrichWithBlobText(unittest.TestCase):
    """Test the _enrich_with_blob_text method on IndexProcessor."""

    @patch("plone.typesense.queueprocessor.get_searchable_blob_text")
    def test_appends_to_searchable_text(self, mock_get_blob_text):
        from plone.typesense.queueprocessor import IndexProcessor

        mock_get_blob_text.return_value = "blob content here"
        processor = IndexProcessor()
        obj = MagicMock()
        index_data = {"SearchableText": "existing text"}

        processor._enrich_with_blob_text(obj, index_data)

        self.assertEqual(
            index_data["SearchableText"],
            "existing text blob content here",
        )

    @patch("plone.typesense.queueprocessor.get_searchable_blob_text")
    def test_sets_searchable_text_when_empty(self, mock_get_blob_text):
        from plone.typesense.queueprocessor import IndexProcessor

        mock_get_blob_text.return_value = "blob content"
        processor = IndexProcessor()
        obj = MagicMock()
        index_data = {}

        processor._enrich_with_blob_text(obj, index_data)

        self.assertEqual(index_data["SearchableText"], "blob content")

    @patch("plone.typesense.queueprocessor.get_searchable_blob_text")
    def test_no_change_when_no_blob_text(self, mock_get_blob_text):
        from plone.typesense.queueprocessor import IndexProcessor

        mock_get_blob_text.return_value = ""
        processor = IndexProcessor()
        obj = MagicMock()
        index_data = {"SearchableText": "existing text"}

        processor._enrich_with_blob_text(obj, index_data)

        self.assertEqual(index_data["SearchableText"], "existing text")

    @patch("plone.typesense.queueprocessor.get_searchable_blob_text")
    def test_handles_extraction_failure(self, mock_get_blob_text):
        from plone.typesense.queueprocessor import IndexProcessor

        mock_get_blob_text.side_effect = Exception("extraction failed")
        processor = IndexProcessor()
        obj = MagicMock()
        obj.id = "test-obj"
        index_data = {"SearchableText": "existing text"}

        # Should not raise, should log and leave data unchanged
        processor._enrich_with_blob_text(obj, index_data)

        self.assertEqual(index_data["SearchableText"], "existing text")
