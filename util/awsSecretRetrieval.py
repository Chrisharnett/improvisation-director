import boto3
import json
from botocore.exceptions import ClientError


def retrieveSecret(secret_name):
    region_name = "us-east-1"

    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )

    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name
        )
    except ClientError as e:
        print(f"An error occurred: {e}")
        raise e

    # Extract and parse the secret value
    secret = get_secret_value_response['SecretString']
    return json.loads(secret)

def getAISecret():
    secret = retrieveSecret("improv_director/openAI")
    oaKey = secret.get("OA_KEY")
    oaProject = secret.get("OA_PROJECT_ID")

    return oaKey, oaProject

def logBucketSecret():
    secret_name = "improv_director/logBucket"
    secret = retrieveSecret(secret_name)
    return secret.get("LOG_BUCKET")

