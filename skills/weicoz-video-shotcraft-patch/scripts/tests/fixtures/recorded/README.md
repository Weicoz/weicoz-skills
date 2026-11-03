# 真实接口录制样例

这些文件是各来源真实接口的原始响应（关键词 `water bottle`，每页 3 条），用来防止手写样例与真实接口不符。
录制日期：2026-11-03。

重录方法（需要 `PEXELS_API_KEY`、`PIXABAY_API_KEY`、`UNSPLASH_ACCESS_KEY`；Wikimedia 不需要 Key）：

    python3 skills/weicoz-video-shotcraft-patch/scripts/tests/record_fixtures.py

脚本不保存请求地址，响应里出现 Key 值时拒绝写入。重录后跑全部测试，确认解析仍通过。
