
# GuaGuaBOT

GuaGuaBOT 是一個支援多人禮包碼兌換與活動提醒的 Discord Bot，搭配本地端 `redeem_worker.py` 自動化處理所有兌換任務。

---

## ✅ 功能總覽

### 🎁 禮包碼兌換
- `/redeem_submit` 提交兌換任務給本地 Worker 執行，支援單人與多人模式。
  - ✅ 自動根據 Discord 伺服器記錄各伺服器的玩家清單。
  - ✅ 輸入新玩家 ID 時自動儲存。
  - ✅ 回傳結果仿照 log.txt 格式整理輸出。

### 👥 玩家 ID 管理
- `/add_id` 新增玩家 ID
- `/remove_id` 移除玩家 ID
- `/list_ids` 列出所有已儲存的玩家 ID

### 🔔 活動提醒系統
- `/add_notify` 設定提醒（日期與時間分開輸入），支援 tag 他人
- `/remove_notify` 刪除提醒（依照關鍵字）
- `/list_notify` 顯示目前提醒列表
- ✅ 通知推送使用台灣時區 (Asia/Taipei)
- ✅ 執行時間 ±90 秒自動推播

### 📖 說明指令
- `/help` 支援中英文版本指令說明，繁體中文風格更活潑

---

## 🧠 系統架構

### Railway（主程式）
- `bot.py`：主程式，註冊 Slash 指令並啟動排程（notify_task）
- `cogs/*.py`：模組化管理各功能指令
- ✅ 長時間在線，負責處理使用者操作與活動推播

### 本地端（執行兌換）
- `redeem_worker.py`：每 15 秒檢查 Firestore 中的兌換任務，觸發 `redeem.py` 執行
- `redeem.py`：執行 Selenium 模擬兌換流程，自動截圖並使用 OCR 判斷是否成功

---

## 🗂️ Firestore 結構

### ids
```
/ids/{guild_id}/players/{doc_id}
  - player_id: "123456789"
```

### redeem_tasks
```
/redeem_tasks/{task_id}
  - code: "GIFT123"
  - player_id: "123456789"
  - channel_id: 123456789012345678
  - status: "pending" or "done"
  - result: "Success" / "Failed, Reason"
  - batch_id: "uuid片段" or None
  - completed_at: timestamp
```

### notifications
```
/notifications/{doc_id}
  - guild_id: "123456789"
  - channel_id: 123456789012345678
  - datetime: timestamp (Asia/Taipei)
  - mention: "@here"
  - message: "活動結束倒數一小時"
```

---

## 📎 使用教學

1. Railway 上部署 `bot.py` 主程式
2. 本地端部署 `redeem_worker.py` 搭配 Selenium 執行環境
3. 於 Discord 輸入 `/redeem_submit` 提交禮包碼（支援群體與個別）
4. 等待回傳統整結果（仿照 log.txt）
5. 指令列表：請輸入 `/help` 查看說明

---

## 👤 作者

Author: GuaGua  
Version: 1.0  
Last Updated: 2025/04/05

