# redeem.py
import os
import sys
import time
import pytesseract
import json
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from PIL import Image
import firebase_admin
from firebase_admin import credentials, firestore

# Firebase 初始化（從 .env 抓 FIREBASE_CREDENTIALS）
from dotenv import load_dotenv

load_dotenv()

cred_json = json.loads(os.environ.get("FIREBASE_CREDENTIALS", "{}"))
if "private_key" in cred_json:
    cred_json["private_key"] = cred_json["private_key"].replace("\\n", "\n")

if not firebase_admin._apps:
    cred = credentials.Certificate(cred_json)
    firebase_admin.initialize_app(cred)

db = firestore.client()


BATCH_ID = os.environ.get("BATCH_ID", "default")
URL = "https://wos-giftcode.centurygame.com/"
SCREENSHOT_DIR = os.path.join("screenshots", BATCH_ID)
LOG_DIR = os.path.join("logs", BATCH_ID)
os.makedirs(SCREENSHOT_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

if len(sys.argv) < 2:
    print("[ERROR] Invalid arguments. Usage: redeem.py <code> [<ID>]")
    sys.exit(1)

REDEEM_CODE = sys.argv[1]
player_ids = []

if len(sys.argv) == 3:
    player_ids = [sys.argv[2]]
else:
    try:
        with open("ids.txt", "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    player_ids.append(line)
    except FileNotFoundError:
        print("[ERROR] ids.txt not found.")
        sys.exit(1)

options = Options()
options.add_argument("--headless")
options.add_argument("--disable-gpu")
options.add_argument("--no-sandbox")

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)
wait = WebDriverWait(driver, 30)

success = []
failure = []
ocr_log_lines = []

FAILURE_KEYWORDS = [
    "兌換碼不存在",
    "請檢查大小寫",
    "超出免換時間",
    "錯誤",
    "無效",
    "超出兌換時間",
    "無法領取",
    "已領取",
    "同類型",
]
FAILURE_REASON_MAP = {
    "兌換碼不存在": "Invalid Code",
    "請檢查大小寫": "Invalid Code",
    "超出免換時間": "Expired",
    "錯誤": "Error",
    "無效": "Invalid",
    "超出兌換時間": "Expired",
    "無法領取": "Unavailable",
    "已領取": "Redeemed",
    "同類型": "Redeemed",
}


def normalize_ocr_text(text):
    return text.replace(" ", "")


def extract_failure_reason(text):
    normalized = normalize_ocr_text(text)
    for keyword in FAILURE_KEYWORDS:
        if keyword in normalized:
            return FAILURE_REASON_MAP.get(keyword, "Unknown Reason")
    return "Unknown Reason"


def is_failure_screenshot(img_path):
    try:
        img = Image.open(img_path)
        text = pytesseract.image_to_string(img, lang="chi_tra+eng")
        normalized = normalize_ocr_text(text)
        failed = any(keyword in normalized for keyword in FAILURE_KEYWORDS)
        return text, failed
    except Exception:
        return "OCR failed", True


for player_id in player_ids:
    player_ocr_log = []
    try:
        driver.get(URL)
        id_input = wait.until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, ".roleId_con .input_wrap input[placeholder='角色ID']")
            )
        )
        id_input.clear()
        id_input.send_keys(player_id)
        wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".roleId_con .login_btn"))
        ).click()
        wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".roleInfo_con .avatar"))
        )
        code_input = wait.until(
            EC.presence_of_element_located(
                (
                    By.CSS_SELECTOR,
                    ".code_con .input_wrap input[placeholder='請輸入兌換碼']",
                )
            )
        )
        code_input.clear()
        code_input.send_keys(REDEEM_CODE)
        wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".exchange_btn"))
        ).click()

        time.sleep(3)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        temp_path = os.path.join(SCREENSHOT_DIR, f"{player_id}_{timestamp}_temp.png")
        driver.save_screenshot(temp_path)

        ocr_text, is_failed = is_failure_screenshot(temp_path)
        player_ocr_log.append(f"{os.path.basename(temp_path)} OCR:\n{ocr_text}\n\n")
        reason = extract_failure_reason(ocr_text) if is_failed else ""
        suffix = reason.replace(" ", "_") if is_failed else "Success"
        new_name = f"{player_id}_{timestamp}_{suffix}.png"
        os.rename(temp_path, os.path.join(SCREENSHOT_DIR, new_name))

        # Firestore logging
        result_data = {
            "code": REDEEM_CODE,
            "player_id": player_id,
            "batch_id": BATCH_ID,
            "timestamp": firestore.SERVER_TIMESTAMP,
            "datetime": datetime.now().isoformat(),
            "result": "fail" if is_failed else "success",
            "reason": reason,
        }
        db.collection("redeem_logs").add(result_data)

        if is_failed:
            failure.append((player_id, reason))
        else:
            success.append((player_id, "Success"))

    except Exception as e:
        failure.append((player_id, f"Exception: {type(e).__name__}: {e}"))
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        err_img = os.path.join(SCREENSHOT_DIR, f"{player_id}_{timestamp}_error.png")
        driver.save_screenshot(err_img)

    # Write per-player log
    player_ocr_path = os.path.join(LOG_DIR, f"ocr_{player_id}_latest.txt")
    with open(player_ocr_path, "w", encoding="utf-8") as f:
        f.writelines(player_ocr_log)
    ocr_log_lines.extend(player_ocr_log)

driver.quit()

# Final print
result_object = {"success": success, "failure": failure}
print(json.dumps(result_object, ensure_ascii=False), end="")

# Append summary log
log_path = os.path.join(LOG_DIR, "log.txt")
ocr_log_path = os.path.join(LOG_DIR, "ocr_log.txt")

summary_lines = [f"--- Summary ({datetime.now()}) ---\n\n"]
summary_lines += [f" - {s[0]} -> {s[1]}\n" for s in success]
summary_lines += [f" - {f[0]} -> Failed, {f[1]}\n" for f in failure]

with open(log_path, "a", encoding="utf-8") as f:
    f.writelines(summary_lines)
with open(ocr_log_path, "a", encoding="utf-8") as f:
    f.writelines(ocr_log_lines)

# Exit with 1 if failure exists
sys.exit(1 if failure else 0)
