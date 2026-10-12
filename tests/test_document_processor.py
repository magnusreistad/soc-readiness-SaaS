"""
Zip-bomb guard for uploads: the entry-count and total-size caps must be
checked before any parser that decompresses a ZIP archive runs: python-docx
and the direct ZIP/XML path (Word), openpyxl and xlrd (Excel), and PyMuPDF
(PDF, which opens ZIP content as EPUB/CBZ/XPS regardless of filetype=).
Caps are monkeypatched relative to small real files, so no large files are
generated.
"""

import io
import struct
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


# ---------------------------------------------------------------------------
# .xlsx sheet aliasing: openpyxl decompresses a sheet's part once per sheet
# that references it (inside load_workbook and again on iteration)
# ---------------------------------------------------------------------------

WS_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"


def _workbook_with_sheet_refs(targets: list[str]) -> bytes:
    """
    Builds a .xlsx with one <sheet> per entry in targets, each pointing via
    its own relationship at that target (relative to xl/). Only
    xl/worksheets/sheet1.xml exists, so repeated targets alias one part.
    """
    buf = io.BytesIO()
    wb = openpyxl.Workbook()
    wb.active["A1"] = TEXT
    wb.save(buf)
    with zipfile.ZipFile(io.BytesIO(buf.getvalue())) as src:
        files = {n: src.read(n) for n in src.namelist()}

    r_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    sheets = "".join(
        f'<sheet name="S{i}" sheetId="{i + 1}" r:id="rIdAlias{i}"/>' for i in range(len(targets))
    )
    wbx = files["xl/workbook.xml"].decode()
    start, end = wbx.index("<sheets>"), wbx.index("</sheets>") + len("</sheets>")
    files["xl/workbook.xml"] = (wbx[:start] + f'<sheets xmlns:r="{r_ns}">{sheets}</sheets>' + wbx[end:]).encode()

    rels = "".join(
        f'<Relationship Id="rIdAlias{i}" Type="{WS_REL_TYPE}" Target="{t}"/>' for i, t in enumerate(targets)
    )
    rx = files["xl/_rels/workbook.xml.rels"].decode()
    files["xl/_rels/workbook.xml.rels"] = rx.replace("</Relationships>", rels + "</Relationships>").encode()

    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return out.getvalue()


def _multi_sheet_xlsx(sheet_texts: list[str]) -> bytes:
    buf = io.BytesIO()
    wb = openpyxl.Workbook()
    wb.active.title = "Sheet0"
    wb.active["A1"] = sheet_texts[0]
    for i, text in enumerate(sheet_texts[1:], start=1):
        wb.create_sheet(f"Sheet{i}")["A1"] = text
    wb.save(buf)
    return buf.getvalue()


@pytest.fixture(scope="module")
def aliasing_xlsx() -> bytes:
    return _workbook_with_sheet_refs(["worksheets/sheet1.xml"] * 50)


@pytest.fixture
def worksheet_opens(monkeypatch):
    """Sheet parts decompressed (ZipFile.read goes through open)."""
    opens = []
    real = zipfile.ZipFile.open

    def spy(self, name, *args, **kwargs):
        member = name if isinstance(name, str) else name.filename
        if "/worksheets/" in f"/{member}":
            opens.append(member)
        return real(self, name, *args, **kwargs)

    monkeypatch.setattr(zipfile.ZipFile, "open", spy)
    return opens


def test_aliasing_workbook_never_reaches_openpyxl(monkeypatch, aliasing_xlsx, worksheet_opens):
    load_calls = _spy(monkeypatch, openpyxl, "load_workbook")

    dp.extract_text(aliasing_xlsx, "reviews.xlsx", XLSX_MIME)

    assert load_calls == []
    assert worksheet_opens == []


def test_aliasing_workbook_amplifies_without_precheck(monkeypatch, aliasing_xlsx, worksheet_opens):
    # Disables the pre-check to show what it prevents: one 50-sheet workbook
    # decompresses its single sheet part twice per sheet.
    monkeypatch.setattr(dp, "_xlsx_sheets_allowed", lambda *a: True)
    load_calls = _spy(monkeypatch, openpyxl, "load_workbook")

    dp.extract_text(aliasing_xlsx, "reviews.xlsx", XLSX_MIME)

    assert len(load_calls) == 1
    assert len(worksheet_opens) >= 100


def test_aliases_spelled_differently_are_still_caught(monkeypatch):
    # Relative, absolute and ../ spellings all normalise to xl/worksheets/sheet1.xml
    data = _workbook_with_sheet_refs([
        "worksheets/sheet1.xml",
        "/xl/worksheets/sheet1.xml",
        "worksheets/../worksheets/sheet1.xml",
    ])
    load_calls = _spy(monkeypatch, openpyxl, "load_workbook")

    dp.extract_text(data, "reviews.xlsx", XLSX_MIME)

    assert load_calls == []


def test_normal_multi_sheet_workbook_extracts_every_sheet(monkeypatch):
    texts = ["Q1 access review", "Q2 access review", "Q3 access review"]
    data = _multi_sheet_xlsx(texts)
    load_calls = _spy(monkeypatch, openpyxl, "load_workbook")
    # Block xlrd so an "excel" result can only have come from openpyxl
    monkeypatch.setitem(sys.modules, "xlrd", None)

    result = dp.extract_text(data, "reviews.xlsx", XLSX_MIME)

    assert len(load_calls) == 1
    # Went through openpyxl, not a fallback: only the spreadsheet parsers emit
    # sheet markers. file_type alone isn't enough, since the final "could not
    # extract" result is also "excel".
    assert result.error is None
    assert result.file_type == "excel"
    assert all(f"[Sheet: Sheet{i}]" in result.text for i in range(3))
    assert result.page_count == 3
    assert all(t in result.text for t in texts)


def test_workbook_over_sheet_cap_goes_to_fallback(monkeypatch):
    data = _multi_sheet_xlsx(["a", "b", "c"])
    monkeypatch.setattr(dp, "MAX_XLSX_SHEETS", 2)
    load_calls = _spy(monkeypatch, openpyxl, "load_workbook")

    result = dp.extract_text(data, "reviews.xlsx", XLSX_MIME)

    assert load_calls == []
    assert result.page_count != 3


def test_sheet_loop_stops_once_text_passes_cap(monkeypatch):
    data = _multi_sheet_xlsx(["x" * 100, "second sheet", "third sheet"])
    monkeypatch.setattr(dp, "MAX_EXTRACTED_CHARS", 50)

    result = dp.extract_text(data, "reviews.xlsx", XLSX_MIME)

    assert result.was_truncated
    assert result.page_count == 1          # later sheets never iterated
    assert "second sheet" not in result.text


# ---------------------------------------------------------------------------
# Files zipfile.is_zipfile accepts but zipfile.ZipFile() can't open
# ---------------------------------------------------------------------------

OLE2_MAGIC = bytes.fromhex("d0cf11e0a1b11ae1")
EPUB_CONTAINER = (
    '<?xml version="1.0"?><container version="1.0" '
    'xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles>'
    '<rootfile full-path="c.opf" media-type="application/oebps-package+xml"/>'
    "</rootfiles></container>"
)
EPUB_OPF = (
    '<?xml version="1.0"?><package xmlns="http://www.idpf.org/2007/opf" version="2.0">'
    '<manifest><item id="a" href="a.xhtml" media-type="application/xhtml+xml"/></manifest>'
    '<spine><itemref idref="a"/></spine></package>'
)
EPUB_TEXT = "EPUBCHAPTERTEXT"


def _stray_eocd() -> bytes:
    """
    An end-of-central-directory record whose central directory "starts" at
    offset 0. is_zipfile accepts the file; ZipFile() fails on the bad
    central-directory magic there.
    """
    return b"PK\x05\x06" + struct.pack("<HHHHIIH", 0, 0, 1, 1, 46, 0, 0)


def _assert_is_zipfile_but_unreadable(data: bytes) -> None:
    assert zipfile.is_zipfile(io.BytesIO(data))
    with pytest.raises(zipfile.BadZipFile):
        zipfile.ZipFile(io.BytesIO(data))


def _epub(extra_stored_entry: bytes | None = None) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        if extra_stored_entry is not None:
            zf.writestr("note.txt", extra_stored_entry, compress_type=zipfile.ZIP_STORED)
        zf.writestr("META-INF/container.xml", EPUB_CONTAINER, compress_type=zipfile.ZIP_DEFLATED)
        zf.writestr("c.opf", EPUB_OPF, compress_type=zipfile.ZIP_DEFLATED)
        zf.writestr(
            "a.xhtml",
            f'<html xmlns="http://www.w3.org/1999/xhtml"><body><p>{EPUB_TEXT}</p></body></html>',
            compress_type=zipfile.ZIP_DEFLATED,
        )
    return buf.getvalue()


def test_pdf_with_stray_eocd_extracts_normally(monkeypatch, pdf_bytes):
    data = pdf_bytes + _stray_eocd()
    _assert_is_zipfile_but_unreadable(data)
    open_calls = _spy(monkeypatch, fitz, "open")

    result = dp.extract_text(data, "report.pdf", "application/pdf")

    assert len(open_calls) == 1
    assert result.error is None
    assert TEXT in result.text


def test_legacy_xls_with_stray_eocd_reaches_xlrd(monkeypatch):
    data = OLE2_MAGIC + b"\x00" * 504 + _stray_eocd()
    _assert_is_zipfile_but_unreadable(data)
    xlrd_calls = []
    sheet = types.SimpleNamespace(name="Legacy", nrows=1, ncols=1, cell_value=lambda r, c: TEXT)
    fake_xlrd = types.ModuleType("xlrd")
    fake_xlrd.open_workbook = lambda **kw: xlrd_calls.append(kw) or types.SimpleNamespace(
        sheets=lambda: [sheet], nsheets=1,
    )
    monkeypatch.setitem(sys.modules, "xlrd", fake_xlrd)

    result = dp.extract_text(data, "legacy.xls", "application/vnd.ms-excel")

    assert len(xlrd_calls) == 1
    assert result.error is None
    assert "[Sheet: Legacy]" in result.text and TEXT in result.text


def test_unreadable_zip_without_pdf_header_never_reaches_pymupdf(monkeypatch):
    # No %PDF- header, so MuPDF would sniff it with its own ZIP reader
    data = b"NOTAPDF" + b"\x00" * 64 + _stray_eocd()
    _assert_is_zipfile_but_unreadable(data)
    open_calls = _spy(monkeypatch, fitz, "open")

    result = dp.extract_text(data, "report.pdf", "application/pdf")

    assert open_calls == []
    assert result.error


@pytest.mark.parametrize("data_fn", [
    lambda: b"%PDF-1.4\n" + _epub(),                   # header before the archive
    lambda: _epub(extra_stored_entry=b"%PDF-1.4"),     # header inside a stored entry
    lambda: b"J" * 1000 + b"%PDF-1.4\n" + _epub(),     # header near the end of the window
], ids=["prefix", "stored-entry", "offset-1000"])
def test_zip_with_pdf_header_is_never_opened_as_epub(monkeypatch, data_fn):
    # These skip the ZIP check (even over the caps), relying on MuPDF always
    # choosing its PDF parser when %PDF- is in the first 1024 bytes. Pins that
    # MuPDF behaviour so an upgrade that changes it fails here.
    data = data_fn()
    assert b"%PDF-" in data[:1024] and zipfile.is_zipfile(io.BytesIO(data))
    monkeypatch.setattr(dp, "MAX_ZIP_UNCOMPRESSED_BYTES", 0)

    result = dp.extract_text(data, "report.pdf", "application/pdf")

    assert EPUB_TEXT not in result.text
    with pytest.raises(Exception):
        fitz.open(stream=data, filetype="pdf")     # PDF parser chosen, and fails


def test_epub_without_pdf_header_is_sniffed_by_mupdf(monkeypatch):
    # Why the ZIP check stays on the PDF path: filetype="pdf" doesn't force
    # the PDF parser, MuPDF opens the EPUB. Over the caps, it's never reached.
    data = _epub()
    assert fitz.open(stream=data, filetype="pdf").metadata["format"] == "EPUB"
    _cap_below(monkeypatch, data)
    open_calls = _spy(monkeypatch, fitz, "open")

    result = dp.extract_text(data, "report.pdf", "application/pdf")

    assert open_calls == []
    assert EPUB_TEXT not in result.text
