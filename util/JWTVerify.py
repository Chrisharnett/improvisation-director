import json
import requests
import jwt
from util.awsSecretRetrieval import cognitoSecret

REGION = 'us-east-1'
USER_POOL_ID, CLIENT_ID = cognitoSecret()
COGNITO_KEYS_URL = f'https://cognito-idp.{REGION}.amazonaws.com/{USER_POOL_ID}/.well-known/jwks.json'

# Fetch AWS Cognito public keys
cognito_keys = requests.get(COGNITO_KEYS_URL).json()

def get_cognito_public_key(token):
    """Extract the public key for verifying the token signature."""
    headers = jwt.get_unverified_header(token)
    for key in cognito_keys.get('keys'):
        if key['kid'] == headers['kid']:
            return jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(key))
    return None

def verify_jwt(token):
    """Verify the JWT signature and claims."""

    publicKey = get_cognito_public_key(token)
    if publicKey is None:
        raise jwt.InvalidTokenError("Public key not found")
    decoded_token = jwt.decode(
        token,
        publicKey,
        algorithms=['RS256'],
        # audience=CLIENT_ID,
        issuer=f'https://cognito-idp.{REGION}.amazonaws.com/{USER_POOL_ID}',
        leeway=10
    )
    return decoded_token


