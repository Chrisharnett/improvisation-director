# dynamo/connections.py
import boto3

def getDynamoDbConnection(regionName='us-east-1'):
    """
    Establish a connection to DynamoDB using default credentials and return the resource object.
    """
    try:
        # Use default credentials from ~/.aws/credentials or environment variables
        dynamoDb = boto3.resource('dynamodb', region_name=regionName)
        return dynamoDb
    except Exception as e:
        print(f"Error in connecting to DynamoDB: {e}")
        raise
