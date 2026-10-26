/**
 * Fall Guardian: Alexa+ MCP Server
 * 
 * Coordinates emergency response when a fall is detected:
 * - Calls 911 with medical context via AWS Bedrock
 * - Contacts emergency contacts
 * - Provides voice confirmation options
 * - Integrates with Fire TV alerts
 */

const express = require('express');
const crypto = require('crypto');
const axios = require('axios');
require('dotenv').config();

const app = express();
// Request body limit: prevents oversized payloads.
app.use(express.json({ limit: '16kb' }));

// JSON parse and size errors become 400/413 instead of stack traces.
app.use((err, req, res, next) => {
  if (err && err.type === 'entity.too.large') {
    return res.status(413).json({ success: false, error: 'Request body too large' });
  }
  if (err && err.type === 'entity.parse.failed') {
    return res.status(400).json({ success: false, error: 'Request body is not valid JSON' });
  }
  return next(err);
});

/**
 * Bearer-token authentication for sensitive endpoints.
 * Reads FG_API_TOKEN at request time. If unset, sensitive endpoints FAIL CLOSED (503).
 * The token value is never logged.
 */
function requireApiToken(req, res, next) {
  const expected = process.env.FG_API_TOKEN;
  if (!expected) {
    return res.status(503).json({ success: false, error: 'Server has no API token configured' });
  }
  const header = req.get('Authorization') || '';
  const match = /^Bearer (.+)$/.exec(header);
  const given = match ? match[1] : '';
  const a = Buffer.from(given);
  const b = Buffer.from(expected);
  const ok = a.length === b.length && crypto.timingSafeEqual(a, b);
  if (!ok) {
    logger.warn(`[AUTH] Rejected request to ${req.path}`);
    return res.status(401).json({ success: false, error: 'Unauthorized' });
  }
  return next();
}

const logger = require('./logger');
const EmergencyCoordinator = require('./emergency_coordinator');
const BedrockIntegration = require('./bedrock_integration');

// Initialize services
const emergency = new EmergencyCoordinator();
const bedrock = new BedrockIntegration();

// MCP Server configuration
const MCP_VERSION = '2025-11-25';
const PORT = process.env.ALEXA_MCP_PORT || 3000;

/**
 * MCP Tool Definitions
 * These define what Alexa+ can ask this server to do
 */
const MCP_TOOLS = [
  {
    name: 'detect_fall_emergency',
    description: 'Process fall detection alert and coordinate emergency response',
    inputSchema: {
      type: 'object',
      properties: {
        patient_id: {
          type: 'string',
          description: 'Unique patient identifier'
        },
        patient_age: {
          type: 'number',
          description: 'Patient age in years'
        },
        fall_location: {
          type: 'string',
          description: 'Location of fall (address or room)'
        },
        confidence: {
          type: 'number',
          description: 'Fall detection confidence (0-1)'
        },
        sensor_data: {
          type: 'object',
          description: 'Biometric data from Bee device'
        }
      },
      required: ['patient_id', 'fall_location', 'confidence']
    }
  },
  {
    name: 'call_911',
    description: 'Call emergency services with medical context',
    inputSchema: {
      type: 'object',
      properties: {
        patient_id: { type: 'string' },
        location: { type: 'string' },
        medical_context: { type: 'string' },
        urgency: { type: 'string', enum: ['critical', 'high', 'medium'] }
      },
      required: ['patient_id', 'location', 'urgency']
    }
  },
  {
    name: 'contact_family',
    description: 'Contact emergency contacts immediately',
    inputSchema: {
      type: 'object',
      properties: {
        patient_id: { type: 'string' },
        alert_type: { type: 'string' },
        location: { type: 'string' }
      },
      required: ['patient_id', 'alert_type']
    }
  },
  {
    name: 'voice_confirmation',
    description: 'Ask patient via voice to confirm fall or dismiss alert',
    inputSchema: {
      type: 'object',
      properties: {
        patient_id: { type: 'string' },
        device_id: { type: 'string' }
      },
      required: ['patient_id', 'device_id']
    }
  }
];

/**
 * MCP Tool Handler
 * Routes incoming tool requests to appropriate handlers
 */
async function handleMCPTool(toolName, toolInput) {
  logger.info(`[MCP] Handling tool: ${toolName}`);
  
  try {
    switch (toolName) {
      case 'detect_fall_emergency':
        return await handleFallDetection(toolInput);
      case 'call_911':
        return await handleEmergencyCall(toolInput);
      case 'contact_family':
        return await handleFamilyContact(toolInput);
      case 'voice_confirmation':
        return await handleVoiceConfirmation(toolInput);
      default:
        throw new Error(`Unknown tool: ${toolName}`);
    }
  } catch (error) {
    logger.error(`[MCP] Tool error: ${error.message}`);
    return {
      success: false,
      error: error.message
    };
  }
}

/**
 * Handle fall detection emergency
 * Orchestrates the full emergency response workflow
 */
async function handleFallDetection(data) {
  logger.warn(`[EMERGENCY] Fall detected for patient ${data.patient_id}`);
  logger.warn(`Location: ${data.fall_location}, Confidence: ${data.confidence}`);
  
  const emergencyId = emergency.createEmergencyRecord({
    patient_id: data.patient_id,
    type: 'fall',
    location: data.fall_location,
    confidence: data.confidence,
    timestamp: new Date().toISOString(),
    sensor_data: data.sensor_data
  });
  
  try {
    // Step 1: Generate medical context using Bedrock AI
    const medicalContext = await bedrock.generateMedicalContext({
      patient_age: data.patient_age,
      sensor_data: data.sensor_data,
      location: data.fall_location
    });
    
    // Step 2: Initiate 911 call
    const callResult = await handleEmergencyCall({
      patient_id: data.patient_id,
      location: data.fall_location,
      medical_context: medicalContext,
      urgency: data.confidence > 0.9 ? 'critical' : 'high'
    });
    
    // Step 3: Contact family members
    const familyResult = await handleFamilyContact({
      patient_id: data.patient_id,
      alert_type: 'FALL_EMERGENCY',
      location: data.fall_location
    });
    
    // Step 4: Voice confirmation (ask if patient needs help)
    // This happens in parallel, no waiting
    const voiceResult = await handleVoiceConfirmation({
      patient_id: data.patient_id,
      device_id: data.device_id || 'default'
    });
    
    // Step 5: Unlock smart lock via Ring (handled by AWS Lambda, not here)
    // Fire TV will be updated via SNS notification
    
    // Report each channel's real state. Nothing here is a confirmed delivery:
    // this server has no live 911, SMS, smart-lock or Fire TV integration yet.
    return {
      success: false,
      status: 'SIMULATED_ONLY',
      emergency_id: emergencyId,
      channels: {
        dispatch_911: callResult.status,
        family_notification: familyResult.status,
        voice_confirmation: voiceResult.status,
        smart_lock: 'NOT_CONFIGURED',
        fire_tv_alert: 'NOT_CONFIGURED'
      },
      note: 'No real emergency service was contacted. See channels for per-action status.',
      timeline: {
        detected_at: new Date().toISOString(),
        dispatch_simulated_at: callResult.timestamp,
        family_logged_at: familyResult.timestamp
      }
    };
    
  } catch (error) {
    logger.error(`[EMERGENCY] Workflow failed: ${error.message}`);
    // No automated emergency action is confirmed. A person must escalate.
    return {
      success: false,
      status: 'FAILED',
      emergency_id: emergencyId,
      message: 'Automated emergency workflow failed. No emergency action is confirmed; escalate manually.'
    };
  }
}

/**
 * Call 911 with medical context
 */
async function handleEmergencyCall(data) {
  logger.warn(`[911 DISPATCH] Calling emergency services for ${data.patient_id}`);
  logger.warn(`Location: ${data.location}`);
  logger.warn(`Urgency: ${data.urgency}`);
  
  try {
    // Generate intelligent 911 dispatch message using Bedrock
    const dispatchMessage = await bedrock.generate911Script({
      patient_age: data.patient_age,
      location: data.location,
      medical_context: data.medical_context,
      urgency: data.urgency
    });
    
    logger.info(`[911] Generated script:\n${dispatchMessage}`);
    
    // In production, this would integrate with:
    // - Real 911 API (varies by region)
    // - Twilio for voice calling
    // - Emergency dispatcher routing
    
    // No 911 integration exists in this server. Nothing is dispatched.
    const callResponse = {
      success: false,
      status: 'SIMULATED',
      dispatched: false,
      timestamp: new Date().toISOString(),
      dispatcher_id: null,
      units_dispatched: [],
      message: dispatchMessage
    };
    
    emergency.updateEmergencyRecord(data.patient_id, {
      dispatch_status: 'SIMULATED',
      dispatcher_contacted: false
    });
    
    return callResponse;
    
  } catch (error) {
    logger.error(`[911] Call failed: ${error.message}`);
    return {
      success: false,
      status: 'FAILED',
      dispatched: false,
      message: '911 call NOT placed. Escalate manually.'
    };
  }
}

/**
 * Contact family members
 */
async function handleFamilyContact(data) {
  logger.info(`[FAMILY] Notifying emergency contacts for ${data.patient_id}`);
  
  try {
    // Get patient's emergency contacts (from database)
    const contacts = await emergency.getEmergencyContacts(data.patient_id);
    
    const notifications = [];
    
    // Send SMS to each contact
    for (const contact of contacts) {
      const smsMessage = `ALERT: ${contact.relationship} may have fallen at ${data.location}. Please check on them.`;
      
      // No SMS provider is wired up. The message is logged, not delivered.
      logger.info(`[SMS - NOT SENT, no provider] → ${contact.phone}: ${smsMessage}`);
      notifications.push({
        contact_id: contact.id,
        contact_name: contact.name,
        method: 'SMS',
        status: 'LOGGED_ONLY',
        delivered: false,
        timestamp: new Date().toISOString()
      });
    }
    
    emergency.updateEmergencyRecord(data.patient_id, {
      family_notified: false,
      notifications_logged: notifications.length
    });
    
    return {
      success: false,
      status: 'LOGGED_ONLY',
      timestamp: new Date().toISOString(),
      contacts_logged: notifications.length,
      contacts_notified: 0,
      notifications: notifications
    };
    
  } catch (error) {
    logger.error(`[FAMILY] Contact failed: ${error.message}`);
    return {
      success: false,
      status: 'FAILED',
      message: 'Could not log family notifications'
    };
  }
}

/**
 * Request voice confirmation from patient
 * "Did you fall? Please say YES or NO"
 */
async function handleVoiceConfirmation(data) {
  logger.info(`[VOICE] Requesting confirmation from patient ${data.patient_id}`);
  
  // No Alexa voice integration exists yet. Nothing is spoken to the patient
  // and no response can be received. Do not treat this as a confirmation.
  logger.warn(`[VOICE - NOT IMPLEMENTED] Patient ${data.patient_id} was not prompted.`);
  return {
    success: false,
    status: 'NOT_IMPLEMENTED',
    prompt_sent: false,
    awaiting_response: false,
    message: 'Voice confirmation is not implemented; no prompt was sent'
  };
}

/**
 * REST API Endpoints
 */

// Health check
app.get('/health', (req, res) => {
  res.json({
    status: 'healthy',
    service: 'Fall Guardian Alexa+ MCP',
    version: MCP_VERSION,
    uptime: process.uptime()
  });
});

// Get MCP tool definitions
app.get('/tools', (req, res) => {
  res.json({
    version: MCP_VERSION,
    tools: MCP_TOOLS
  });
});

// Handle MCP tool requests (authenticated, input validated before dispatch)
const KNOWN_TOOLS = new Set(MCP_TOOLS.map(t => t.name));
app.post('/execute_tool', requireApiToken, async (req, res) => {
  const body = req.body || {};
  const toolName = body.tool_name;
  const toolInput = body.tool_input;

  if (typeof toolName !== 'string' || !KNOWN_TOOLS.has(toolName)) {
    return res.status(400).json({ success: false, error: 'Unknown or missing tool_name' });
  }
  if (toolInput === null || typeof toolInput !== 'object' || Array.isArray(toolInput)) {
    return res.status(400).json({ success: false, error: 'tool_input must be a JSON object' });
  }

  // Do not log tool_input: it can contain patient information.
  logger.info(`[API] Tool request accepted: ${toolName}`);
  try {
    const result = await handleMCPTool(toolName, toolInput);
    return res.json(result);
  } catch (err) {
    logger.error(`[API] Tool failed: ${toolName}: ${err.message}`);
    return res.status(500).json({ success: false, error: 'Tool execution failed' });
  }
});

// Emergency status endpoint (authenticated: contains patient information)
app.get('/emergencies/:patient_id', requireApiToken, (req, res) => {
  const status = emergency.getEmergencyStatus(req.params.patient_id);
  res.json(status || { error: 'No emergency found' });
});

// Start the server only when run directly (npm start / node index.js).
if (require.main === module) {
  app.listen(PORT, () => {
    logger.info(`🚨 Fall Guardian MCP Server listening on port ${PORT}`);
    logger.info(`MCP Version: ${MCP_VERSION}`);
    logger.info(`Available tools: ${MCP_TOOLS.length}`);
    logger.info('Ready to coordinate emergency response...');
  });
}

module.exports = { app, handleMCPTool, MCP_TOOLS };
