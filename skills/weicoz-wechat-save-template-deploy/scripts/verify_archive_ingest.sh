#!/usr/bin/env bash
set -euo pipefail

SSH_TARGET="${WEICOZ_WECHAT_SAVE_SSH_TARGET:?set WEICOZ_WECHAT_SAVE_SSH_TARGET}"
SSH_KEY="${WEICOZ_WECHAT_SAVE_SSH_KEY:?set WEICOZ_WECHAT_SAVE_SSH_KEY}"
REMOTE_DIR="${WEICOZ_WECHAT_SAVE_REMOTE_DIR:?set WEICOZ_WECHAT_SAVE_REMOTE_DIR}"
REMOTE_PORT="${WEICOZ_WECHAT_SAVE_REMOTE_PORT:?set WEICOZ_WECHAT_SAVE_REMOTE_PORT}"
DB_CONTAINER="${WEICOZ_WECHAT_SAVE_DB_CONTAINER:?set WEICOZ_WECHAT_SAVE_DB_CONTAINER}"
DB_NAME="${WEICOZ_WECHAT_SAVE_DB_NAME:?set WEICOZ_WECHAT_SAVE_DB_NAME}"

ssh -i "$SSH_KEY" "$SSH_TARGET" "set -euo pipefail; cd '$REMOTE_DIR'; token=\$(grep '^WECOM_ARCHIVE_INGEST_TOKEN=' .env.production | cut -d= -f2- || true); if [ -z \"\$token\" ]; then token=\$(grep '^WECHAT_WEBHOOK_TOKEN=' .env.production | cut -d= -f2-); fi; ts=\$(date -u +%Y%m%dT%H%M%SZ); before=\$(docker exec '$DB_CONTAINER' psql -U root -d '$DB_NAME' -At -c \"select count(*) from wecom_archive_messages;\"); payload=\$(printf '{\"token\":\"%s\",\"source\":\"deploy-skill-smoke\",\"last_seq\":\"%s\",\"chatdata\":[{\"seq\":\"%s\",\"msgid\":\"skill-smoke-%s\",\"publickey_ver\":1,\"encrypt_random_key\":\"skill-enc-key-%s\",\"encrypt_chat_msg\":\"skill-enc-msg-%s\",\"decrypted\":{\"msgid\":\"skill-smoke-%s\",\"action\":\"send\",\"from\":\"skill-bot\",\"roomid\":\"skill-room\",\"msgtime\":1715000000,\"msgtype\":\"text\",\"text\":{\"content\":\"skill smoke %s\"}}}]}' \"\$token\" \"\$ts\" \"\$ts\" \"\$ts\" \"\$ts\" \"\$ts\" \"\$ts\" \"\$ts\"); echo '[verify-archive] before='\"\$before\"; curl -i -m 10 -sS -X POST 'http://127.0.0.1:$REMOTE_PORT/api/wecom/archive/messages' -H 'content-type: application/json' --data \"\$payload\"; echo; after=\$(docker exec '$DB_CONTAINER' psql -U root -d '$DB_NAME' -At -c \"select count(*) from wecom_archive_messages;\"); echo '[verify-archive] after='\"\$after\"; docker exec '$DB_CONTAINER' psql -U root -d '$DB_NAME' -c \"select msg_id, seq, from_user_id, room_id, msg_type, text_content from wecom_archive_messages order by id desc limit 3;\""
