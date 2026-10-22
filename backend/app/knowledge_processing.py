"""Bounded extraction and deterministic page-aware overlapping chunks."""
import io
import re
from pypdf import PdfReader, apply_configuration
from .intelligence import IntelligenceError


def extract_pages(content: bytes, file_type: str, max_chars: int = 200_000) -> list[tuple[int | None, str]]:
    try:
        if file_type == 'txt':
            text = content.decode('utf-8-sig')
            if any(ord(c) < 32 and c not in '\n\r\t' for c in text):
                raise ValueError()
            pages = [(None, text)]
        else:
            if not content.startswith(b'%PDF-'):
                raise ValueError()
            with apply_configuration(
                maximum_declared_stream_length=8_000_000,
                zlib_maximum_output_length=8_000_000,
                lzw_maximum_output_length=8_000_000,
                run_length_maximum_output_length=8_000_000,
                array_based_stream_maximum_output_length=8_000_000,
                stream_decoding_work_maximum_length=25_000_000,
                stream_parsing_work_maximum_count=100_000,
            ):
                reader = PdfReader(io.BytesIO(content), strict=True)
                if reader.is_encrypted or len(reader.pages) > 100:
                    raise ValueError()
                pages, total = [], 0
                for number, page in enumerate(reader.pages, 1):
                    text = page.extract_text() or ''
                    total += len(text)
                    if total > max_chars:
                        raise IntelligenceError('extracted_text_limit', 422)
                    pages.append((number, text))
    except IntelligenceError:
        raise
    except Exception:
        # PDF parser exceptions contain paths/content; expose only a stable code.
        raise IntelligenceError('unreadable_document', 422) from None
    if sum(len(text) for _, text in pages) > max_chars:
        raise IntelligenceError('extracted_text_limit', 422)
    pages = [(page, re.sub(r'\s+', ' ', text).strip()) for page, text in pages]
    if not any(text for _, text in pages):
        raise IntelligenceError('empty_document', 422)
    return pages


def split_chunks(pages: list[tuple[int | None, str]], size: int, overlap: int) -> list[dict]:
    if not 100 <= size <= 2000 or not 0 <= overlap < size:
        raise IntelligenceError('invalid_chunk_configuration', 503)
    chunks = []
    for page, text in pages:
        for start in range(0, len(text), size - overlap):
            passage = text[start:start + size].strip()
            if passage:
                chunks.append({'page_number': page, 'chunk_index': len(chunks), 'passage': passage})
            if start + size >= len(text):
                break
    if len(chunks) > 200:
        raise IntelligenceError('document_chunk_limit', 422)
    return chunks
