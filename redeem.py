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

BATCH_ID = os.environ.get("BATCH_ID", "default")

URL = "https://wos-giftcode.centurygame.com/"
SCREENSHOT_DIR = "screenshots"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

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
        print("[ERROR] ids.txt not found. Please check if the file exists.")
        sys.exit(1)

options = Options()
options.add_argument("--start-maximized")
options.add_argument("--headless")
options.add_argument("--disable-gpu")
options.add_argument("--disable-extensions")
options.add_argument("--disable-dev-shm-usage")
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
        ocr_log_lines.append(f"{os.path.basename(img_path)} OCR result:\n{text}\n\n")
        normalized = normalize_ocr_text(text)
        failed = any(keyword in normalized for keyword in FAILURE_KEYWORDS)
        return text, failed
    except Exception:
        return "OCR failed", True


for player_id in player_ids:
    try:
        driver.get(URL)
        id_input = wait.until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, ".roleId_con .input_wrap input[placeholder='角色ID']")
            )
        )
        id_input.clear()
        id_input.send_keys(player_id)

        login_btn = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".roleId_con .login_btn"))
        )
        login_btn.click()

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

        exchange_btn = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".exchange_btn"))
        )
        exchange_btn.click()

        time.sleep(3)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        temp_path = os.path.join(SCREENSHOT_DIR, f"{player_id}_{timestamp}_temp.png")
        driver.save_screenshot(temp_path)

        ocr_text, is_failed = is_failure_screenshot(temp_path)
        reason = extract_failure_reason(ocr_text) if is_failed else ""

        new_name = f"{player_id}_{timestamp}_{'fail' if is_failed else 'success'}.png"
        new_path = os.path.join(SCREENSHOT_DIR, new_name)
        os.rename(temp_path, new_path)

        if is_failed:
            failure.append((player_id, reason))
        else:
            success.append((player_id, "Success"))

    except Exception as e:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        error_path = os.path.join(SCREENSHOT_DIR, f"{player_id}_{timestamp}_error.png")
        driver.save_screenshot(error_path)
        failure.append((player_id, f"Exception: {type(e).__name__}"))

driver.quit()

summary_lines = []
summary_lines.append("--- Summary ---\n")
summary_lines.append(f"Success: {len(success)} player(s)\n")
for s in success:
    summary_lines.append(f" - {s[0]} -> {s[1]}\n")
summary_lines.append(f"Failed: {len(failure)} player(s)\n")
for f_ in failure:
    summary_lines.append(f" - {f_[0]} -> Failed, {f_[1]}\n")

result_object = {
    "success": success,  # list of (player_id, "Success")
    "failure": failure,  # list of (player_id, reason)
}
print(json.dumps(result_object, ensure_ascii=False))

# ✅ 寫入 log 檔案（照舊）
log_path = f"logs/log_{BATCH_ID}.txt"
ocr_log_path = f"logs/ocr_log_{BATCH_ID}.txt"

summary_lines = []
summary_lines.append("--- Summary ---\n")
summary_lines.append(f"Success: {len(success)} player(s)\n")
for s in success:
    summary_lines.append(f" - {s[0]} -> {s[1]}\n")
summary_lines.append(f"Failed: {len(failure)} player(s)\n")
for f_ in failure:
    summary_lines.append(f" - {f_[0]} -> Failed, {f_[1]}\n")
output_log = "".join(summary_lines)

# 覆蓋最新 log
with open("logs/log.txt", "w", encoding="utf-8") as f:
    f.write(output_log)
with open("logs/ocr_log.txt", "w", encoding="utf-8") as f:
    f.writelines(ocr_log_lines)

# 追加 batch log
with open(log_path, "a", encoding="utf-8") as f:
    f.write(output_log)
with open(ocr_log_path, "a", encoding="utf-8") as f:
    f.writelines(ocr_log_lines)
