import io
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

async def schedule_convert(credentials_path: str, document_id: str) -> bytes:
    creds = service_account.Credentials.from_service_account_file(
        credentials_path,
        scopes=['https://www.googleapis.com/auth/drive']
    )
    
    service = build('drive', 'v3', credentials=creds)
    request = service.files().export_media(
        fileId=document_id,
        mimeType='application/pdf'
    )
    
    pdf_buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(pdf_buffer, request)

    done = False
    while not done:
        _, done = downloader.next_chunk()
    
    return pdf_buffer.getvalue()
