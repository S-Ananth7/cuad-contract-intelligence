"""Turn an uploaded file into plain text. Only the text is kept; the original file is never stored.

Supported: text, PDF with selectable text, and Word (.docx). Everything else is refused with a message a person can
act on. A scanned PDF has no text to read (that needs OCR, which is not included), so it is refused too.
"""
import io
import zipfile
from pathlib import PurePath

from cuad_ai.live import config
from cuad_ai.live.store import RejectedUpload

SUPPORTED = ("txt", "pdf", "docx")
MIN_PDF_CHARS = 100  # fewer characters than this in a whole PDF means a scan or a page of images
MAX_UNPACKED = 100 * 1024 * 1024  # a .docx that unpacks to more than this is refused (a zip bomb)

REFUSALS = {
    **dict.fromkeys(("xlsx", "xlsm", "xls", "csv"),
                    "Spreadsheets are not supported. Please upload the contract as a PDF, Word (.docx) or text file."),
    "doc": "Old Word (.doc) files are not supported. Please save the contract as .docx or PDF and upload that.",
    **dict.fromkeys(("png", "jpg", "jpeg", "tif", "tiff", "gif"),
                    "Images are not supported. Please upload a PDF with selectable text, a Word file or a text file."),
}
OTHER = "This file type is not supported. Please upload a PDF, Word (.docx) or text file."


def read_upload(filename, data):
    """The text of an uploaded file. Raises RejectedUpload with a reason that is safe to show."""
    extension = PurePath(filename or "").suffix.lower().lstrip(".")
    if extension not in SUPPORTED:
        raise RejectedUpload(REFUSALS.get(extension, OTHER))
    limit = config.max_file_mb() * 1024 * 1024
    if len(data) > limit:
        raise RejectedUpload(f"The file is {len(data) / 1e6:.1f} MB; the limit is {config.max_file_mb()} MB.")
    return {"txt": _text, "pdf": _pdf, "docx": _docx}[extension](data)


def _text(data):
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace")


def _pdf(data):
    try:
        from pypdf import PdfReader
    except ImportError:
        raise RejectedUpload("This server cannot read PDF files.") from None
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted and not reader.decrypt(""):
            raise RejectedUpload("This PDF is password protected. Please remove the password and upload it again.")
        pages = len(reader.pages)
        if pages > config.max_pages():
            raise RejectedUpload(f"This PDF has {pages} pages; the limit is {config.max_pages()}.")
        text = "\n\n".join((page.extract_text() or "") for page in reader.pages)
    except RejectedUpload:
        raise
    except Exception:
        raise RejectedUpload("This PDF could not be read. Please save it again as a PDF or upload a Word file.") from None
    if len(text.strip()) < MIN_PDF_CHARS:
        raise RejectedUpload("This PDF has no selectable text, so it is probably a scan. "
                             "Please upload a text version or a Word file.")
    return text


def _docx(data):
    try:
        from docx import Document
        from docx.table import Table
        from docx.text.paragraph import Paragraph
    except ImportError:
        raise RejectedUpload("This server cannot read Word files.") from None
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if sum(item.file_size for item in archive.infolist()) > MAX_UNPACKED:
                raise RejectedUpload("This Word file is too large once unpacked.")
        document = Document(io.BytesIO(data))
        lines = []
        for child in document.element.body.iterchildren():  # paragraphs and tables, in the order they appear
            if child.tag.endswith("}p"):
                lines.append(Paragraph(child, document).text)
            elif child.tag.endswith("}tbl"):
                for row in Table(child, document).rows:
                    cells, seen = [], set()
                    for cell in row.cells:  # a merged cell appears once per column it spans
                        if id(cell._tc) not in seen:
                            seen.add(id(cell._tc))
                            cells.append(cell.text.strip())
                    lines.append(" | ".join(c for c in cells if c))
        return "\n".join(lines)
    except RejectedUpload:
        raise
    except Exception:
        raise RejectedUpload("This Word file could not be read. Please save it again as .docx or PDF.") from None
