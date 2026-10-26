'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const EmergencyCoordinator = require('../emergency_coordinator');

test('new emergency record starts ACTIVE with dispatch PENDING and nothing confirmed', () => {
  const c = new EmergencyCoordinator();
  const id = c.createEmergencyRecord({ patient_id: 'p1', type: 'fall', location: 'kitchen' });
  const rec = c.getEmergencyStatus('p1');
  assert.equal(rec.id, id);
  assert.equal(rec.status, 'ACTIVE');
  assert.equal(rec.dispatch_status, 'PENDING');
  assert.equal(rec.family_notified, false);
  assert.equal(rec.smart_lock_unlocked, false);
});

test('update applies only to the active record for that patient', () => {
  const c = new EmergencyCoordinator();
  c.createEmergencyRecord({ patient_id: 'p1', type: 'fall' });
  const updated = c.updateEmergencyRecord('p1', { dispatch_status: 'SIMULATED' });
  assert.equal(updated.dispatch_status, 'SIMULATED');
  assert.equal(c.updateEmergencyRecord('nobody', { dispatch_status: 'X' }), null);
});

test('resolving an emergency removes it from active list', () => {
  const c = new EmergencyCoordinator();
  c.createEmergencyRecord({ patient_id: 'p1', type: 'fall' });
  assert.equal(c.getActiveEmergencies().length, 1);
  const resolved = c.resolveEmergency('p1');
  assert.equal(resolved.status, 'RESOLVED');
  assert.ok(resolved.resolved_at);
  assert.equal(c.getActiveEmergencies().length, 0);
  assert.equal(c.getEmergencyStatus('p1'), null);
});

test('contacts are the documented mock list (not real data)', async () => {
  const c = new EmergencyCoordinator();
  const contacts = await c.getEmergencyContacts('p1');
  assert.equal(contacts.length, 2);
  assert.ok(contacts.every(x => /^\+1-555-/.test(x.phone)), 'mock contacts use reserved 555 numbers');
});
