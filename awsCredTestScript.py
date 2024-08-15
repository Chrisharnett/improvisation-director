import boto3
from botocore.exceptions import NoCredentialsError, ClientError

def test_credentials():
    secret_name = "improv_director/openAI"
    region_name = "us-east-1"

    try:
        session = boto3.session.Session()
        client = session.client(
            service_name='secretsmanager',
            region_name=region_name
        )

        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
        print("Secret fetched successfully:", get_secret_value_response['SecretString'])
    except NoCredentialsError:
        print("No credentials found.")
    except ClientError as e:
        print(f"Client error: {e}")

if __name__ == "__main__":
    test_credentials()
