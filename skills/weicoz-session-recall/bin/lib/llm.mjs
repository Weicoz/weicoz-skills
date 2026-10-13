// 摘要模型的调用层：凭据、降级链、超时、JSON 抽取。
//
// 网关是本机 NewAPI（复用 ~/.opencodex 的 newapi 凭据，不写入任何仓库）。
// 关键教训（都是踩过的坑，别改回去）：
//  - 单个请求会挂死（TCP 一直 ESTABLISHED 但 14 分钟无响应），所以必须有 AbortSignal 超时；
//  - 免费渠道会集体掉线（model_not_found），所以必须有降级链而不是单模型重试；
//  - 推理型模型偶尔把思考过程当正文输出，解析失败就换下一个模型，不要原地重试同一个。
import { readFile } from 'node:fs/promises';
import { join } from 'node:path';
import { homedir } from 'node:os';

/**
 * 解析 API 配置与协议：
 * - 协议：支持 'chat' (OpenAI Chat Completions 规范) 与 'respond' / 'responses' (OpenAI Responses 规范)
 * - 判定优先级：
 *   1. 环境变量显式指定 (SESSION_RECALL_PROTOCOL / LLM_WIKI_PROTOCOL)
 *   2. 若未指定，检查环境变量提供的端点 URL (包含 /responses 则为 respond，包含 /chat/completions 则为 chat)
 *   3. 若未提供 URL，读取宿主配置 (~/.opencodex/config.json):
 *      - provider.adapter 为 'openai-responses' -> 协议为 respond，端点为 ${baseUrl}/responses
 *      - provider.adapter 为 'openai-chat' -> 协议为 chat，端点为 ${baseUrl}/chat/completions
 *   4. 最终默认兜底：协议 chat，端点 https://api.deepseek.com/v1/chat/completions
 */
export async function resolveApiConfig() {
  let url = (process.env.SESSION_RECALL_API_URL || process.env.LLM_WIKI_API_URL || '').trim();
  let protocol = (process.env.SESSION_RECALL_PROTOCOL || process.env.LLM_WIKI_PROTOCOL || '').toLowerCase().trim();
  if (protocol === 'responses') protocol = 'respond';

  let hostBaseUrl = '';
  let hostAdapter = '';

  try {
    const cfg = JSON.parse(await readFile(join(homedir(), '.opencodex', 'config.json'), 'utf8'));
    const provider = cfg?.providers?.newapi || cfg?.providers?.deepseek;
    if (provider) {
      hostBaseUrl = (provider.baseUrl || '').trim();
      hostAdapter = (provider.adapter || '').trim();
    }
  } catch { /* 忽略本地宿主配置解析失败 */ }

  if (!protocol) {
    if (url.includes('/responses')) {
      protocol = 'respond';
    } else if (url.includes('/chat/completions')) {
      protocol = 'chat';
    } else if (hostAdapter === 'openai-responses') {
      protocol = 'respond';
    } else if (hostAdapter === 'openai-chat') {
      protocol = 'chat';
    } else {
      protocol = 'chat';
    }
  }

  if (!url) {
    if (hostBaseUrl) {
      url = hostBaseUrl;
    } else if (protocol === 'respond') {
      url = 'https://api.openai.com/v1';
    } else {
      url = 'https://api.deepseek.com/v1';
    }
  }

  const trimmed = url.replace(/\/+$/, '');
  if (protocol === 'respond') {
    url = trimmed.endsWith('/responses') ? trimmed : `${trimmed}/responses`;
  } else {
    url = trimmed.endsWith('/chat/completions') ? trimmed : `${trimmed}/chat/completions`;
  }

  return { url, protocol };
}

/** 兼容旧版入口：返回当前解析后的请求端点 URL。 */
export async function resolveApiUrl() {
  const { url } = await resolveApiConfig();
  return url;
}

/** 根据协议构造标准化请求载荷。 */
export function buildRequestBody(protocol, model, prompt) {
  if (protocol === 'respond') {
    return {
      model,
      instructions: SYSTEM_PROMPT,
      input: [
        {
          type: 'message',
          role: 'user',
          content: [{ type: 'input_text', text: prompt }],
        },
      ],
      temperature: 0.2,
      max_output_tokens: 1500,
    };
  }

  return {
    model,
    messages: [
      { role: 'system', content: SYSTEM_PROMPT },
      { role: 'user', content: prompt },
    ],
    temperature: 0.2,
    max_tokens: 1500,
  };
}

/** 兼容多协议提取响应正文文本（支持 choices[0].message.content 与 output[].content[].text / output_text）。 */
export function extractResponseContent(d) {
  if (!d || typeof d !== 'object') return '';

  if (d.choices?.[0]?.message?.content) {
    return d.choices[0].message.content;
  }

  if (typeof d.output_text === 'string' && d.output_text) {
    return d.output_text;
  }

  if (Array.isArray(d.output)) {
    const textParts = [];
    for (const item of d.output) {
      if (!item) continue;
      if (Array.isArray(item.content)) {
        for (const part of item.content) {
          if (typeof part === 'string') {
            textParts.push(part);
          } else if (part && typeof part.text === 'string') {
            textParts.push(part.text);
          }
        }
      } else if (typeof item.text === 'string') {
        textParts.push(item.text);
      } else if (typeof item.content === 'string') {
        textParts.push(item.content);
      }
    }
    if (textParts.length) return textParts.join('');
  }

  if (typeof d.text === 'string') return d.text;
  if (typeof d.content === 'string') return d.content;

  return '';
}

const PRIMARY = process.env.SESSION_RECALL_MODEL || process.env.LLM_WIKI_MODEL || '';

/** 模型降级链：主模型失败（渠道掉线 / 限流 / 输出不可解析）时自动顶上。 */
export const MODELS = PRIMARY
  ? [PRIMARY, 'deepseek-flash', 'deepseek-v4-flash-0731', 'claude-haiku-5-5']
  : ['deepseek-flash', 'deepseek-v4-flash-0731', 'claude-haiku-5-5'];

/** 单会话送给模型的字符预算。 */
export const INPUT_BUDGET = 12000;
/** 单次请求超时：网关偶发挂起，必须快速失败交给降级链，否则整个任务被一个请求拖死。 */
export const CALL_TIMEOUT_MS = Number(process.env.SESSION_RECALL_TIMEOUT_MS || 45_000);
export const USER_MSG_CAP = 700;
export const ASSISTANT_MSG_CAP = 900;

/** 凭据：环境变量优先，其次复用本机 newapi 配置。 */
export async function loadApiKey() {
  if (process.env.SESSION_RECALL_API_KEY) return process.env.SESSION_RECALL_API_KEY;
  if (process.env.LLM_WIKI_API_KEY) return process.env.LLM_WIKI_API_KEY;
  try {
    const cfg = JSON.parse(await readFile(join(homedir(), '.opencodex', 'config.json'), 'utf8'));
    return cfg?.providers?.newapi?.apiKey || '';
  } catch { return ''; }
}

export const SYSTEM_PROMPT = `你是知识库整理助手。用户在 DSH 里执行过大量开发会话，需要一份可快速检索的摘要索引。
读下面的会话记录，输出严格的 JSON（不要 markdown 代码块、不要额外解释）：
{"summary":"一句到一段话的中文摘要","keywords":["关键词"],"status":"已完成|进行中|中断|仅咨询","artifacts":["产出物"]}
要求：
- summary：2-4 句中文，说清这段会话要解决什么问题、做到什么程度、有什么结论或未完成的部分。不要复述用户原话，要概括意图和结果。
- keywords：3-8 个检索关键词，可含项目名/文件名/技术名/业务名词，用中文或英文原词。
- status：根据会话结束时的状态判断。
- artifacts：会话中产生或修改的产物（文件、文档、代码、方案），没有就空数组。`;

/** 把解析出的会话拼成模型输入：用户原话为主，助手回复只留头尾两条当结论。 */
export function buildPrompt(s, label = '') {
  const parts = [];
  if (label) parts.push(`所属项目：${label}`);
  parts.push(`会话标题：${s.title || '（无）'}`);
  parts.push(`用户消息条数：${s.userMsgs.length}，工具调用：${Object.entries(s.tools).map(([k, v]) => `${k}×${v}`).join('、') || '无'}`);
  parts.push('');
  parts.push('===== 用户原话（按时间顺序）=====');
  s.userMsgs.forEach((t, i) => {
    const clipped = t.length > USER_MSG_CAP ? t.slice(0, USER_MSG_CAP) + ' …[截断]' : t;
    parts.push(`[${i + 1}] ${clipped}`);
  });
  const tail = s.assistantTexts.filter(Boolean);
  if (tail.length) {
    parts.push('');
    parts.push('===== 助手的关键回复（节选）=====');
    const picks = tail.length <= 4 ? tail : [...tail.slice(0, 2), ...tail.slice(-2)];
    for (const t of picks) {
      parts.push(`· ${(t.length > ASSISTANT_MSG_CAP ? t.slice(0, ASSISTANT_MSG_CAP) + ' …[截断]' : t).replace(/\n+/g, ' ')}`);
    }
  }
  let body = parts.join('\n');
  if (body.length > INPUT_BUDGET) body = body.slice(0, INPUT_BUDGET) + '\n…[输入已截断]';
  return body;
}

/** 模型偶尔会用 ```json 围栏或加前后缀，这里剥掉再取第一个完整对象。 */
export function extractJson(raw) {
  if (!raw) return null;
  const t = String(raw).trim().replace(/^```(?:json)?/i, '').replace(/```$/, '').trim();
  const start = t.indexOf('{');
  const end = t.lastIndexOf('}');
  if (start < 0 || end <= start) return null;
  try { return JSON.parse(t.slice(start, end + 1)); } catch { return null; }
}

async function callOneModel(model, prompt, apiKey, retries = 0) {
  let lastErr = '未知错误';
  const { url: apiUrl, protocol } = await resolveApiConfig();
  const body = buildRequestBody(protocol, model, prompt);

  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const res = await fetch(apiUrl, {
        method: 'POST',
        headers: { Authorization: `Bearer ${apiKey}`, 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: AbortSignal.timeout(CALL_TIMEOUT_MS),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status} ${(await res.text()).slice(0, 140)}`);
      const d = await res.json();
      const raw = extractResponseContent(d);
      const parsed = extractJson(raw);
      if (!parsed) throw new Error(`无法解析模型输出：${String(raw).slice(0, 140)}`);
      return { ok: true, parsed };
    } catch (e) {
      lastErr = String(e.message || e);
      if (attempt < retries) await new Promise((r) => setTimeout(r, 1200 * (attempt + 1)));
    }
  }
  return { ok: false, error: lastErr };
}

/** 依次尝试降级链上的模型，全挂才返回错误。 */
export async function callModel(prompt, apiKey) {
  if (!apiKey) {
    return { error: '未配置 API Key：请设置环境变量 SESSION_RECALL_API_KEY 或在宿主配置 (~/.opencodex/config.json) 中提供凭据。' };
  }
  const errors = [];
  for (const model of MODELS) {
    const r = await callOneModel(model, prompt, apiKey);
    if (r.ok) return { ...r.parsed, modelUsed: model };
    errors.push(`${model}: ${r.error.slice(0, 80)}`);
  }
  return { error: errors.join(' | ') };
}
