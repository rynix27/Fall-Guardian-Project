/**
 * AWS Bedrock Integration
 * Uses Claude API to generate intelligent medical context and 911 dispatch scripts
 */

const axios = require('axios');
const logger = require('./logger');
require('dotenv').config();

class BedrockIntegration {
  constructor() {
    // No placeholder key: without a real key, no AI call is made.
    this.apiKey = process.env.ANTHROPIC_API_KEY || null;
    this.apiUrl = 'https://api.anthropic.com/v1/messages';
    this.model = 'claude-sonnet-4-6';
    
    logger.info('Bedrock Integration initialized (using Anthropic Claude)');
  }
  
  /**
   * Generate medical context based on biometric data
   * Used to provide intelligent context to 911 dispatchers
   */
  async generateMedicalContext(data) {
    const prompt = `
You are a medical AI assistant helping with emergency response. Based on the following biometric data from a fall detection system, provide a brief medical assessment for emergency dispatch.

PATIENT AGE: ${data.patient_age}
LOCATION: ${data.fall_location}
SENSOR DATA:
- Peak Acceleration: ${data.sensor_data?.peak_acceleration || 'unknown'} G-force
- Heart Rate Response: ${data.sensor_data?.heart_rate_change || 'unknown'} BPM change
- Detection Confidence: ${data.sensor_data?.confidence || 'unknown'}
- Immobility Duration: ${data.sensor_data?.immobility_duration || 'unknown'} seconds

Provide a 1-2 sentence medical assessment suitable for emergency dispatch. Focus on:
1. Likelihood of serious injury based on fall dynamics
2. Any age-related considerations
3. Recommended responder urgency level

Keep response brief and actionable for dispatchers.
`;

    try {
      const response = await this.callClaude(prompt);
      logger.info(`[BEDROCK] Medical context generated`);
      return response;
    } catch (error) {
      logger.error(`[BEDROCK] Medical context generation failed: ${error.message}`);
      // Fallback medical context
      return `[UNVERIFIED FALLBACK] Age ${data.patient_age}. Fall detected by sensor. No medical assessment was generated; responders must assess on arrival.`;
    }
  }
  
  /**
   * Generate intelligent 911 dispatch script
   * Creates contextual emergency dispatch message
   */
  async generate911Script(data) {
    const prompt = `
You are helping create a 911 dispatch script for an elderly fall emergency. Generate a concise, professional dispatch message.

PATIENT INFORMATION:
- Age: ${data.patient_age}
- Location: ${data.location}
- Fall Type: Automatic detection from wearable device
- Urgency Level: ${data.urgency}

MEDICAL CONTEXT: ${data.medical_context}

Generate a 2-3 sentence dispatch script that:
1. Confirms location and patient condition
2. Requests appropriate responders (ambulance, fire)
3. Mentions device-based automatic alert

Format: "This is an automated medical alert from Fall Guardian system. [Message]"
`;

    try {
      const response = await this.callClaude(prompt);
      logger.info(`[BEDROCK] 911 script generated`);
      return response;
    } catch (error) {
      logger.error(`[BEDROCK] 911 script generation failed: ${error.message}`);
      // Fallback script
      return `[UNVERIFIED FALLBACK] Automated alert from Fall Guardian. Fall detected by sensor at ${data.location}. Patient age ${data.patient_age}. Urgency flag: ${data.urgency}. No AI-generated script was produced.`;
    }
  }
  
  /**
   * Call Claude API (via Bedrock mock)
   * In production, would use actual AWS Bedrock SDK
   */
  async callClaude(prompt) {
    try {
      // For hackathon: use direct Claude API if key available
      if (this.apiKey) {
        return await this.callClaudeAPI(prompt);
      } else {
        // Fallback for testing
        logger.warn('[BEDROCK] No API key configured; returning unverified placeholder');
        return this.getMockResponse(prompt);
      }
    } catch (error) {
      logger.error(`[BEDROCK] API call failed: ${error.message}`);
      return this.getMockResponse(prompt);
    }
  }
  
  /**
   * Actually call Claude API
   */
  async callClaudeAPI(prompt) {
    try {
      const response = await axios.post(this.apiUrl, {
        model: this.model,
        max_tokens: 150,
        messages: [
          {
            role: 'user',
            content: prompt
          }
        ]
      }, {
        headers: {
          'x-api-key': this.apiKey,
          'anthropic-version': '2023-06-01'
        }
      });
      
      return response.data.content[0].text;
    } catch (error) {
      logger.error(`[BEDROCK] Claude API error: ${error.message}`);
      throw error;
    }
  }
  
  /**
   * Mock response for testing (when no API key)
   */
  getMockResponse(prompt) {
    // Deliberately contains no medical claims and no statement that help is coming.
    return '[UNVERIFIED PLACEHOLDER] No AI assessment is available. Sensor-detected fall; responders must assess on arrival.';
  }
}

module.exports = BedrockIntegration;
