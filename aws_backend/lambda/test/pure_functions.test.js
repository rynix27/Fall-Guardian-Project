'use strict';
// Tests for pure helper functions. The handler itself is NOT invoked here
// because it calls DynamoDB, Bedrock and SNS.
const test = require('node:test');
const assert = require('node:assert/strict');
const { validateEvent, calculateSeverity } = require('../fall_detector_trigger');

test('valid event produces no validation errors', () => {
  const errs = validateEvent({ user_id: 'u-1', accelerometer: [1, 2, 3], heart_rate: 80 });
  assert.deepEqual(errs, []);
});

test('missing accelerometer is reported, not thrown', () => {
  const errs = validateEvent({ user_id: 'u-1' });
  assert.ok(errs.some(e => /accelerometer/i.test(e)));
});

test('null event is reported, not thrown', () => {
  assert.doesNotThrow(() => validateEvent(null));
  assert.ok(validateEvent(null).length > 0);
});

test('non-numeric accelerometer values are rejected', () => {
  const errs = validateEvent({ user_id: 'u-1', accelerometer: [1, 'x', 3] });
  assert.ok(errs.some(e => /numbers/i.test(e)));
});

test('non-string user_id is rejected', () => {
  const errs = validateEvent({ user_id: 42, accelerometer: [1, 2, 3] });
  assert.ok(errs.some(e => /user_id/i.test(e)));
});

test('severity is capped at 10 for large magnitudes', () => {
  assert.equal(calculateSeverity([100, 100, 100], null), 10);
});

test('elevated heart rate raises severity by one, capped at 10', () => {
  const base = calculateSeverity([10, 0, 0], null);      // magnitude 10 -> 5
  const raised = calculateSeverity([10, 0, 0], 120);
  assert.equal(raised, base + 1);
  assert.equal(calculateSeverity([100, 0, 0], 120), 10);
});
