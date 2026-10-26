/**
 * Emergency Coordinator
 * Manages emergency records, contacts, and status tracking
 */

const logger = require('./logger');
const uuid = require('crypto').randomUUID || (() => Math.random().toString(36).substr(2, 9));

class EmergencyCoordinator {
  constructor() {
    // In-memory store (in production, use DynamoDB)
    this.emergencies = new Map();
    this.contacts = new Map();
    
    logger.info('Emergency Coordinator initialized');
  }
  
  /**
   * Create a new emergency record
   */
  createEmergencyRecord(data) {
    const emergencyId = `EMG-${uuid()}`;
    
    const record = {
      id: emergencyId,
      patient_id: data.patient_id,
      type: data.type, // 'fall', 'help_button', etc.
      location: data.location,
      confidence: data.confidence,
      timestamp: data.timestamp,
      sensor_data: data.sensor_data,
      status: 'ACTIVE',
      dispatch_status: 'PENDING',
      family_notified: false,
      responder_eta: null,
      responder_contacted: null,
      voice_confirmation: null,
      smart_lock_unlocked: false,
      resolved_at: null
    };
    
    this.emergencies.set(emergencyId, record);
    logger.info(`[EMERGENCY RECORD] Created: ${emergencyId}`);
    
    return emergencyId;
  }
  
  /**
   * Update an emergency record
   */
  updateEmergencyRecord(patientId, updates) {
    // Find emergency by patient ID
    for (const [id, record] of this.emergencies) {
      if (record.patient_id === patientId && record.status === 'ACTIVE') {
        Object.assign(record, updates);
        logger.info(`[EMERGENCY RECORD] Updated: ${id}`);
        return record;
      }
    }
    
    logger.warn(`[EMERGENCY RECORD] No active emergency found for patient ${patientId}`);
    return null;
  }
  
  /**
   * Get emergency status
   */
  getEmergencyStatus(patientId) {
    for (const [id, record] of this.emergencies) {
      if (record.patient_id === patientId && record.status === 'ACTIVE') {
        return record;
      }
    }
    return null;
  }
  
  /**
   * Get emergency contacts for a patient
   * In production, fetch from database
   */
  async getEmergencyContacts(patientId) {
    // Mock data for testing
    // In production: query DynamoDB with patient's contact list
    
    return [
      {
        id: 'contact-1',
        patient_id: patientId,
        name: 'John Smith',
        relationship: 'Son',
        phone: '+1-555-0100',
        email: 'john@example.com',
        priority: 1
      },
      {
        id: 'contact-2',
        patient_id: patientId,
        name: 'Sarah Smith',
        relationship: 'Daughter',
        phone: '+1-555-0101',
        email: 'sarah@example.com',
        priority: 2
      }
    ];
  }
  
  /**
   * Resolve emergency (emergency is over)
   */
  resolveEmergency(patientId) {
    for (const [id, record] of this.emergencies) {
      if (record.patient_id === patientId && record.status === 'ACTIVE') {
        record.status = 'RESOLVED';
        record.resolved_at = new Date().toISOString();
        logger.info(`[EMERGENCY RECORD] Resolved: ${id}`);
        return record;
      }
    }
  }
  
  /**
   * Get all active emergencies
   */
  getActiveEmergencies() {
    const active = [];
    for (const [id, record] of this.emergencies) {
      if (record.status === 'ACTIVE') {
        active.push(record);
      }
    }
    return active;
  }
}

module.exports = EmergencyCoordinator;
