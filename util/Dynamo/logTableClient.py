# dynamo/promptTableClient.py
from util.Dynamo.baseTable import BaseTable

class LogTableClient(BaseTable):
    def __init__(self, dynamoDb):
        """
        Table 1 specific client, inheriting common operations from BaseTable.
        """
        super().__init__(dynamoDb, 'improvisationDirector_performanceLogs')

    def putLog(self, roomName, log):
        """
        Inserts a game log into the table.
        """
        return self.table.put_item(Item=log)


    def getLogs(self):
        """
        Retrieves all prompt scripts from the DynamoDB table and organizes them into a dictionary.

        :return: Dictionary where keys are 'prompt' and values are the corresponding 'script'.
        """
        try:
            # Scan the entire table to retrieve all items
            response = self.table.scan()
            items = response.get('Items', [])
            # Convert the items into a dictionary
            performanceLogs = {
                item['roomName']: {
                    'endingTimestamp': item['endingTimestamp'],
                    'summary': item['summary'],
                    'promptLog': item['promptLog'],
                    'performers': item['performers']
                }
                for item in items
            }
            return performanceLogs

        except Exception as e:
            print(f"Failed to retrieve items from DynamoDB: {e}")
            raise
