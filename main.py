
from playwright.sync_api import sync_playwright
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import os
import json
import mimetypes

# === 1. Login configuration ===
LOGIN_URL = "http://103.230.126.114/eportal/public/signin.aspx"

USERNAME = os.environ["LOGIN_USERNAME"]
PASSWORD = os.environ["LOGIN_PASSWORD"]

DOWNLOAD_DIR = "."


# === 2. Download Excel report ===
def download_excel():
    print("Starting browser automation...")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )

        try:
            page = browser.new_page()

            page.goto(LOGIN_URL)
            page.fill(
                'input[name="ctl00$MainContent$txtEmpID"]',
                USERNAME
            )
            page.fill(
                'input[name="ctl00$MainContent$txtPassword"]',
                PASSWORD
            )
            page.click(
                'input[name="ctl00$MainContent$btnSignIn"]'
            )
            page.wait_for_load_state("networkidle")

            page.goto(
                "http://103.230.126.114/eportal/admin/processor/lvhistoryepe.aspx"
            )
            page.wait_for_load_state("networkidle")

            page.fill(
                'input[name="ctl00$MainContent$txtFromDate"]',
                "01/01/2026"
            )
            page.fill(
                'input[name="ctl00$MainContent$txtToDate"]',
                "31/12/2026"
            )
            page.click(
                'input[name="ctl00$MainContent$btnSearch"]'
            )

            print("Waiting for results...")
            page.wait_for_timeout(7000)
            page.evaluate(
                "window.scrollTo(0, document.body.scrollHeight)"
            )

            page.wait_for_selector(
                "input[value='Save to Excel']",
                timeout=60000
            )

            print("Downloading Excel report...")

            with page.expect_download() as download_info:
                page.click("input[value='Save to Excel']")

            download = download_info.value
            output_path = os.path.join(
                DOWNLOAD_DIR,
                download.suggested_filename
            )

            download.save_as(output_path)

            print(f"Download completed: {output_path}")
            return output_path

        finally:
            browser.close()


# === 3. Upload to Google Drive ===
def upload_to_drive(file_path):
    print("Uploading to Google Drive...")

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    service_account_info = json.loads(
        os.environ["GOOGLE_SERVICE_ACCOUNT"]
    )

    creds = service_account.Credentials.from_service_account_info(
        service_account_info,
        scopes=["https://www.googleapis.com/auth/drive.file"]
    )

    drive_service = build(
        "drive",
        "v3",
        credentials=creds
    )

    folder_id = os.environ["GOOGLE_DRIVE_FOLDER_ID"]

    file_metadata = {
        "name": os.path.basename(file_path),
        "parents": [folder_id]
    }

    mime_type = (
        mimetypes.guess_type(file_path)[0]
        or "application/octet-stream"
    )

    media = MediaFileUpload(
        file_path,
        mimetype=mime_type
    )

    uploaded_file = drive_service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id, name, webViewLink",
        supportsAllDrives=True
    ).execute()

    print("Google Drive upload completed!")
    print(f"File name: {uploaded_file.get('name')}")
    print(f"File ID: {uploaded_file.get('id')}")
    print(f"File link: {uploaded_file.get('webViewLink')}")


# === 4. Main execution ===
if __name__ == "__main__":
    try:
        excel_path = download_excel()
        upload_to_drive(excel_path)
        print("Automation completed successfully!")

    except Exception as e:
        print(f"Workflow failed: {e}")
        raise
