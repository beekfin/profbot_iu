import io
from typing import List

import pypdfium2 as pdfium
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload


async def schedule_convert(credentials_path: str, document_id: str) -> List[bytes]:
    """Download Google Doc as PDF and convert each page to PNG bytes."""
    pdf_bytes = _download_pdf(credentials_path, document_id)
    return _pdf_to_png(pdf_bytes)


def _download_pdf(credentials_path: str, document_id: str) -> bytes:
    creds = service_account.Credentials.from_service_account_file(
        credentials_path,
        scopes=["https://www.googleapis.com/auth/drive"],
    )

    service = build("drive", "v3", credentials=creds)
    request = service.files().export_media(
        fileId=document_id,
        mimeType="application/pdf",
    )

    pdf_buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(pdf_buffer, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()

    return pdf_buffer.getvalue()


def _pdf_to_png(pdf_bytes: bytes) -> List[bytes]:
    """Render each PDF page to PNG using pdfium."""
    document = pdfium.PdfDocument(pdf_bytes)
    images: List[bytes] = []

    for page_index in range(len(document)):
        page = document.get_page(page_index)
        bitmap = page.render(scale=2)
        pil_image = bitmap.to_pil()
        buffer = io.BytesIO()
        pil_image.save(buffer, format="PNG")
        images.append(buffer.getvalue())
        buffer.close()
        page.close()

    document.close()
    return images
