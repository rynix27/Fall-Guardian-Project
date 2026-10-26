'use strict';
// HTTP-level tests against the real Express app on an ephemeral port.
// The token is read at request time, so tests can set and clear it.
const test = require('node:test');
const assert = require('node:assert/strict');

const TOKEN = 'test-token-0123456789abcdef';
const { app } = require('../index');

let server;
let base;

test.before(async () => {
  await new Promise((resolve) => {
    server = app.listen(0, '127.0.0.1', () => {
      base = `http://127.0.0.1:${server.address().port}`;
      resolve();
    });
  });
});

test.after(async () => {
  delete process.env.FG_API_TOKEN;
  await new Promise((resolve) => server.close(resolve));
});

async function call(path, { method = 'GET', headers = {}, body } = {}) {
  const opts = { method, headers: { ...headers } };
  if (body !== undefined) {
    opts.body = typeof body === 'string' ? body : JSON.stringify(body);
    opts.headers['Content-Type'] = 'application/json';
  }
  const res = await fetch(base + path, opts);
  const text = await res.text();
  let json = null;
  try { json = JSON.parse(text); } catch (_) { /* not JSON */ }
  return { status: res.status, json, text };
}

const auth = { Authorization: `Bearer ${TOKEN}` };

test('health and tool list stay public', async () => {
  const h = await call('/health');
  assert.equal(h.status, 200);
  assert.equal(h.json.status, 'healthy');
  const t = await call('/tools');
  assert.equal(t.status, 200);
  assert.ok(Array.isArray(t.json.tools) && t.json.tools.length > 0);
});

test('execute_tool without a token is rejected with 401', async () => {
  process.env.FG_API_TOKEN = TOKEN;
  const r = await call('/execute_tool', { method: 'POST',
    body: { tool_name: 'call_911', tool_input: {} } });
  assert.equal(r.status, 401);
});

test('execute_tool with a wrong token is rejected with 401', async () => {
  process.env.FG_API_TOKEN = TOKEN;
  const r = await call('/execute_tool', { method: 'POST',
    headers: { Authorization: 'Bearer wrong-token-value-xxxxxxxxxx' },
    body: { tool_name: 'call_911', tool_input: {} } });
  assert.equal(r.status, 401);
});

test('no configured token fails closed with 503, even if a token is sent', async () => {
  delete process.env.FG_API_TOKEN;
  const r = await call('/execute_tool', { method: 'POST', headers: auth,
    body: { tool_name: 'call_911', tool_input: {} } });
  assert.equal(r.status, 503);
  const e = await call('/emergencies/p1', { headers: auth });
  assert.equal(e.status, 503);
});

test('unknown tool name is rejected before dispatch', async () => {
  process.env.FG_API_TOKEN = TOKEN;
  const r = await call('/execute_tool', { method: 'POST', headers: auth,
    body: { tool_name: 'rm_rf_root', tool_input: {} } });
  assert.equal(r.status, 400);
});

test('tool_input must be an object', async () => {
  process.env.FG_API_TOKEN = TOKEN;
  const r = await call('/execute_tool', { method: 'POST', headers: auth,
    body: { tool_name: 'call_911', tool_input: 'not-an-object' } });
  assert.equal(r.status, 400);
});

test('malformed JSON returns 400 with a safe message', async () => {
  process.env.FG_API_TOKEN = TOKEN;
  const r = await call('/execute_tool', { method: 'POST', headers: auth, body: '{bad json' });
  assert.equal(r.status, 400);
  assert.doesNotMatch(r.text, /SyntaxError|at JSON|stack/i);
});

test('oversized body returns 413', async () => {
  process.env.FG_API_TOKEN = TOKEN;
  const big = { tool_name: 'call_911', tool_input: { pad: 'x'.repeat(20000) } };
  const r = await call('/execute_tool', { method: 'POST', headers: auth, body: big });
  assert.equal(r.status, 413);
});

test('valid authenticated call returns an honest simulated result', async () => {
  process.env.FG_API_TOKEN = TOKEN;
  const r = await call('/execute_tool', { method: 'POST', headers: auth,
    body: { tool_name: 'call_911', tool_input: { patient_id: 'p-test-1', location: 'kitchen' } } });
  assert.equal(r.status, 200);
  // 911 is never reported as dispatched by this server.
  assert.notEqual(r.json.dispatched, true);
  assert.equal(r.json.status, 'SIMULATED');
});

test('emergency status requires the token', async () => {
  process.env.FG_API_TOKEN = TOKEN;
  const r = await call('/emergencies/p-test-1');
  assert.equal(r.status, 401);
  const ok = await call('/emergencies/p-test-1', { headers: auth });
  assert.equal(ok.status, 200);
});
