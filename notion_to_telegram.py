import requests
import json
import os
from dotenv import load_dotenv
from datetime import datetime
import logging

# Konfigurasi logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.debug("Starting script at " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

# Muat variabel lingkungan dari file .env
load_dotenv()

NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
NOTION_API_KEY = os.getenv("NOTION_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SENT_IDS_FILE = "id_sent.json"

def get_notion_data():
    url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }
    try:
        response = requests.post(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching Notion data: {e}")
        return None

def send_to_telegram(chat_id, message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        logger.info(f"Message sent to Telegram ID {chat_id}")
        logger.debug(f"Telegram response: {response.text}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error sending message to {chat_id}: {e}")

def read_sent_ids():
    if os.path.exists(SENT_IDS_FILE):
        with open(SENT_IDS_FILE, "r") as f:
            return json.load(f)
    return []

def save_sent_ids(sent_ids):
    with open(SENT_IDS_FILE, "w") as f:
        json.dump(sent_ids, f, indent=4)

def extract_text(prop_list, default="Tidak ada data"):
    """Ambil isi teks dari rich_text atau title"""
    if isinstance(prop_list, list) and prop_list:
        return prop_list[0].get("plain_text", default)
    return default

def extract_formula(prop):
    """Ambil isi dari formula"""
    if isinstance(prop, dict):
        formula_result = prop.get("formula", {})
        logger.debug(f"Formula result: {json.dumps(formula_result)}")
        
        if "string" in formula_result:
            return formula_result["string"]
        elif "number" in formula_result:
            return formula_result["number"]
        elif "boolean" in formula_result:
            return formula_result["boolean"]
        elif "date" in formula_result:
            return formula_result["date"].get("start", "Tidak ada data")
    return "Tidak ada data"

def extract_date(prop):
    """Ambil tanggal dari properti type date dan format ke 'DD/MM/YYYY HH:MM'"""
    if isinstance(prop, dict):
        date_value = prop.get("date")
        if isinstance(date_value, dict):
            raw_date = date_value.get("start")
            if raw_date:
                dt = datetime.fromisoformat(raw_date)
                return dt.strftime("%d/%m/%Y %H:%M")
    return "Tidak ada data"

def main():
    notion_data = get_notion_data()
    if not notion_data:
        return

    results = notion_data.get("results", [])
    if not results:
        logger.info("No data found.")
        return

    sent_ids = read_sent_ids()

    for item in results:
        item_id = item.get("id")
        properties = item.get("properties", {})

        # Ambil data dari properti
        activities_name = extract_text(properties.get("Activities Name", {}).get("title", []))
        deliverable_name = extract_text(properties.get("Deliverable Name", {}).get("rich_text", []))
        link_activities = extract_formula(properties.get("Link Activities", {}))
        link_approval = extract_formula(properties.get("Link Approval", {}))
        # Properti tambahan
        project_name = extract_text(properties.get("Project Name", {}).get("rich_text", []), default="-")
        work_package_name = extract_text(properties.get("Work Package Name", {}).get("rich_text", []))
        id_activities = extract_text(properties.get("ID Activities", {}).get("rich_text", []))
        uploader_name = extract_text(properties.get("Uploader.Name (As)", {}).get("rich_text", []))
        upload_date = extract_date(properties.get("Upload.Date", {}))

        # Ambil Tele ID
        tele_id = extract_text(properties.get("ID Telegram (Us)", {}).get("rich_text", []))

        logger.debug(f"Tele ID for item {item_id}: {tele_id}")

        if item_id not in sent_ids and tele_id not in [None, "", "Tidak ada data"]:
            message = (
                f"*PERMINTAAN APPROVAL DELIVERABLE*\n\n"
                f"📅 *Tanggal Upload:* {upload_date}\n"
                f"✅ *Nama Deliverable:* {deliverable_name}\n"
                f"📁 *Nama Project:* {project_name}\n"
                f"📦 *Work Package:* {work_package_name}\n"
                f"📄 *Nama Activity:* {activities_name}\n"
                f"🆔 *ID Activity:* {id_activities}\n"
                f"👤 *Diupload oleh:* {uploader_name}\n"
                f"📎 *Link Informasi Activity:* {link_activities}\n"
                f"📎 *Link Form Approval:* {link_approval}\n"
            )
            logger.debug(f"Sending message: {message}")
            send_to_telegram(tele_id, message)
            sent_ids.append(item_id)
            save_sent_ids(sent_ids)

if __name__ == "__main__":
    main()
