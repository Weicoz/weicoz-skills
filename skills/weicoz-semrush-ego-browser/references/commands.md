# 浏览器命令

## Keyword Magic

ego-browser 主路径：

```bash
ego-browser nodejs <<'EOF'
const task = await useOrCreateTaskSpace('semrush keyword research')
const host = process.env.WEICOZ_SEMRUSH_PROXY_HOST
const url = new URL(`https://${host}/analytics/keywordmagic/`)
url.searchParams.set('q', '<query>')
url.searchParams.set('db', 'us')
if (process.env.WEICOZ_SEMRUSH_FID) url.searchParams.set('fid', process.env.WEICOZ_SEMRUSH_FID)
await openOrReuseTab(url.toString(), { wait: true, timeout: 30 })
cliLog(JSON.stringify({ taskId: task.id, page: await pageInfo(), snapshot: await snapshotText() }))
EOF
```

确认数据已提取并保存后，单独清理：

```bash
ego-browser nodejs <<'EOF'
const result = await completeTaskSpace(<task-id>, { keep: false })
cliLog(JSON.stringify(result))
EOF
```

带页面筛选验证和 JSON 输出：

```bash
node scripts/keywordmagic-filter-runner.mjs \
  --query '<query>' --db us --fid "$WEICOZ_SEMRUSH_FID" \
  --seed-url '<verified-filter-url>' --minVolume 100 --maxKd 30 --minCpc 0.1 --limit 20
```

## Fallback

仅 ego-browser 不可用或无法完成当前能力时：

```text
browser-skill: bsk session start -> navigate/snapshot/evaluate -> bsk session stop
@Chrome: load chrome:control-chrome -> browser-client binding -> reuse tab -> close temporary tab
```

任何 fallback 都必须记录上一层失败信号，不得直接跳级。
