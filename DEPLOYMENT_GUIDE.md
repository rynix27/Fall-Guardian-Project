# Deployment guide

This guide separates what runs locally from what needs AWS. Nothing here has been deployed
to AWS by the build process. Follow the steps yourself, in your own account.

## 1. Local (no AWS, no credentials needed)

```bash
python3 -m venv venv && . venv/bin/activate
python -m pip install -r requirements.txt
python -m pytest -q                        # expect: 160 passed, 2 xfailed
python run_cv_demo.py                      # synthetic clip, scripted approval, simulated workflow
cd alexa_mcp_server && npm ci && npm run check && npm test   # expect: 17 pass
cd ../aws_backend/lambda && npm ci && npm test               # expect: 7 pass
```

Environment variables (copy `.env.example` to `.env`; never commit `.env`):

| Variable | Needed for | Required? |
|---|---|---|
| `FG_API_TOKEN` | Alexa HTTP API authentication | Yes, to call protected endpoints |
| `ALEXA_MCP_PORT` | Alexa HTTP API port | No (default 3000) |
| `FALL_GUARDIAN_DB` | SQLite file path | No (default `fall_guardian.db`) |
| `EMERGENCY_CONTACTS` | Contacts in INTEGRATION mode | Only if you use INTEGRATION mode |
| `FALLS_TABLE` | Lambda DynamoDB table | Only in AWS |
| `ANTHROPIC_API_KEY` | Legacy Bedrock module | No; without it a placeholder is used |

Start the HTTP API locally (development only, plain HTTP):

```bash
cd alexa_mcp_server
FG_API_TOKEN="$(python3 -c 'import secrets;print(secrets.token_urlsafe(32))')" npm start
```

## 2. AWS prerequisites

- An AWS account with billing alerts enabled.
- An IAM identity you control, with permission to create a DynamoDB table, an IAM role and policy, and a Lambda function (and a function URL if you want one).
- A region used consistently (examples use `us-east-1`).
- AWS CLI v2 installed and configured with **your** profile. Do not put keys in the repository.

## 3. AWS deployment

Follow `aws/DEPLOY.md` step by step. It creates:

- one DynamoDB table (`fall-guardian-events`, on-demand billing),
- one IAM role with the AWS-managed Lambda logging policy and an inline policy allowing `dynamodb:PutItem` on that one table,
- one Lambda function (Python 3.12),
- optionally one function URL (use `AWS_IAM` auth unless you have a reason to change it).

Expected cost: on-demand DynamoDB and Lambda charges are tiny at demo volume, but they are
not zero. Check the current AWS pricing pages before you deploy. This document does not
quote prices.

## 4. Verification

After deployment, run one invocation with a real event (command in `aws/DEPLOY.md`, step 5).
Then:

- `aws dynamodb scan` shows one item for the invocation.
- Repeating the identical request returns `duplicate: true` and the item count stays at one.
- A request with `decision` other than `APPROVED` returns 400 and writes nothing.

Save these outputs as evidence. Until you have them, the AWS component is **not verified**.

## 5. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `AccessDeniedException` on PutItem | Inline policy missing or wrong table ARN | Re-check the policy resource ARN and region |
| `ResourceNotFoundException` | Table name differs from `FALLS_TABLE` | Set the environment variable to the table name |
| Lambda returns 500 with `ProvisionedThroughputExceeded` | Throttling | Retry later; the idempotency key makes retries safe |
| Alexa API returns 503 | `FG_API_TOKEN` not set | Set it and restart the server |
| Alexa API returns 401 | Wrong or missing `Authorization: Bearer` header | Send the exact token |
| `npm test` says cannot find module | `npm ci` not run | Run `npm ci` in that folder |

## 6. Cleanup

```bash
aws lambda delete-function --function-name fall-guardian-event-handler --region us-east-1
aws dynamodb delete-table --table-name fall-guardian-events --region us-east-1
aws iam delete-role-policy --role-name fall-guardian-lambda-role --policy-name dynamo-put
aws iam detach-role-policy --role-name fall-guardian-lambda-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
aws iam delete-role --role-name fall-guardian-lambda-role
```

Also delete the CloudWatch log group `/aws/lambda/fall-guardian-event-handler` if you do not
want the logs kept. Confirm in the console that nothing remains.
