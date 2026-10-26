"""
In-memory stand-in for a DynamoDB table, for local runs and tests only.
Enforces the attribute_not_exists condition the handler uses, so duplicate
handling is exercised the same way it would be against DynamoDB.
"""


class ConditionalCheckFailedException(Exception):
    def __init__(self):
        super().__init__('The conditional request failed')
        self.response = {'Error': {'Code': 'ConditionalCheckFailedException'}}


class LocalTable:
    def __init__(self):
        self.items = {}

    def put_item(self, Item, ConditionExpression=None):
        key = Item['incident_id']
        if ConditionExpression == 'attribute_not_exists(incident_id)' and key in self.items:
            raise ConditionalCheckFailedException()
        self.items[key] = dict(Item)

    @property
    def count(self):
        return len(self.items)
