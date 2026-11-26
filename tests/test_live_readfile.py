import io

import pytest

from cuad_ai.live import readfile
from cuad_ai.live.store import RejectedUpload

CLAUSE = "This Agreement shall be governed by the laws of the State of Delaware. " * 3


def text_pdf(text):
    """A tiny valid PDF with one page of real text, built by hand so the tests need no PDF-writing library."""
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
               b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
               b"/Resources << /Font << /F1 5 0 R >> >> >>",
               b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, offsets = b"%PDF-1.4\n", []
    for number, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    start = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    return out + b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % (len(objects) + 1, start)


def blank_pdf(pages=1, password=None):
    from pypdf import PdfWriter

    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(612, 792)
    if password:
        writer.encrypt(password, algorithm="AES-128")
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def test_text_is_read_as_utf8_with_a_fallback_for_old_windows_files():
    assert readfile.read_upload("a.txt", "Café agreement".encode("utf-8")) == "Café agreement"
    assert readfile.read_upload("a.TXT", "Café agreement".encode("cp1252")) == "Café agreement"
    assert readfile.read_upload("a.txt", b"\xef\xbb\xbfhello") == "hello"  # a byte-order mark is dropped


@pytest.mark.parametrize("name, word", [
    ("deal.xlsx", "Spreadsheets"), ("deal.CSV", "Spreadsheets"), ("deal.doc", "Old Word"),
    ("scan.png", "Images"), ("deal.rtf", "not supported"), ("noextension", "not supported"), ("", "not supported")])
def test_other_file_types_are_refused_with_a_message_a_person_can_act_on(name, word):
    with pytest.raises(RejectedUpload, match=word):
        readfile.read_upload(name, b"anything")


def test_a_file_over_the_size_limit_is_refused_before_it_is_read(monkeypatch):
    monkeypatch.setenv("LIVE_MAX_FILE_MB", "1")
    with pytest.raises(RejectedUpload, match="limit is 1 MB"):
        readfile.read_upload("big.txt", b"x" * (1024 * 1024 + 1))


def test_a_pdf_with_text_is_read():
    text = readfile.read_upload("contract.pdf", text_pdf(CLAUSE))
    assert "governed by the laws of the State of Delaware" in text
    assert readfile.read_upload("CONTRACT.PDF", text_pdf(CLAUSE))  # the extension is not case sensitive


def test_a_scanned_pdf_is_refused_because_there_is_no_text_to_read():
    with pytest.raises(RejectedUpload, match="no selectable text"):
        readfile.read_upload("scan.pdf", blank_pdf())


def test_a_password_protected_or_broken_pdf_is_refused_politely():
    with pytest.raises(RejectedUpload, match="password"):
        readfile.read_upload("locked.pdf", blank_pdf(password="secret"))
    with pytest.raises(RejectedUpload, match="could not be read"):
        readfile.read_upload("broken.pdf", b"this is not a pdf")


def test_a_pdf_with_too_many_pages_is_refused(monkeypatch):
    monkeypatch.setenv("LIVE_MAX_PAGES", "2")
    with pytest.raises(RejectedUpload, match="3 pages; the limit is 2"):
        readfile.read_upload("long.pdf", blank_pdf(pages=3))


def word_file(build):
    from docx import Document

    document = Document()
    build(document)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def test_a_word_file_gives_its_paragraphs_and_tables_in_order():
    def build(document):
        document.add_paragraph("SERVICES AGREEMENT")
        table = document.add_table(rows=1, cols=2)
        table.rows[0].cells[0].text = "Governing law"
        table.rows[0].cells[1].text = "Delaware"
        document.add_paragraph("The fees are payable within thirty days.")

    text = readfile.read_upload("deal.docx", word_file(build))
    assert text.split("\n")[:3] == ["SERVICES AGREEMENT", "Governing law | Delaware", "The fees are payable within thirty days."]


def test_a_corrupt_word_file_is_refused_politely():
    with pytest.raises(RejectedUpload, match="could not be read"):
        readfile.read_upload("deal.docx", b"not a zip file")
