from util.Dynamo.baseTable import BaseTable

class UserTableClient(BaseTable):
    def __init__(self, dynamoDb):
        """
        Table 1 specific client, inheriting common operations from BaseTable.
        """
        super().__init__(dynamoDb, 'improvisation_director_users')
