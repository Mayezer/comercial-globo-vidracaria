from textwrap import wrap


def _pdf_text(value):
    encoded = str(value).encode('cp1252', errors='replace')
    return encoded.replace(b'\\', b'\\\\').replace(b'(', b'\\(').replace(b')', b'\\)')


def build_text_pdf(title, lines):
    """Build a compact A4 PDF without requiring a system PDF dependency."""
    wrapped_lines = []
    for line in lines:
        text = str(line)
        wrapped_lines.extend(wrap(text, width=88, replace_whitespace=False) or [''])

    pages = [wrapped_lines[index:index + 48] for index in range(0, len(wrapped_lines), 48)] or [[]]
    objects = {
        1: b'<< /Type /Catalog /Pages 2 0 R >>',
        3: b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>',
        4: b'<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>',
    }
    page_ids = []

    for page_index, page_lines in enumerate(pages):
        page_id = 5 + page_index * 2
        stream_id = page_id + 1
        page_ids.append(page_id)
        content = [
            b'BT',
            b'/F1 16 Tf',
            b'50 795 Td',
            b'(' + _pdf_text(title) + b') Tj',
            b'/F2 9 Tf',
            b'0 -26 Td',
            b'14 TL',
        ]
        for line in page_lines:
            content.append(b'(' + _pdf_text(line) + b') Tj')
            content.append(b'T*')
        content.append(b'ET')
        content.extend(
            (
                b'BT',
                b'/F1 9 Tf',
                b'470 28 Td',
                b'(' + _pdf_text(f'Página {page_index + 1} de {len(pages)}') + b') Tj',
                b'ET',
            )
        )
        stream = b'\n'.join(content)
        objects[page_id] = (
            f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] '
            f'/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents {stream_id} 0 R >>'
        ).encode('ascii')
        objects[stream_id] = (
            f'<< /Length {len(stream)} >>\nstream\n'.encode('ascii')
            + stream
            + b'\nendstream'
        )

    kids = ' '.join(f'{page_id} 0 R' for page_id in page_ids)
    objects[2] = f'<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>'.encode('ascii')

    max_object_id = max(objects)
    document = bytearray(b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n')
    offsets = [0] * (max_object_id + 1)
    for object_id in range(1, max_object_id + 1):
        offsets[object_id] = len(document)
        document.extend(f'{object_id} 0 obj\n'.encode('ascii'))
        document.extend(objects[object_id])
        document.extend(b'\nendobj\n')

    xref_offset = len(document)
    document.extend(f'xref\n0 {max_object_id + 1}\n'.encode('ascii'))
    document.extend(b'0000000000 65535 f \n')
    for offset in offsets[1:]:
        document.extend(f'{offset:010d} 00000 n \n'.encode('ascii'))
    document.extend(
        (
            f'trailer\n<< /Size {max_object_id + 1} /Root 1 0 R >>\n'
            f'startxref\n{xref_offset}\n%%EOF\n'
        ).encode('ascii')
    )
    return bytes(document)
