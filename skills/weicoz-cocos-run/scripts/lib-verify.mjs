// cocos-verify / cocos-playtest 的纯判定函数，便于单测。

// 失败输出只含超时类（Test timed out / Timeout calling），且没有任何断言报错（含时长断言）
export const isTimeoutOnly = (out) => {
  const timeout = /Test timed out|Timeout calling "?onTaskUpdate/.test(out)
  const assertion = out.split('\n').some((l) => /AssertionError|expected .* to (be|equal|deeply|have|match|contain)|to be less than/.test(l))
  return timeout && !assertion
}

// 只有本机负载高且失败全是超时类才重跑
export const shouldRerun = (out, loadHigh) => loadHigh && isTimeoutOnly(out)

// 重跑后明细：通过时保留首轮失败输出末 5 行并标不稳定
export const flakyDetail = (firstOut) => {
  const tail = firstOut.split('\n').map((l) => l.trim()).filter(Boolean).slice(-5).join(' | ')
  return `不稳定：首轮超时（首轮失败输出末 5 行：${tail}）`
}

// 没有 test 脚本：未验证，不是通过
export const noTestScriptRow = () => ({ name: '单元测试', ok: false, unverified: true, missing: 'test 脚本', detail: '未验证（缺：test 脚本）' })

// 缩小范围的开关；快检本身是独立档位，不算缩小，但快检再限定脚本仍算部分
export const partialReasons = ({ quick, noRelease, scriptGiven }) =>
  [!quick && noRelease && '--no-release', scriptGiven && '--script'].filter(Boolean)

// 未知参数、缺值都报错，不静默忽略。返回 { error } 或 { ok: true }
export const checkArgs = (argv) => {
  const flags = ['--quick', '--no-release']
  const withValue = ['--project', '--script', '--port', '--base']
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i]
    if (flags.includes(a)) continue
    if (!withValue.includes(a)) return { error: a }
    const v = argv[++i]
    if (v === undefined || v.startsWith('--')) return { error: `${a}（缺值）` }
  }
  return { ok: true }
}

// 评分相关文件：改动须交用户确认。changed 为相对 base 变动或新建未跟踪的文件名
export const SCORING_FILES = ['AGENTS.md', 'CLAUDE.md', 'package.json']

// 返回 { verdict: 0|1|3, line }
export const finalVerdict = (rows, partial = []) => {
  const failed = rows.filter((r) => !r.ok && !r.unverified && !r.info)
  const missing = rows.filter((r) => r.unverified)
  if (failed.length) return { verdict: 1, line: `结论：不通过（失败：${failed.map((r) => r.name).join('、')}）` }
  const need = missing.map((r) => r.missing ?? r.detail)
  if (partial.length) need.push(`完整全检，本次用了 ${partial.join('、')}`)
  if (need.length) return { verdict: 3, line: `结论：未验证（缺：${need.join('；')}）` }
  return { verdict: 0, line: '结论：通过' }
}

// 试玩脚本结果：不只信自报的 pass，log 必须非空且逐项 ok
export const judgePlaytest = (r) => {
  if (!r || typeof r !== 'object') return { pass: false, error: '没有拿到结果' }
  if (!Array.isArray(r.log) || r.log.length === 0) return { pass: false, error: '脚本没有任何 check' }
  return { pass: r.pass === true && r.log.every((l) => l.ok === true) }
}

// 联系图分页：每页最多 size 张
export const paginate = (files, size = 12) => {
  const pages = []
  for (let i = 0; i < files.length; i += size) pages.push(files.slice(i, i + size))
  return pages
}
