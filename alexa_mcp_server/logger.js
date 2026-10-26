/**
 * Simple Logger for Fall Guardian
 */

const LOG_LEVEL = process.env.LOG_LEVEL || 'INFO';

const LEVELS = {
  DEBUG: 0,
  INFO: 1,
  WARN: 2,
  ERROR: 3
};

function formatTimestamp() {
  const now = new Date();
  return now.toISOString();
}

function formatMessage(level, message) {
  return `[${formatTimestamp()}] [${level}] ${message}`;
}

function shouldLog(level) {
  return LEVELS[level] >= LEVELS[LOG_LEVEL];
}

const logger = {
  debug: (msg) => {
    if (shouldLog('DEBUG')) console.log(formatMessage('DEBUG', msg));
  },
  
  info: (msg) => {
    if (shouldLog('INFO')) console.log(formatMessage('INFO', msg));
  },
  
  warn: (msg) => {
    if (shouldLog('WARN')) console.warn(formatMessage('WARN', msg));
  },
  
  error: (msg) => {
    if (shouldLog('ERROR')) console.error(formatMessage('ERROR', msg));
  }
};

module.exports = logger;
