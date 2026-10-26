# Deploying the AWS component (you run these; not executed in the build environment)

The Lambda stores only human-approved fall events in DynamoDB. It does not contact
emergency services. Use an account where you can create IAM roles, DynamoDB tables,
Lambda functions and (optionally) a function URL. Free-tier credits cover this.

Region below is an example; use one region throughout.

```bash
export AWS_REGION=us-east-1
export TABLE=fall-guardian-events
export FUNC=fall-guardian-event-handler
export ROLE=fall-guardian-lambda-role
```

## 0. Requirements

Every request must include an `idempotency_key` of 8–128 characters (letters, digits, `-`, `_`).
Retries with the same key do not create a second incident.

## 1. Create the DynamoDB table
```bash
aws dynamodb create-table \
  --table-name $TABLE \
  --attribute-definitions AttributeName=incident_id,AttributeType=S \
  --key-schema AttributeName=incident_id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region $AWS_REGION
```

## 2. Create an execution role
Save this as `trust.json`:
```json
{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}
```
Then:
```bash
aws iam create-role --role-name $ROLE --assume-role-policy-document file://trust.json
aws iam attach-role-policy --role-name $ROLE \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
```
Save this as `dynamo-write.json` (replace ACCOUNT_ID and region):
```json
{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":["dynamodb:PutItem"],
 "Resource":"arn:aws:dynamodb:REGION:ACCOUNT_ID:table/fall-guardian-events"}]}
```
```bash
aws iam put-role-policy --role-name $ROLE --policy-name dynamo-put \
  --policy-document file://dynamo-write.json
```
Wait about 10 seconds for IAM to propagate before the next step.

## 3. Package and create the function
```bash
cd aws
zip -r handler.zip fall_event_handler.py
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
aws lambda create-function \
  --function-name $FUNC \
  --runtime python3.12 \
  --handler fall_event_handler.handler \
  --role arn:aws:iam::$ACCOUNT_ID:role/$ROLE \
  --zip-file fileb://handler.zip \
  --environment "Variables={FALLS_TABLE=$TABLE}" \
  --region $AWS_REGION
```
The handler file has a top-level `handler(event, context=None, table=None)` function.
Lambda calls it with `(event, context)`, so the optional `table` argument defaults to `None`
and the handler builds its own DynamoDB resource from `FALLS_TABLE`.

## 4. Expose it (optional, for a live demo endpoint)
```bash
aws lambda create-function-url-config --function-name $FUNC --auth-type AWS_IAM --region $AWS_REGION
```
`AWS_IAM` keeps the endpoint private. Use `NONE` only for a short public demo, and
turn it off afterwards.

## 5. Test it and keep the evidence
```bash
aws lambda invoke --function-name $FUNC --region $AWS_REGION \
  --cli-binary-format raw-in-base64-out \
  --payload '{"body":"{\"user_id\":\"u-42\",\"event_type\":\"vision_fall\",\"timestamp\":\"2026-10-24T10:00:00Z\",\"decision\":\"APPROVED\",\"idempotency_key\":\"test-run-0001\"}"}' \
  response.json && cat response.json
aws dynamodb scan --table-name $TABLE --region $AWS_REGION
```
Run the same invoke command a second time. The response should show `"duplicate": true` and the scan should still show one item.
Save the `response.json` outputs, the scan output and a screenshot of the Lambda console.
These are the evidence for the AWS requirement. Do not claim the deployment works without them.

## 6. Clean up after judging
```bash
aws lambda delete-function --function-name $FUNC --region $AWS_REGION
aws dynamodb delete-table --table-name $TABLE --region $AWS_REGION
```
