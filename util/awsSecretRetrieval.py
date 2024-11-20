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
    model = secret.get("TRAINED_MODEL")

    return oaKey, oaProject, model

def logBucketSecret():
    secretName = "improv_director/logBucket"
    secret = retrieveSecret(secretName)
    return secret.get("LOG_BUCKET")

def cognitoSecret():
    secretName = "improv_director/cognitoSecrets"
    secret = retrieveSecret(secretName)
    return secret.get('userPoolId'), secret.get('clientId')

def origins():
    secretName = "improv_director/origins"
    secret = retrieveSecret(secretName)
    originString =  secret.get('origins')
    originList = originString.split(',') if originString else []
    originList = [origin.strip() for origin in originList]
    return originList

