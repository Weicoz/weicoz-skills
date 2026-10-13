import test from 'node:test';
import assert from 'node:assert/strict';
import {
  buildRequestBody,
  extractResponseContent,
  resolveApiConfig,
  SYSTEM_PROMPT,
} from './llm.mjs';

test('buildRequestBody：chat 协议生成 messages 结构与 max_tokens', () => {
  const body = buildRequestBody('chat', 'deepseek-chat', '用户测试输入');
  assert.equal(body.model, 'deepseek-chat');
  assert.equal(body.max_tokens, 1500);
  assert.ok(Array.isArray(body.messages));
  assert.equal(body.messages[0].role, 'system');
  assert.equal(body.messages[0].content, SYSTEM_PROMPT);
  assert.equal(body.messages[1].role, 'user');
  assert.equal(body.messages[1].content, '用户测试输入');
});

test('buildRequestBody：respond 协议生成 instructions 与 input 结构及 max_output_tokens', () => {
  const body = buildRequestBody('respond', 'deepseek-chat', '用户测试输入');
  assert.equal(body.model, 'deepseek-chat');
  assert.equal(body.instructions, SYSTEM_PROMPT);
  assert.equal(body.max_output_tokens, 1500);
  assert.ok(Array.isArray(body.input));
  assert.equal(body.input[0].type, 'message');
  assert.equal(body.input[0].role, 'user');
  assert.equal(body.input[0].content[0].type, 'input_text');
  assert.equal(body.input[0].content[0].text, '用户测试输入');
});

test('extractResponseContent：从 chat completions 响应中提取 choices[0].message.content', () => {
  const sample = {
    choices: [
      {
        message: {
          role: 'assistant',
          content: '{"summary":"测试摘要","keywords":["测试"],"status":"已完成","artifacts":[]}',
        },
      },
    ],
  };
  const text = extractResponseContent(sample);
  assert.equal(text, '{"summary":"测试摘要","keywords":["测试"],"status":"已完成","artifacts":[]}');
});

test('extractResponseContent：从 responses API output_text 中直接提取', () => {
  const sample = {
    output_text: '{"summary":"直接文本摘要","keywords":["直接"],"status":"已完成","artifacts":[]}',
  };
  const text = extractResponseContent(sample);
  assert.equal(text, '{"summary":"直接文本摘要","keywords":["直接"],"status":"已完成","artifacts":[]}');
});

test('extractResponseContent：从 responses API output 数组消息结构中聚合提取', () => {
  const sample = {
    output: [
      {
        type: 'message',
        role: 'assistant',
        content: [
          {
            type: 'output_text',
            text: '{"summary":"多块文本摘要",',
          },
          {
            type: 'output_text',
            text: '"keywords":["测试"],"status":"已完成","artifacts":[]}',
          },
        ],
      },
    ],
  };
  const text = extractResponseContent(sample);
  assert.equal(text, '{"summary":"多块文本摘要","keywords":["测试"],"status":"已完成","artifacts":[]}');
});

test('resolveApiConfig：根据环境变量与 URL 特征判定 chat 与 respond 协议', async () => {
  const origUrl = process.env.SESSION_RECALL_API_URL;
  const origProto = process.env.SESSION_RECALL_PROTOCOL;
  try {
    // 显式指定 chat 协议
    process.env.SESSION_RECALL_API_URL = 'https://mock.api.com/v1';
    process.env.SESSION_RECALL_PROTOCOL = 'chat';
    const cfgChat = await resolveApiConfig();
    assert.equal(cfgChat.protocol, 'chat');
    assert.equal(cfgChat.url, 'https://mock.api.com/v1/chat/completions');

    // 显式指定 respond 协议
    process.env.SESSION_RECALL_PROTOCOL = 'respond';
    const cfgRespond = await resolveApiConfig();
    assert.equal(cfgRespond.protocol, 'respond');
    assert.equal(cfgRespond.url, 'https://mock.api.com/v1/responses');

    // 协议值为 responses 时自适应规整为 respond
    process.env.SESSION_RECALL_PROTOCOL = 'responses';
    const cfgResponses = await resolveApiConfig();
    assert.equal(cfgResponses.protocol, 'respond');
    assert.equal(cfgResponses.url, 'https://mock.api.com/v1/responses');

    // URL 自带 /responses 时自动识别为 respond
    delete process.env.SESSION_RECALL_PROTOCOL;
    process.env.SESSION_RECALL_API_URL = 'https://custom.gateway.com/v1/responses';
    const cfgAutoRespond = await resolveApiConfig();
    assert.equal(cfgAutoRespond.protocol, 'respond');
    assert.equal(cfgAutoRespond.url, 'https://custom.gateway.com/v1/responses');

    // URL 自带 /chat/completions 时自动识别为 chat
    process.env.SESSION_RECALL_API_URL = 'https://custom.gateway.com/v1/chat/completions';
    const cfgAutoChat = await resolveApiConfig();
    assert.equal(cfgAutoChat.protocol, 'chat');
    assert.equal(cfgAutoChat.url, 'https://custom.gateway.com/v1/chat/completions');
  } finally {
    if (origUrl !== undefined) process.env.SESSION_RECALL_API_URL = origUrl;
    else delete process.env.SESSION_RECALL_API_URL;
    if (origProto !== undefined) process.env.SESSION_RECALL_PROTOCOL = origProto;
    else delete process.env.SESSION_RECALL_PROTOCOL;
  }
});
