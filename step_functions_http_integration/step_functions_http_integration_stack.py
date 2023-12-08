from aws_cdk import (
    CfnOutput,
    Stack,
    aws_lambda as _lambda,
    aws_events as events,
    aws_stepfunctions as sfn,
    aws_iam as iam,
)
from constructs import Construct
import json


class StepFunctionsHttpIntegrationStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create lambda function to simulate auth endpoint
        auth_lambda = _lambda.Function(
            self,
            "AuthLambda",
            runtime=_lambda.Runtime.PYTHON_3_12,
            code=_lambda.Code.from_asset("src/auth_lambda"),
            handler="index.handler",
        )

        # Add function url for auth_lambda
        auth_lambda_url = auth_lambda.add_function_url(
            auth_type=_lambda.FunctionUrlAuthType.NONE
        )

        # Create lambda function to simulate api endpoint
        api_lambda = _lambda.Function(
            self,
            "ApiLambda",
            runtime=_lambda.Runtime.PYTHON_3_12,
            code=_lambda.Code.from_asset("src/api_lambda"),
            handler="index.handler",
        )

        # Add function url for api_lambda
        api_lambda_url = api_lambda.add_function_url(
            auth_type=_lambda.FunctionUrlAuthType.NONE
        )

        # Create Eventbridge connection with authroizaion_type Oauth
        eventbridge_connection = events.CfnConnection(
            self,
            "EventbridgeConnection",
            name="EventbridgeConnectionForStepFunction",
            authorization_type="OAUTH_CLIENT_CREDENTIALS",
            auth_parameters=events.CfnConnection.AuthParametersProperty(
                o_auth_parameters=events.CfnConnection.OAuthParametersProperty(
                    authorization_endpoint=f"{auth_lambda_url.url}token",
                    client_parameters=events.CfnConnection.ClientParametersProperty(
                        client_id="oauth_client_id", client_secret="oauth_client_secret"
                    ),
                    http_method="POST",
                ),
            ),
        )

        # State machine with single HTTPApi integration
        state_machine = sfn.StateMachine(
            self,
            "StateMachineWithHttpApi",
            state_machine_type=sfn.StateMachineType.STANDARD,
            definition_body=sfn.DefinitionBody.from_string(
                json.dumps(
                    {
                        "Comment": "A description of my state machine",
                        "StartAt": "Call third-party API",
                        "States": {
                            "Call third-party API": {
                                "Type": "Task",
                                "Resource": "arn:aws:states:::http:invoke",
                                "Parameters": {
                                    "ApiEndpoint": api_lambda_url.url,
                                    "Method": "GET",
                                    "Authentication": {
                                        "ConnectionArn": eventbridge_connection.attr_arn
                                    },
                                    "RequestBody": {
                                        "hello": "world",
                                        "set401.$": "$.set401",
                                        "executionId.$": "$$.Execution.Name",
                                    },
                                },
                                "End": True,
                                "Retry": [
                                    {
                                        "ErrorEquals": ["States.Http.StatusCode.401"],
                                        "BackoffRate": 1,
                                        "MaxAttempts": 3,
                                        "IntervalSeconds": 2,
                                        "Comment": "Retry on 401",
                                    }
                                ],
                            },
                        },
                    }
                )
            ),
        )

        # attach inline policy for state machine role
        state_machine.role.attach_inline_policy(
            iam.Policy(
                self,
                "InvokeHttpEndpoint",
                document=iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=["states:InvokeHTTPEndpoint"],
                            resources=[state_machine.state_machine_arn],
                            conditions={
                                "StringEquals": {
                                    "states:HTTPEndpoint": [api_lambda_url.url],
                                    "states:HTTPMethod": ["GET"],
                                },
                            },
                        ),
                    ]
                ),
            )
        )

        state_machine.role.attach_inline_policy(
            iam.Policy(
                self,
                "EventBridgeConnectionPermissions",
                document=iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=["events:UpdateConnection"],
                            resources=[eventbridge_connection.attr_arn],
                        ),
                        iam.PolicyStatement(
                            actions=["events:RetrieveConnectionCredentials"],
                            resources=[eventbridge_connection.attr_arn],
                        ),
                        iam.PolicyStatement(
                            actions=[
                                "secretsmanager:GetSecretValue",
                                "secretsmanager:DescribeSecret",
                            ],
                            resources=[eventbridge_connection.attr_secret_arn],
                        ),
                    ]
                ),
            )
        )

        CfnOutput(self, "StateMachineArn", value=state_machine.state_machine_arn)
        CfnOutput(
            self, "EventBridgeConnectionArn", value=eventbridge_connection.attr_arn
        )
        CfnOutput(
            self,
            "EventBridgeConnectionSecretArn",
            value=eventbridge_connection.attr_secret_arn,
        )
