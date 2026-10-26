# Configuration

Only the settings below are read by the code in this repository.

| Variable | Read by | Default | Purpose |
|---|---|---|---|
| `FG_API_TOKEN` | `alexa_mcp_server/index.js` | unset (sensitive endpoints return 503) | Bearer token for `/execute_tool` and `/emergencies/:id` |
| `ALEXA_MCP_PORT` | `alexa_mcp_server/index.js` | `3000` | HTTP port |
| `FALL_GUARDIAN_DB` | `database_setup.py` | `fall_guardian.db` | SQLite file path |
| `EMERGENCY_CONTACTS` | `emergency_response_service.py` | empty | Contacts for INTEGRATION-mode family notification. Empty means `NOT_CONFIGURED`. |
| `FALLS_TABLE` | `aws/fall_event_handler.py`, `aws_backend/lambda/fall_detector_trigger.js` | `fall-guardian-events` / `fall-events` | DynamoDB table name |
| `ANTHROPIC_API_KEY` | `alexa_mcp_server/bedrock_integration.js` | unset | Enables the AI call in the legacy module. Unset means placeholder only. |
| `LOG_LEVEL` | `alexa_mcp_server/logger.js` | `INFO` | Node logging verbosity |
| `SNS_TOPIC_ARN` | `aws_backend/lambda/fall_detector_trigger.js` | unset | If unset, the legacy Lambda reports `NOT_CONFIGURED` for notification |

Not read by any code (do not expect an effect): Ring and Bee API keys, SMS-provider credentials,
HIPAA or encryption switches.

Secrets belong in a secret manager or the deployment environment, never in files committed to the repository.
