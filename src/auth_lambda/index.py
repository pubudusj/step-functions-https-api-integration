import json
import secrets


def generate_oauth_access_token(length: int = 32) -> str:
    """Generate an example OAuth access token."""
    token = secrets.token_hex(length)

    return token


def handler(event, context):
    if event["rawPath"] in ["/token"]:
        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "access_token": generate_oauth_access_token(),
                    "token_type": "Bearer",
                    "expires_in": 3600,
                }
            ),
            "headers": {"Content-Type": "application/json"},
        }
