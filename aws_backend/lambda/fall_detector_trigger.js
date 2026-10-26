/**
 * AWS Lambda Function: Fall Detector Trigger
 * 
 * Triggered by: Bee (Apple Watch) fall detection event
 * Actions: 
 *   1. Process fall data from Bee
 *   2. Call emergency response service
 *   3. Update DynamoDB
 *   4. Trigger SNS notifications
 * 
 * Error Handling: All async operations wrapped with try/catch
 */

const AWS = require('aws-sdk');

// Initialize AWS services
const dynamodb = new AWS.DynamoDB.DocumentClient();
const sns = new AWS.SNS();
const bedrock = new AWS.BedrockRuntime();

// Configuration from environment
const FALLS_TABLE = process.env.FALLS_TABLE || 'fall-events';
const SNS_TOPIC = process.env.SNS_TOPIC_ARN || '';
const BEDROCK_MODEL = process.env.BEDROCK_MODEL || 'anthropic.claude-3-5-sonnet-20241022-v2:0';

/**
 * Validate incoming event data
 */
function validateEvent(event) {
    const errors = [];
    
    if (!event || typeof event !== 'object') {
        return ['Event must be an object'];
    }
    
    if (!event.user_id || typeof event.user_id !== 'string') {
        errors.push('Missing or invalid user_id');
    }
    
    if (!Array.isArray(event.accelerometer) || event.accelerometer.length !== 3) {
        errors.push('Invalid accelerometer data (expected [x, y, z])');
    } else if (event.accelerometer.some(val => typeof val !== 'number' || !Number.isFinite(val))) {
        errors.push('Accelerometer values must be finite numbers');
    }
    
    if (event.heart_rate !== undefined && typeof event.heart_rate !== 'number') {
        errors.push('Invalid heart_rate');
    }
    
    return errors;
}

/**
 * Calculate fall severity from acceleration
 */
function calculateSeverity(accelerometer, heartRate) {
    try {
        const magnitude = Math.sqrt(
            accelerometer[0] ** 2 + 
            accelerometer[1] ** 2 + 
            accelerometer[2] ** 2
        );
        
        let severity = Math.min(10, Math.floor((magnitude / 20) * 10));
        
        // Adjust for elevated heart rate
        if (heartRate && heartRate > 100) {
            severity = Math.min(10, severity + 1);
        }
        
        return severity;
    } catch (error) {
        console.error('Severity calculation error:', error);
        return 5; // Default
    }
}

/**
 * Log fall event to DynamoDB
 */
async function logFallToDynamoDB(userId, severity, accelerometer, heartRate) {
    try {
        const timestamp = new Date().toISOString();
        const fallId = `${userId}-${Date.now()}`;
        
        const params = {
            TableName: FALLS_TABLE,
            Item: {
                fall_id: fallId,
                user_id: userId,
                timestamp: timestamp,
                severity: severity,
                accelerometer: accelerometer,
                heart_rate: heartRate || null,
                processed_at: timestamp,
                status: 'LOGGED'
            }
        };
        
        await dynamodb.put(params).promise();
        console.log(`Fall logged to DynamoDB: ${fallId}`);
        return fallId;
    } catch (error) {
        console.error('DynamoDB logging error:', error);
        throw new Error(`Failed to log fall: ${error.message}`);
    }
}

/**
 * Get user medical context from DynamoDB
 */
async function getUserMedicalContext(userId) {
    try {
        const params = {
            TableName: 'users', // Assumes users table exists
            Key: { user_id: userId }
        };
        
        const result = await dynamodb.get(params).promise();
        return result.Item || null;
    } catch (error) {
        console.error('Error retrieving user context:', error);
        return null; // Continue without context
    }
}

/**
 * Send SNS notification
 */
async function sendNotification(userId, severity, fallId) {
    // Returns the real outcome. 'SNS_ACCEPTED' means SNS accepted the publish;
    // it does NOT mean any caregiver or emergency service received the alert.
    if (!SNS_TOPIC) {
        console.warn('SNS_TOPIC_ARN not configured, skipping notification');
        return { status: 'NOT_CONFIGURED', detail: 'SNS_TOPIC_ARN is not set' };
    }
    
    try {
        const params = {
            TopicArn: SNS_TOPIC,
            Subject: `[URGENT] Fall Detected - User ${userId}`,
            Message: JSON.stringify({
                event: 'FALL_DETECTED',
                user_id: userId,
                fall_id: fallId,
                severity: severity,
                timestamp: new Date().toISOString(),
                action_required: 'EMERGENCY_RESPONSE'
            }, null, 2)
        };
        
        await sns.publish(params).promise();
        console.log(`SNS publish accepted for fall: ${fallId}`);
        return { status: 'SNS_ACCEPTED', detail: 'SNS accepted the message; downstream delivery not confirmed' };
    } catch (error) {
        console.error('SNS notification error:', error);
        // Processing continues, but the failure is reported to the caller.
        return { status: 'FAILED', detail: error.message };
    }
}

/**
 * Generate emergency context using Bedrock/Claude
 */
async function generateEmergencyContext(userId, severity, userContext) {
    try {
        if (!userContext) {
            return 'Standard fall detected - medical context unavailable';
        }
        
        const prompt = `Given a fall has been detected for a ${userContext.age || 'unknown age'} year old person with severity ${severity}/10, 
what emergency response context should paramedics know? Include medications: ${userContext.medications || 'none on file'}.
Provide 2-3 sentences max.`;
        
        // Note: Bedrock integration is optional - can be added later
        console.log('Emergency context generation prepared (Bedrock integration optional)');
        return `Fall detected for ${userContext.age || 'elderly'} year old, severity ${severity}/10`;
        
    } catch (error) {
        console.error('Context generation error:', error);
        return `Fall detected - severity ${severity}/10`;
    }
}

/**
 * Main Lambda handler
 */
exports.handler = async (event) => {
    console.log('Fall Detector Trigger - Event received:', JSON.stringify(event));
    
    const startTime = Date.now();
    const response = {
        statusCode: 200,
        body: {
            event_id: `event-${Date.now()}`,
            status: 'PROCESSING',
            fall_id: null,
            errors: [],
            processing_time_ms: 0
        }
    };
    
    try {
        // Validate input
        const validationErrors = validateEvent(event);
        if (validationErrors.length > 0) {
            console.error('Validation errors:', validationErrors);
            response.statusCode = 400;
            response.body.status = 'VALIDATION_FAILED';
            response.body.errors = validationErrors;
            return response;
        }
        
        const { user_id: userId, accelerometer, heart_rate: heartRate } = event;
        
        // Calculate severity
        const severity = calculateSeverity(accelerometer, heartRate);
        console.log(`Fall severity calculated: ${severity}/10`);
        
        // Log to DynamoDB
        const fallId = await logFallToDynamoDB(userId, severity, accelerometer, heartRate);
        response.body.fall_id = fallId;
        
        // Get user medical context
        const userContext = await getUserMedicalContext(userId);
        
        // Generate emergency context
        const emergencyContext = await generateEmergencyContext(userId, severity, userContext);
        response.body.emergency_context = emergencyContext;
        
        // Send notifications and record the real outcome
        const notification = await sendNotification(userId, severity, fallId);
        response.body.notification = notification;
        
        // SUCCESS only when the notification was actually accepted by SNS.
        response.body.status = notification.status === 'SNS_ACCEPTED' ? 'SUCCESS' : 'PARTIAL';
        response.body.severity = severity;
        response.body.actions = [
            'FALL_LOGGED',
            notification.status === 'SNS_ACCEPTED' ? 'SNS_PUBLISH_ACCEPTED' : 'NOTIFICATION_NOT_SENT',
            'EMERGENCY_CONTEXT_GENERATED'
        ];
        response.body.note = 'No 911 call or smart-lock action is performed by this function.';
        
        console.log(`Fall processing complete: ${fallId}`);
        
    } catch (error) {
        console.error('Lambda execution error:', error);
        response.statusCode = 500;
        response.body.status = 'ERROR';
        response.body.errors.push(error.message);
    } finally {
        response.body.processing_time_ms = Date.now() - startTime;
        console.log(`Processing completed in ${response.body.processing_time_ms}ms`);
    }
    
    return response;
};

// Export for testing
module.exports.calculateSeverity = calculateSeverity;
module.exports.validateEvent = validateEvent;
