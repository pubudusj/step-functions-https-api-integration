import json
import time

executed_requests = []


def handler(event, context):
    global executed_requests
    print(event)

    body = json.loads(event["body"])
    execution_id = body["executionId"]
    is_retry = execution_id in executed_requests

    if body["set401"] == True and not is_retry:
        executed_requests.append(execution_id)
        return {
            "statusCode": 401,
            "body": json.dumps({"message": "Unauthorized"}),
            "headers": {"Content-Type": "application/json"},
        }

    return {
        "statusCode": 200,
        "body": {"status": "OK"},
        "headers": {"Content-Type": "application/json"},
    }
