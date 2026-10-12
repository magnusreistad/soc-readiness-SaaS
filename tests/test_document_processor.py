"""
Zip-bomb guard for uploads: the entry-count and total-size caps must be
checked before any parser that decompresses a ZIP archive runs: python-docx
and the direct ZIP/XML path (Word), openpyxl and xlrd (Excel), and PyMuPDF
(PDF, which opens ZIP content as EPUB/CBZ/XPS regardless of filetype=).
Caps are monkeypatched relative to small real files, so no large files are
generated.
"""

import io
import sys
import types
import zipfile

import docx
import fitz
import openpyxl
import pytest

from app.utils import document_processor as dp

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
TEXT = "Access reviews are performed quarterly"


@pytest.fixture(scope="module")
def docx_bytes() -> bytes:
    # Module-scoped, so it is built before the function-scoped spies below
    # are installed and its own docx.Document() call isn't recorded.
    buf = io.BytesIO()
    d = docx.Document()
    d.add_paragraph(TEXT)
    d.save(buf)
    return buf.getvalue()


def _total_uncompressed(file_bytes: bytes) -> int:
    with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
        return sum(i.file_size for i in zf.infolist())


def _entry_count(file_bytes: bytes) -> int:
    with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
        return len(zf.infolist())


@pytest.fixture
def document_calls(monkeypatch):
    """Records every call to docx.Document while still delegating to it."""
    calls = []
    real = docx.Document

    def spy(*args, **kwargs):
        calls.append(args)
        return real(*args, **kwargs)

    monkeypatch.setattr(docx, "Document", spy)
    return calls


@pytest.fixture
def zip_reads(monkeypatch):
    """Records every member decompressed via ZipFile.read (python-docx and Strategy 2)."""
    reads = []
    real = zipfile.ZipFile.read

    def spy(self, name, *args, **kwargs):
        reads.append(name if isinstance(name, str) else name.filename)
        return real(self, name, *args, **kwargs)

    monkeypatch.setattr(zipfile.ZipFile, "read", spy)
    return reads


def test_docx_under_caps_extracts_normally(monkeypatch, docx_bytes, document_calls):
    data = docx_bytes
    monkeypatch.setattr(dp, "MAX_ZIP_UNCOMPRESSED_BYTES", _total_uncompressed(data))
    monkeypatch.setattr(dp, "MAX_ZIP_ENTRIES", _entry_count(data))

    result = dp.extract_text(data, "policy.docx", DOCX_MIME)

    assert len(document_calls) == 1
    assert result.file_type == "word"
    assert TEXT in result.text
    assert result.error is None


def test_docx_over_total_size_cap_never_reaches_document(monkeypatch, docx_bytes, document_calls, zip_reads):
    data = docx_bytes
    monkeypatch.setattr(dp, "MAX_ZIP_UNCOMPRESSED_BYTES", _total_uncompressed(data) - 1)

    result = dp.extract_text(data, "policy.docx", DOCX_MIME)

    assert document_calls == []
    assert zip_reads == []          # Strategy 2 skipped too
    assert TEXT not in result.text  # only the non-ZIP fallbacks ran


def test_docx_over_entry_count_cap_never_reaches_document(monkeypatch, docx_bytes, document_calls, zip_reads):
    data = docx_bytes
    monkeypatch.setattr(dp, "MAX_ZIP_ENTRIES", _entry_count(data) - 1)

    result = dp.extract_text(data, "policy.docx", DOCX_MIME)

    assert document_calls == []
    assert zip_reads == []
    assert TEXT not in result.text


def test_direct_zip_fallback_still_works_under_caps(monkeypatch):
    # A .docx missing [Content_Types].xml: python-docx rejects it and the
    # direct ZIP/XML path (Strategy 2) recovers the text.
    w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("word/document.xml", f'<w:document xmlns:w="{w}"><w:t>{TEXT}</w:t></w:document>')
    data = buf.getvalue()
    monkeypatch.setattr(dp, "MAX_ZIP_UNCOMPRESSED_BYTES", _total_uncompressed(data))

    result = dp.extract_text(data, "repacked.docx", DOCX_MIME)

    assert TEXT in result.text


# ---------------------------------------------------------------------------
# All ZIP-capable upload paths
# ---------------------------------------------------------------------------

# Data before the archive: still a valid ZIP to zipfile (and so to python-docx
# and openpyxl), but no longer starts with the PK magic bytes.
PREPENDED = b"JUNKJUNK"


@pytest.fixture(scope="module")
def xlsx_bytes() -> bytes:
    buf = io.BytesIO()
    wb = openpyxl.Workbook()
    wb.active["A1"] = TEXT
    wb.save(buf)
    return buf.getvalue()


@pytest.fixture(scope="module")
def pdf_bytes() -> bytes:
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), TEXT)
    return doc.tobytes()


def _spy(monkeypatch, target, name):
    """Replaces target.name with a recorder that still delegates to the original."""
    calls = []
    real = getattr(target, name)

    def recorder(*args, **kwargs):
        calls.append(args)
        return real(*args, **kwargs)

    monkeypatch.setattr(target, name, recorder)
    return calls


@pytest.fixture
def member_opens(monkeypatch):
    """Every ZIP member decompressed by any Python parser (ZipFile.read goes through open)."""
    return _spy(monkeypatch, zipfile.ZipFile, "open")


def _cap_below(monkeypatch, file_bytes: bytes) -> None:
    monkeypatch.setattr(dp, "MAX_ZIP_UNCOMPRESSED_BYTES", _total_uncompressed(file_bytes) - 1)


@pytest.mark.parametrize("prefix", [b"", PREPENDED], ids=["plain", "prepended"])
def test_docx_over_cap_never_reaches_document_even_without_pk_prefix(
    monkeypatch, docx_bytes, document_calls, member_opens, prefix,
):
    data = prefix + docx_bytes
    _cap_below(monkeypatch, docx_bytes)

    result = dp.extract_text(data, "policy.docx", DOCX_MIME)

    assert document_calls == []
    assert member_opens == []
    assert TEXT not in result.text


@pytest.mark.parametrize("prefix", [b"", PREPENDED], ids=["plain", "prepended"])
def test_xlsx_over_cap_never_reaches_openpyxl(monkeypatch, xlsx_bytes, member_opens, prefix):
    data = prefix + xlsx_bytes
    _cap_below(monkeypatch, xlsx_bytes)
    load_calls = _spy(monkeypatch, openpyxl, "load_workbook")

    result = dp.extract_text(data, "reviews.xlsx", XLSX_MIME)

    assert load_calls == []
    assert member_opens == []
    assert TEXT not in result.text


def test_xlsx_under_cap_extracts_normally(monkeypatch, xlsx_bytes):
    monkeypatch.setattr(dp, "MAX_ZIP_UNCOMPRESSED_BYTES", _total_uncompressed(xlsx_bytes))
    load_calls = _spy(monkeypatch, openpyxl, "load_workbook")

    result = dp.extract_text(xlsx_bytes, "reviews.xlsx", XLSX_MIME)

    assert len(load_calls) == 1
    assert result.file_type == "excel"
    assert TEXT in result.text


def test_xlsx_over_cap_never_reaches_xlrd(monkeypatch, xlsx_bytes):
    # xlrd isn't a dependency; a stand-in proves the fallback is skipped too
    # (xlrd < 2.0 opens .xlsx archives itself).
    xlrd_calls = []
    fake_xlrd = types.ModuleType("xlrd")
    fake_xlrd.open_workbook = lambda *a, **k: xlrd_calls.append(k) or pytest.fail("xlrd reached")
    monkeypatch.setitem(sys.modules, "xlrd", fake_xlrd)
    # Make openpyxl fail if reached, so without the guard xlrd would run next
    monkeypatch.setattr(openpyxl, "load_workbook", lambda *a, **k: (_ for _ in ()).throw(ValueError("bad")))
    _cap_below(monkeypatch, xlsx_bytes)

    dp.extract_text(xlsx_bytes, "legacy.xls", "application/vnd.ms-excel")

    assert xlrd_calls == []


def test_zip_sent_as_pdf_over_cap_never_reaches_pymupdf(monkeypatch, docx_bytes):
    _cap_below(monkeypatch, docx_bytes)
    open_calls = _spy(monkeypatch, fitz, "open")

    result = dp.extract_text(docx_bytes, "report.pdf", "application/pdf")

    assert open_calls == []
    assert result.text == ""
    assert result.error


def test_real_pdf_is_unaffected_by_zip_caps(monkeypatch, pdf_bytes):
    monkeypatch.setattr(dp, "MAX_ZIP_UNCOMPRESSED_BYTES", 0)
    monkeypatch.setattr(dp, "MAX_ZIP_ENTRIES", 0)

    result = dp.extract_text(pdf_bytes, "report.pdf", "application/pdf")

    assert result.error is None
    assert TEXT in result.text


@pytest.mark.parametrize("filename,mime", [
    ("deck.pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
    ("bundle.zip", "application/zip"),
])
def test_pptx_and_zip_mime_types_are_rejected_unparsed(docx_bytes, member_opens, filename, mime):
    result = dp.extract_text(docx_bytes, filename, mime)

    assert result.error and result.error.startswith("Unsupported file type")
    assert member_opens == []


@pytest.mark.parametrize("filename", ["bundle.zip", "deck.pptx"])
def test_octet_stream_zip_is_sniffed_into_guarded_path(monkeypatch, docx_bytes, member_opens, filename):
    # _resolve_mime sniffs PK + "word/" and routes these into _extract_word,
    # so they're covered by the same guard rather than being a separate path.
    _cap_below(monkeypatch, docx_bytes)

    dp.extract_text(docx_bytes, filename, "application/octet-stream")

    assert member_opens == []
