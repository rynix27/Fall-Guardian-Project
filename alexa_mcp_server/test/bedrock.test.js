'use strict';
// Ensures no AI-looking medical text is produced when no API key is configured.
const test = require('node:test');
const assert = require('node:assert/strict');

delete process.env.ANTHROPIC_API_KEY;
const BedrockIntegration = require('../bedrock_integration');

test('without an API key, no key is invented', () => {
  const b = new BedrockIntegration();
  assert.equal(b.apiKey, null);
});

test('without an API key, the placeholder makes no medical claim', async () => {
  const b = new BedrockIntegration();
  const text = await b.callClaude('Give a medical context for this fall');
  assert.match(text, /UNVERIFIED/);
  assert.doesNotMatch(text, /paramedic|ETA|ambulance|help is on the way|injur/i);
});

test('fallback 911 script is labelled unverified', async () => {
  const b = new BedrockIntegration();
  b.callClaude = async () => { throw new Error('boom'); };
  const script = await b.generate911Script({ patient_age: 80, location: 'hall', urgency: 'high' });
  assert.match(script, /UNVERIFIED FALLBACK/);
  assert.doesNotMatch(script, /injury present|High priority dispatch recommended/);
});
