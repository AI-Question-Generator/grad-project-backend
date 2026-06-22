import hashlib

from django.conf import settings
from pypdf import PdfReader


MAX_SOURCE_FILE_SIZE = getattr(settings, 'MAX_SOURCE_FILE_SIZE', 20 * 1024 * 1024)
ALLOWED_SOURCE_FILE_TYPES = {'application/pdf'}


def compute_file_hash(uploaded_file):
    hasher = hashlib.sha256()
    for chunk in uploaded_file.chunks():
        hasher.update(chunk)
    uploaded_file.seek(0)
    return hasher.hexdigest()


def get_pdf_page_count(uploaded_file):
    try:
        reader = PdfReader(uploaded_file)
        uploaded_file.seek(0)
        return len(reader.pages)
    except Exception:
        uploaded_file.seek(0)
        return None


def validate_pdf_upload(uploaded_file):
    if uploaded_file.size > MAX_SOURCE_FILE_SIZE:
        raise ValueError(
            f'File size exceeds maximum allowed size of {MAX_SOURCE_FILE_SIZE // (1024 * 1024)} MB.'
        )

    content_type = getattr(uploaded_file, 'content_type', '') or ''
    if content_type and content_type not in ALLOWED_SOURCE_FILE_TYPES:
        raise ValueError('Only PDF files are allowed.')

    if not uploaded_file.name.lower().endswith('.pdf'):
        raise ValueError('Only PDF files are allowed.')

    page_count = get_pdf_page_count(uploaded_file)
    if page_count is not None and page_count < 1:
        raise ValueError('The uploaded PDF has no pages.')

    return page_count


def build_file_url(request, file_field):
    if not file_field:
        return ''
    return request.build_absolute_uri(file_field.url)
