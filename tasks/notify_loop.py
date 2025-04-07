# tasks/notify_loop.py

from datetime import datetime, timedelta
from firebase_admin import firestore
from google.cloud.firestore_v1 import FieldFilter
import pytz
import discord

TIMEZONE = pytz.timezone("Asia/Taipei")


async def run_notify_once(bot: discord.Client):
    db = firestore.client()
    now_utc = datetime.now(pytz.utc)
    now_taipei = now_utc.astimezone(TIMEZONE)

    lower_bound = now_utc - timedelta(seconds=30)
    upper_bound = now_utc + timedelta(seconds=15)

    print(f"🔁 notify_task run (UTC): {now_utc.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🕰️ 台北時間：{now_taipei.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"⏱️ 查詢時間範圍(UTC):{lower_bound} ~ {upper_bound}")

    try:
        docs = list(
            db.collection("notifications")
            .where(filter=FieldFilter("datetime", ">=", lower_bound))
            .where(filter=FieldFilter("datetime", "<=", upper_bound))
            .stream()
        )
        print(f"📄 找到 {len(docs)} 筆提醒")

        for doc in docs:
            data = doc.to_dict()
            print(f"➡️ 發送提醒：{data}")
            channel_id = data.get("channel_id")
            mention = data.get("mention", "")
            message = data.get("message", "")

            try:
                channel = await bot.fetch_channel(channel_id)
                if channel:
                    content = (
                        f"{mention}\n⏰ 活動提醒 ⏰{message}"
                        if mention
                        else f"⏰ 活動提醒 ⏰{message}"
                    )
                    await channel.send(content)
                    db.collection("notifications").document(doc.id).delete()
                    print(f"✅ 發送成功並刪除：{doc.id}")
                else:
                    print(f"⚠️ 找不到頻道：{channel_id}")
            except Exception as e:
                print(f"❌ 發送失敗：{type(e).__name__}: {e}")
    except Exception as e:
        print(f"❌ 通知任務錯誤：{type(e).__name__}: {e}")
