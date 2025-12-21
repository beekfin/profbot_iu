import io
from typing import List

import aiohttp
import pypdfium2 as pdfium
from google.auth.transport.requests import Request
from google.oauth2 import service_account

from app.logger import logger

DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.readonly"
METADATA_URL = "https://www.googleapis.com/drive/v3/files/{file_id}?fields=mimeType"
EXPORT_URL = "https://www.googleapis.com/drive/v3/files/{file_id}/export?mimeType=application/pdf"
DOWNLOAD_URL = "https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"


async def schedule_convert(credentials_path: str, document_id: str) -> List[bytes]:
    pdf_bytes = await _download_pdf(credentials_path, document_id)
    return _pdf_to_png(pdf_bytes)


async def _download_pdf(credentials_path: str, document_id: str) -> bytes:
    creds = service_account.Credentials.from_service_account_file(
        credentials_path,
        scopes=[DRIVE_SCOPE],
    )
    creds.refresh(Request())
    headers = {"Authorization": f"Bearer {creds.token}"}

    async with aiohttp.ClientSession() as session:
        mime_type = await _get_mime_type(session, headers, document_id)
        if mime_type.startswith("application/vnd.google-apps."):
            return await _export_google_doc(session, headers, document_id)
        if mime_type == "application/pdf":
            return await _download_existing_pdf(session, headers, document_id)

        message = (
            "Drive file must be a Google Doc or PDF; received mimeType=%s" % mime_type
        )
        logger.error(message)
        raise ValueError(message)


async def _get_mime_type(
    session: aiohttp.ClientSession, headers: dict, document_id: str
) -> str:
    url = METADATA_URL.format(file_id=document_id)
    async with session.get(url, headers=headers) as response:
        if response.status >= 400:
            await _log_drive_error(response)
            response.raise_for_status()
        data = await response.json()
        mime_type = data.get("mimeType")
        if not mime_type:
            raise ValueError("Drive file metadata does not include mimeType")
        return mime_type


async def _export_google_doc(
    session: aiohttp.ClientSession, headers: dict, document_id: str
) -> bytes:
    url = EXPORT_URL.format(file_id=document_id)
    async with session.get(url, headers=headers) as response:
        if response.status >= 400:
            await _log_drive_error(response)
            response.raise_for_status()
        return await response.read()


async def _download_existing_pdf(
    session: aiohttp.ClientSession, headers: dict, document_id: str
) -> bytes:
    url = DOWNLOAD_URL.format(file_id=document_id)
    async with session.get(url, headers=headers) as response:
        if response.status >= 400:
            await _log_drive_error(response)
            response.raise_for_status()
        return await response.read()


async def _log_drive_error(response: aiohttp.ClientResponse) -> None:
    error_text = await response.text()
    logger.error(
        "Drive request failed: status=%s body=%s",
        response.status,
        error_text.strip(),
    )


def _pdf_to_png(pdf_bytes: bytes) -> List[bytes]:
    """Рендерим каждую страницу PDF в PNG с помощью pdfium."""
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
