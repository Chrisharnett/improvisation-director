# dynamo/baseTable.py

class BaseTable:
    def __init__(self, dynamoDb, tableName):
        """
        Base class for DynamoDB table interactions.
        """
        self.table = dynamoDb.Table(tableName)

    def putItem(self, item):
        """
        Inserts an item into the table.
        """
        return self.table.put_item(Item=item)

    def getItem(self, key):
        """
        Retrieves an item from the table by the key.
        """
        return self.table.get_item(Key=key)

    def deleteItem(self, key):
        """
        Deletes an item from the table by the key.
        """
        return self.table.delete_item(Key=key)
