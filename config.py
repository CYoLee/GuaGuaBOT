import os


# 將字串轉為清單（逗號分隔）
def parse_list(env_str):
    return [int(gid.strip()) for gid in env_str.split(",") if gid.strip()]


GUILD_IDS = parse_list(os.getenv("GUILD_IDS", ""))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", "0"))
LOG_FIRESTORE_ENABLED = os.getenv("LOG_FIRESTORE_ENABLED", "true").lower() == "true"
ENABLE_DEBUG_COMMANDS = os.getenv("ENABLE_DEBUG_COMMANDS", "false").lower() == "true"

# 權限管理：這個建議仍寫死在程式碼中（較安全），也比較不需要調整
ROLE_PERMISSIONS = {
    "add_notify": [1299676212247138314, 1126409399351644171],
    "edit_notify": [
        1299677394151669770,
        1299677504495161374,
        1352587057419259974,
        1126409399351644171,
    ],
    "remove_notify": [
        1299677394151669770,
        1299677504495161374,
        1352587057419259974,
        1126409399351644171,
    ],
}
