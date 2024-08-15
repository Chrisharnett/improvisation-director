import boto3
from botocore.exceptions import NoCredentialsError

def get_secret():
    secret_name = "your-secret-name"
    region_name = "your-region-name"

    # Create a Secrets Manager client
    client = boto3.client(
        service_name='secretsmanager',
        region_name=region_name
    )

    try:
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
    except NoCredentialsError as e:
        print("Credentials not available", e)
        raise e

    secret = get_secret_value_response['SecretString']
    return secret
