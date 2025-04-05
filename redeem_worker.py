# redeem_worker.py
import os
import json
import discord
import asyncio
from datetime import datetime
from discord.ext import tasks
from dotenv import load_dotenv
import subprocess

import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1 import FieldFilter

load_dotenv()

cred_json = json.loads(os.environ.get("FIREBASE_CREDENTIALS", "{}"))
if "private_key" in cred_json:
    cred_json["private_key"] = cred_json["private_key"].replace("\\n", "\n")

if not firebase_admin._apps:
    cred = credentials.Certificate(cred_json)
    firebase_admin.initialize_app(cred)

db = firestore.client()

intents = discord.Intents.default()
bot = discord.Client(intents=intents)


@bot.event
async def on_ready():
    print(f"✅ Redeem Worker Online as {bot.user}")
    if not check_tasks.is_running():
        check_tasks.start()


@tasks.loop(seconds=15)
async def check_tasks():
    print("🔍 Checking redeem tasks...")
    tasks_ref = db.collection("redeem_tasks").where(
        filter=FieldFilter("status", "==", "pending")
    )
    docs = list(tasks_ref.stream())

    batches = {}
    for doc in docs:
        task = doc.to_dict()
        batch_id = task.get("batch_id", "default")
        batches.setdefault(batch_id, []).append((doc.id, task))

    for batch_id, task_list in batches.items():
        await process_batch(batch_id, task_list)


async def process_batch(batch_id, task_list):
    channel_id = None
    all_success = []
    all_failure = []
    code = task_list[0][1]["code"] if task_list else "unknown"

    for doc_id, task in task_list:
        code = task.get("code")
        player_id = task.get("player_id")
        channel_id = task.get("channel_id")

        print(f"🎁 Redeeming code: {code} for {player_id}...")

        try:
            result_json = await run_redeem(code, player_id, batch_id)
            result = json.loads(result_json)

            for s in result.get("success", []):
                all_success.append(s[0])
            for f in result.get("failure", []):
                all_failure.append((f[0], f[1]))

            db.collection("redeem_tasks").document(doc_id).update(
                {
                    "status": "done",
                    "result": json.dumps(result, ensure_ascii=False),
                    "completed_at": firestore.SERVER_TIMESTAMP,
                }
            )
        except Exception as e:
            all_failure.append((player_id, f"{type(e).__name__}: {e}"))
            db.collection("redeem_tasks").document(doc_id).update(
                {
                    "status": "done",
                    "result": f"{player_id} -> Failed, {type(e).__name__}: {e}",
                    "completed_at": firestore.SERVER_TIMESTAMP,
                }
            )

    # ✅ 回傳統一的結果到 Discord
    if channel_id:
        try:
            channel = bot.get_channel(channel_id)
            if channel:
                summary_lines = []
                summary_lines.append(f"📦 Result of redeem `{code}`:")
                summary_lines.append("--- Summary ---")
                summary_lines.append(f"Success: {len(all_success)} player(s)")
                for pid in all_success:
                    summary_lines.append(f" - {pid} -> Success")
                summary_lines.append(f"Failed: {len(all_failure)} player(s)")
                for pid, reason in all_failure:
                    summary_lines.append(f" - {pid} -> Failed, {reason}")
                final_text = "\n".join(summary_lines)
                await channel.send(f"```\n{final_text[:1800]}\n```")
        except Exception as e:
            print(f"❌ Failed to send result message: {e}")


async def run_redeem(code: str, player_id: str, batch_id: str = "default") -> str:
    try:

        def call_redeem():
            env = os.environ.copy()
            if batch_id:
                env["BATCH_ID"] = batch_id
            return subprocess.run(
                ["python", "redeem.py", code, player_id],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                encoding="utf-8",
                timeout=90,
                env=env,  # ✅ 傳入環境變數
            ).stdout.strip()

        result = await asyncio.to_thread(call_redeem)
        json.loads(result)  # 確保 JSON 格式正確
        return result  # ⬅️ 正確傳回

    except subprocess.TimeoutExpired:
        return f"{player_id} -> Failed, Timeout"
    except Exception as e:
        return f"{player_id} -> Failed, {type(e).__name__}: {e}"


if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN not set.")
    bot.run(token)
