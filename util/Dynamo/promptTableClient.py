# dynamo/promptTableClient.py
from util.Dynamo.baseTable import BaseTable

class PromptTableClient(BaseTable):
    def __init__(self, dynamoDb):
        """
        Table 1 specific client, inheriting common operations from BaseTable.
        """
        super().__init__(dynamoDb, 'improvisationDirector_promptTable')

    def getAllPromptScripts(self):
        """
        Retrieves all prompt scripts from the DynamoDB table and organizes them into a dictionary.

        :return: Dictionary where keys are 'prompt' and values are the corresponding 'script'.
        """
        try:
            # Scan the entire table to retrieve all items
            response = self.table.scan()
            items = response.get('Items', [])

            # Convert the items into a dictionary
            promptScripts = {item['prompt']: item['script'] for item in items}

            return promptScripts

        except Exception as e:
            print(f"Failed to retrieve items from DynamoDB: {e}")
            raise
