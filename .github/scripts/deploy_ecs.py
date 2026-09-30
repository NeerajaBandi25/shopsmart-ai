"""Deploy an immutable backend image to an existing ECS Fargate service."""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unittest
from typing import Any, Callable
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from deploy_preflight import PreflightError, run_preflight

GENERATED_TASK_DEFINITION_FIELDS = {
    "taskDefinitionArn",
    "revision",
    "status",
    "requiresAttributes",
    "compatibilities",
    "registeredAt",
    "registeredBy",
    "deregisteredAt",
}
REQUIRED_SECRETS = ("DATABASE_URL", "SECRET_KEY")
IMAGE_DIGEST_PATTERN = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._:/-]*@sha256:[0-9a-f]{64}$"
)
SAFE_OUTPUT_PATTERN = re.compile(r"^[A-Za-z0-9:/._-]+$")


class DeploymentError(RuntimeError):
    """Raised when an ECS deployment prerequisite or operation fails."""


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(
        self,
        request: Request,
        file_pointer: Any,
        code: int,
        message: str,
        headers: Any,
        new_url: str,
    ) -> None:
        return None


_READINESS_OPENER = build_opener(_NoRedirectHandler)


class AwsCli:
    def __init__(self, region: str) -> None:
        self.region = region

    def run_json(self, arguments: list[str]) -> dict[str, Any]:
        command = ["aws", *arguments, "--region", self.region, "--output", "json"]
        try:
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=1200,
            )
        except (OSError, subprocess.SubprocessError):
            raise DeploymentError("AWS CLI command could not be completed") from None
        if result.returncode != 0:
            raise DeploymentError(
                f"AWS CLI {arguments[0]} {arguments[1]} failed; inspect CloudTrail and ECS events"
            )
        try:
            response = json.loads(result.stdout)
        except json.JSONDecodeError:
            raise DeploymentError("AWS CLI returned an invalid JSON response") from None
        if not isinstance(response, dict):
            raise DeploymentError("AWS CLI returned an unexpected response")
        return response

    def wait(self, arguments: list[str]) -> None:
        command = ["aws", *arguments, "--region", self.region]
        try:
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=1200,
            )
        except (OSError, subprocess.SubprocessError):
            raise DeploymentError("AWS ECS waiter could not be completed") from None
        if result.returncode != 0:
            raise DeploymentError(f"AWS ECS waiter {arguments[1]} did not complete successfully")


def validate_image_digest(image: str) -> None:
    if not IMAGE_DIGEST_PATTERN.fullmatch(image):
        raise DeploymentError("The backend image must be identified by an ECR sha256 digest")


def build_registration_payload(
    description: dict[str, Any],
    *,
    container_name: str,
    image: str,
) -> dict[str, Any]:
    validate_image_digest(image)
    task_definition = description.get("taskDefinition")
    if not isinstance(task_definition, dict) or task_definition.get("status") != "ACTIVE":
        raise DeploymentError("The current ECS task definition is missing or inactive")
    if task_definition.get("networkMode") != "awsvpc":
        raise DeploymentError("The ECS task definition must use awsvpc networking")
    if "FARGATE" not in task_definition.get("requiresCompatibilities", []):
        raise DeploymentError("The ECS task definition must support Fargate")
    if not task_definition.get("executionRoleArn"):
        raise DeploymentError("The ECS task definition must have an execution role")

    containers = task_definition.get("containerDefinitions")
    if not isinstance(containers, list) or not all(
        isinstance(container, dict) for container in containers
    ):
        raise DeploymentError("The ECS task definition has no container definitions")
    matching_containers = [
        container
        for container in containers
        if isinstance(container, dict) and container.get("name") == container_name
    ]
    if len(matching_containers) != 1:
        raise DeploymentError("The configured ECS container was not found exactly once")
    container = matching_containers[0]

    environment = container.get("environment", [])
    if not isinstance(environment, list):
        raise DeploymentError("The ECS container environment is invalid")
    literal_names = {
        item.get("name") for item in environment if isinstance(item, dict)
    }
    if literal_names.intersection(REQUIRED_SECRETS):
        raise DeploymentError("DATABASE_URL and SECRET_KEY must not be task-definition literals")

    secrets = container.get("secrets", [])
    if not isinstance(secrets, list):
        raise DeploymentError("The ECS container secret references are invalid")
    for secret_name in REQUIRED_SECRETS:
        references = [
            secret
            for secret in secrets
            if isinstance(secret, dict) and secret.get("name") == secret_name
        ]
        if len(references) != 1 or not references[0].get("valueFrom"):
            raise DeploymentError(
                f"The ECS task definition must reference {secret_name} through ECS secrets"
            )

    logging = container.get("logConfiguration")
    options = logging.get("options") if isinstance(logging, dict) else None
    if not isinstance(options, dict) or logging.get("logDriver") != "awslogs":
        raise DeploymentError("The ECS container must use the awslogs log driver")
    if not options.get("awslogs-group"):
        raise DeploymentError("The ECS awslogs group must be configured")

    updated_containers = copy.deepcopy(containers)
    for updated_container in updated_containers:
        if updated_container.get("name") == container_name:
            updated_container["image"] = image

    registration = {
        key: copy.deepcopy(value)
        for key, value in task_definition.items()
        if key not in GENERATED_TASK_DEFINITION_FIELDS
    }
    registration["containerDefinitions"] = updated_containers
    tags = description.get("tags", [])
    if not isinstance(tags, list):
        raise DeploymentError("The ECS task definition tags are invalid")
    registration["tags"] = copy.deepcopy(tags)
    return registration


def describe_service(aws: Any, cluster: str, service_name: str) -> dict[str, Any]:
    response = aws.run_json(
        ["ecs", "describe-services", "--cluster", cluster, "--services", service_name]
    )
    failures = response.get("failures", [])
    services = response.get("services", [])
    if failures or not isinstance(services, list) or len(services) != 1:
        raise DeploymentError("The configured ECS service could not be found")
    service = services[0]
    if not isinstance(service, dict) or service.get("status") != "ACTIVE":
        raise DeploymentError("The configured ECS service is not active")
    if not service.get("taskDefinition"):
        raise DeploymentError("The ECS service has no active task definition")
    return service


def service_network(service: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    configuration = service.get("networkConfiguration")
    awsvpc = configuration.get("awsvpcConfiguration") if isinstance(configuration, dict) else None
    if not isinstance(awsvpc, dict):
        raise DeploymentError("The ECS Fargate service has no awsvpc network configuration")
    subnets = awsvpc.get("subnets")
    security_groups = awsvpc.get("securityGroups")
    if (
        not isinstance(subnets, list)
        or not subnets
        or not all(isinstance(value, str) and value for value in subnets)
    ):
        raise DeploymentError("The ECS service must have configured Fargate subnets")
    if (
        not isinstance(security_groups, list)
        or not security_groups
        or not all(isinstance(value, str) and value for value in security_groups)
    ):
        raise DeploymentError("The ECS service must have configured Fargate security groups")

    task_network: dict[str, Any] = {
        "subnets": list(subnets),
        "securityGroups": list(security_groups),
    }
    assign_public_ip = awsvpc.get("assignPublicIp")
    if assign_public_ip in {"ENABLED", "DISABLED"}:
        task_network["assignPublicIp"] = assign_public_ip

    strategy = service.get("capacityProviderStrategy") or []
    if strategy:
        providers = [
            item.get("capacityProvider")
            for item in strategy
            if isinstance(item, dict)
        ]
        if len(providers) != len(strategy) or not providers:
            raise DeploymentError("The ECS service capacity provider strategy is invalid")
        if not set(providers).issubset({"FARGATE", "FARGATE_SPOT"}):
            raise DeploymentError("The ECS service must use a Fargate capacity provider")
        return task_network, ["--capacity-provider-strategy", json.dumps(strategy)]
    if service.get("launchType") != "FARGATE":
        raise DeploymentError("The ECS service must use the FARGATE launch type")
    return task_network, ["--launch-type", "FARGATE"]


def register_task_definition(aws: Any, payload: dict[str, Any]) -> str:
    temporary_path = ""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=".json", delete=False
        ) as temporary_file:
            json.dump(payload, temporary_file, separators=(",", ":"))
            temporary_path = temporary_file.name
        response = aws.run_json(
            ["ecs", "register-task-definition", "--cli-input-json", f"file://{temporary_path}"]
        )
    except OSError:
        raise DeploymentError("Could not prepare the ECS task definition for registration") from None
    finally:
        if temporary_path and os.path.exists(temporary_path):
            os.unlink(temporary_path)

    task_definition = response.get("taskDefinition")
    arn = task_definition.get("taskDefinitionArn") if isinstance(task_definition, dict) else None
    if not isinstance(arn, str) or not arn:
        raise DeploymentError("ECS did not return the registered task definition ARN")
    return arn


def validate_readiness_url(url: str) -> None:
    try:
        parsed = urlsplit(url)
        hostname = parsed.hostname
    except ValueError:
        raise DeploymentError("BACKEND_READINESS_URL is invalid") from None
    if (
        parsed.scheme != "https"
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or not parsed.path.rstrip("/").endswith("/readiness")
    ):
        raise DeploymentError("BACKEND_READINESS_URL must be an HTTPS /readiness URL")


def probe_readiness(url: str) -> bool:
    try:
        with _READINESS_OPENER.open(Request(url, method="GET"), timeout=10) as response:
            return response.status == 200
    except (HTTPError, URLError, TimeoutError, OSError):
        return False


def wait_for_readiness(
    url: str,
    *,
    timeout_seconds: int = 300,
    interval_seconds: int = 10,
    probe: Callable[[str], bool] = probe_readiness,
) -> None:
    validate_readiness_url(url)
    deadline = time.monotonic() + timeout_seconds
    while True:
        if probe(url):
            return
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise DeploymentError("The backend /readiness endpoint did not return HTTP 200")
        time.sleep(min(interval_seconds, remaining))


def write_github_outputs(path: str | None, values: dict[str, str]) -> None:
    if not path:
        return
    for value in values.values():
        if not SAFE_OUTPUT_PATTERN.fullmatch(value):
            raise DeploymentError("A deployment output contains unsupported characters")
    try:
        with open(path, "a", encoding="utf-8", newline="\n") as output_file:
            for name, value in values.items():
                output_file.write(f"{name}={value}\n")
    except OSError:
        raise DeploymentError("Could not write deployment outputs") from None


def migration_task(
    aws: Any,
    *,
    cluster: str,
    task_definition: str,
    container_name: str,
    network: dict[str, Any],
    launch_arguments: list[str],
) -> str:
    overrides = {
        "containerOverrides": [
            {
                "name": container_name,
                "command": ["alembic", "upgrade", "head"],
            }
        ]
    }
    response = aws.run_json(
        [
            "ecs",
            "run-task",
            "--cluster",
            cluster,
            *launch_arguments,
            "--task-definition",
            task_definition,
            "--count",
            "1",
            "--network-configuration",
            json.dumps({"awsvpcConfiguration": network}, separators=(",", ":")),
            "--overrides",
            json.dumps(overrides, separators=(",", ":")),
        ]
    )
    failures = response.get("failures", [])
    tasks = response.get("tasks", [])
    if failures or not isinstance(tasks, list) or len(tasks) != 1:
        raise DeploymentError("ECS could not start the one-off Alembic migration task")
    task_arn = tasks[0].get("taskArn") if isinstance(tasks[0], dict) else None
    if not isinstance(task_arn, str) or not task_arn:
        raise DeploymentError("ECS did not return the Alembic migration task ARN")

    try:
        aws.wait(["ecs", "wait", "tasks-stopped", "--cluster", cluster, "--tasks", task_arn])
    except DeploymentError:
        try:
            aws.run_json(["ecs", "stop-task", "--cluster", cluster, "--task", task_arn])
        except DeploymentError:
            pass
        raise DeploymentError("The Alembic migration task did not stop successfully") from None

    task_response = aws.run_json(
        ["ecs", "describe-tasks", "--cluster", cluster, "--tasks", task_arn]
    )
    stopped_tasks = task_response.get("tasks", [])
    if not isinstance(stopped_tasks, list) or len(stopped_tasks) != 1:
        raise DeploymentError("ECS did not return the completed Alembic migration task")
    containers = stopped_tasks[0].get("containers", [])
    container_statuses = [
        container
        for container in containers
        if isinstance(container, dict) and container.get("name") == container_name
    ]
    if (
        stopped_tasks[0].get("lastStatus") != "STOPPED"
        or len(container_statuses) != 1
        or container_statuses[0].get("exitCode") != 0
    ):
        raise DeploymentError("The Alembic migration task failed; the ECS service was not changed")
    return task_arn


def restore_task_definition(
    aws: Any,
    *,
    cluster: str,
    service_name: str,
    expected_task_definition: str,
    previous_task_definition: str,
    readiness_url: str | None = None,
    readiness_check: Callable[[str], None] = wait_for_readiness,
) -> None:
    service = describe_service(aws, cluster, service_name)
    current_task_definition = service["taskDefinition"]
    if current_task_definition not in {expected_task_definition, previous_task_definition}:
        raise DeploymentError(
            "Refusing ECS rollback because the service no longer uses this release revision"
        )

    if current_task_definition != previous_task_definition:
        aws.run_json(
            [
                "ecs",
                "update-service",
                "--cluster",
                cluster,
                "--service",
                service_name,
                "--task-definition",
                previous_task_definition,
            ]
        )
    aws.wait(["ecs", "wait", "services-stable", "--cluster", cluster, "--services", service_name])
    if readiness_url:
        readiness_check(readiness_url)


def deploy_backend(
    aws: Any,
    *,
    cluster: str,
    service_name: str,
    container_name: str,
    image: str,
    readiness_url: str,
    output_path: str | None = None,
    release_gate_check: Callable[[], None] | None = None,
    readiness_check: Callable[[str], None] = wait_for_readiness,
) -> dict[str, str]:
    validate_image_digest(image)
    validate_readiness_url(readiness_url)
    service = describe_service(aws, cluster, service_name)
    network, launch_arguments = service_network(service)
    previous_task_definition = service["taskDefinition"]

    description = aws.run_json(
        [
            "ecs",
            "describe-task-definition",
            "--task-definition",
            previous_task_definition,
            "--include",
            "TAGS",
        ]
    )
    registration = build_registration_payload(
        description,
        container_name=container_name,
        image=image,
    )
    deployed_task_definition = register_task_definition(aws, registration)
    outputs = {
        "previous_task_definition": previous_task_definition,
        "deployed_task_definition": deployed_task_definition,
        "image_digest": image.rsplit("@", maxsplit=1)[1],
    }
    write_github_outputs(output_path, outputs)

    task_arn = migration_task(
        aws,
        cluster=cluster,
        task_definition=deployed_task_definition,
        container_name=container_name,
        network=network,
        launch_arguments=launch_arguments,
    )
    outputs["migration_task_arn"] = task_arn
    write_github_outputs(output_path, {"migration_task_arn": task_arn})

    if release_gate_check is not None:
        release_gate_check()

    try:
        aws.run_json(
            [
                "ecs",
                "update-service",
                "--cluster",
                cluster,
                "--service",
                service_name,
                "--task-definition",
                deployed_task_definition,
            ]
        )
        aws.wait(
            ["ecs", "wait", "services-stable", "--cluster", cluster, "--services", service_name]
        )
        readiness_check(readiness_url)
    except DeploymentError as deployment_error:
        try:
            restore_task_definition(
                aws,
                cluster=cluster,
                service_name=service_name,
                expected_task_definition=deployed_task_definition,
                previous_task_definition=previous_task_definition,
                readiness_url=readiness_url,
                readiness_check=readiness_check,
            )
        except DeploymentError as rollback_error:
            raise DeploymentError(
                f"ECS deployment failed ({deployment_error}); rollback failed ({rollback_error})"
            ) from None
        raise DeploymentError(
            f"ECS deployment failed; previous task definition restored ({deployment_error})"
        ) from None

    return outputs


def load_configuration() -> dict[str, str]:
    names = {
        "region": "AWS_REGION",
        "cluster": "ECS_CLUSTER",
        "service_name": "ECS_SERVICE",
        "container_name": "ECS_CONTAINER_NAME",
        "readiness_url": "BACKEND_READINESS_URL",
    }
    configuration = {key: os.environ.get(name, "") for key, name in names.items()}
    missing = [name for key, name in names.items() if not configuration[key]]
    if missing:
        raise DeploymentError(f"Required deployment configuration is missing: {', '.join(missing)}")
    return configuration


def verify_current_release() -> None:
    try:
        run_preflight(
            repository=os.environ.get("GITHUB_REPOSITORY", ""),
            ref=os.environ.get("GITHUB_REF", ""),
            sha=os.environ.get("GITHUB_SHA", ""),
            token=os.environ.get("GITHUB_TOKEN", ""),
        )
    except PreflightError as error:
        raise DeploymentError(
            f"Release preflight changed before ECS service update: {error}"
        ) from None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    deploy_parser = subparsers.add_parser("deploy")
    deploy_parser.add_argument("--image", required=True)
    deploy_parser.add_argument("--github-output", default=os.environ.get("GITHUB_OUTPUT"))
    rollback_parser = subparsers.add_parser("rollback")
    rollback_parser.add_argument("--previous-task-definition", required=True)
    rollback_parser.add_argument("--expected-task-definition", required=True)
    rollback_parser.add_argument("--github-output", default=os.environ.get("GITHUB_OUTPUT"))
    arguments = parser.parse_args()

    try:
        configuration = load_configuration()
        aws = AwsCli(configuration["region"])
        if arguments.command == "deploy":
            outputs = deploy_backend(
                aws,
                cluster=configuration["cluster"],
                service_name=configuration["service_name"],
                container_name=configuration["container_name"],
                image=arguments.image,
                readiness_url=configuration["readiness_url"],
                output_path=arguments.github_output,
                release_gate_check=verify_current_release,
            )
            print(
                "ECS deployment passed: "
                f"task_definition={outputs['deployed_task_definition']}, "
                f"image_digest={outputs['image_digest']}"
            )
        else:
            restore_task_definition(
                aws,
                cluster=configuration["cluster"],
                service_name=configuration["service_name"],
                expected_task_definition=arguments.expected_task_definition,
                previous_task_definition=arguments.previous_task_definition,
                readiness_url=configuration["readiness_url"],
            )
            print("ECS rollback passed")
    except DeploymentError as error:
        print(f"ECS deployment failed: {error}", file=sys.stderr)
        return 1
    return 0


class FakeAwsCli:
    def __init__(self, *, migration_exit_code: int = 0) -> None:
        self.cluster = "shopsmart-cluster"
        self.service_name = "shopsmart-backend"
        self.container_name = "backend"
        self.previous_task_definition = "arn:aws:ecs:us-east-1:example:task-definition/backend:3"
        self.deployed_task_definition = "arn:aws:ecs:us-east-1:example:task-definition/backend:4"
        self.migration_task_arn = "arn:aws:ecs:us-east-1:example:task/backend/migration-1"
        self.current_task_definition = self.previous_task_definition
        self.migration_exit_code = migration_exit_code
        self.commands: list[list[str]] = []
        self.waits: list[list[str]] = []
        self.registered_payload: dict[str, Any] | None = None
        self.run_task_network: dict[str, Any] | None = None
        self.run_task_overrides: dict[str, Any] | None = None
        self.fail_service_wait_once = False

    def run_json(self, arguments: list[str]) -> dict[str, Any]:
        self.commands.append(arguments)
        operation = arguments[1]
        if operation == "describe-services":
            return {
                "failures": [],
                "services": [
                    {
                        "status": "ACTIVE",
                        "taskDefinition": self.current_task_definition,
                        "launchType": "FARGATE",
                        "networkConfiguration": {
                            "awsvpcConfiguration": {
                                "subnets": ["subnet-a", "subnet-b"],
                                "securityGroups": ["sg-backend"],
                                "assignPublicIp": "DISABLED",
                            }
                        },
                    }
                ],
            }
        if operation == "describe-task-definition":
            return task_definition_response()
        if operation == "register-task-definition":
            input_path = arguments[arguments.index("--cli-input-json") + 1].removeprefix("file://")
            with open(input_path, encoding="utf-8") as input_file:
                self.registered_payload = json.load(input_file)
            return {"taskDefinition": {"taskDefinitionArn": self.deployed_task_definition}}
        if operation == "run-task":
            self.run_task_network = json.loads(
                arguments[arguments.index("--network-configuration") + 1]
            )
            self.run_task_overrides = json.loads(arguments[arguments.index("--overrides") + 1])
            return {"failures": [], "tasks": [{"taskArn": self.migration_task_arn}]}
        if operation == "describe-tasks":
            return {
                "tasks": [
                    {
                        "lastStatus": "STOPPED",
                        "containers": [
                            {"name": self.container_name, "exitCode": self.migration_exit_code}
                        ],
                    }
                ]
            }
        if operation == "update-service":
            self.current_task_definition = arguments[arguments.index("--task-definition") + 1]
            return {"service": {"taskDefinition": self.current_task_definition}}
        if operation == "stop-task":
            return {"task": {"taskArn": self.migration_task_arn}}
        raise AssertionError(f"Unexpected AWS CLI operation: {operation}")

    def wait(self, arguments: list[str]) -> None:
        self.waits.append(arguments)
        if self.fail_service_wait_once and arguments[1:3] == ["wait", "services-stable"]:
            self.fail_service_wait_once = False
            raise DeploymentError("ECS service did not stabilize")


def task_definition_response() -> dict[str, Any]:
    return {
        "taskDefinition": {
            "family": "backend",
            "taskDefinitionArn": "arn:aws:ecs:us-east-1:example:task-definition/backend:3",
            "revision": 3,
            "status": "ACTIVE",
            "requiresCompatibilities": ["FARGATE"],
            "networkMode": "awsvpc",
            "cpu": "512",
            "memory": "1024",
            "executionRoleArn": "arn:aws:iam::example:role/ecsExecutionRole",
            "taskRoleArn": "arn:aws:iam::example:role/ecsTaskRole",
            "registeredAt": "2026-01-01T00:00:00Z",
            "registeredBy": "arn:aws:iam::example:user/operator",
            "requiresAttributes": [],
            "compatibilities": ["EC2", "FARGATE"],
            "containerDefinitions": [
                {
                    "name": "backend",
                    "image": "shopsmart/backend:old",
                    "essential": True,
                    "environment": [{"name": "AUTO_CREATE_TABLES", "value": "false"}],
                    "secrets": [
                        {"name": "DATABASE_URL", "valueFrom": "arn:secret:database"},
                        {"name": "SECRET_KEY", "valueFrom": "arn:secret:signing"},
                    ],
                    "logConfiguration": {
                        "logDriver": "awslogs",
                        "options": {
                            "awslogs-group": "/shopsmart/backend",
                            "awslogs-region": "us-east-1",
                            "awslogs-stream-prefix": "ecs",
                        },
                    },
                }
            ],
        },
        "tags": [{"key": "service", "value": "backend"}],
    }


class DeploymentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.aws = FakeAwsCli()
        self.image = f"example.dkr.ecr.us-east-1.amazonaws.com/backend@sha256:{'a' * 64}"
        self.readiness_url = "https://api.example.invalid/readiness"

    def test_task_definition_changes_only_the_requested_image(self) -> None:
        response = task_definition_response()
        payload = build_registration_payload(
            response,
            container_name="backend",
            image=self.image,
        )
        original = response["taskDefinition"]
        self.assertEqual(payload["containerDefinitions"][0]["image"], self.image)
        self.assertEqual(payload["containerDefinitions"][0]["secrets"], original["containerDefinitions"][0]["secrets"])
        self.assertEqual(payload["executionRoleArn"], original["executionRoleArn"])
        self.assertEqual(payload["taskRoleArn"], original["taskRoleArn"])
        self.assertEqual(payload["tags"], response["tags"])
        self.assertNotIn("taskDefinitionArn", payload)
        self.assertNotIn("registeredAt", payload)

    def test_task_definition_requires_secret_references_and_cloudwatch_logs(self) -> None:
        invalid_cases = (
            ("missing database secret", lambda container: container["secrets"].pop(0)),
            (
                "plaintext database secret",
                lambda container: container["environment"].append(
                    {"name": "DATABASE_URL", "value": "fixture-redacted"}
                ),
            ),
            (
                "missing CloudWatch logs",
                lambda container: container["logConfiguration"].update(logDriver="json-file"),
            ),
        )
        for case_name, mutate in invalid_cases:
            with self.subTest(case_name=case_name):
                response = task_definition_response()
                mutate(response["taskDefinition"]["containerDefinitions"][0])
                with self.assertRaises(DeploymentError):
                    build_registration_payload(
                        response,
                        container_name="backend",
                        image=self.image,
                    )

    def test_fargate_task_definition_is_required(self) -> None:
        response = task_definition_response()
        response["taskDefinition"]["networkMode"] = "bridge"
        with self.assertRaisesRegex(DeploymentError, "awsvpc"):
            build_registration_payload(
                response,
                container_name="backend",
                image=self.image,
            )

    def test_migration_runs_with_service_network_before_service_update(self) -> None:
        outputs = deploy_backend(
            self.aws,
            cluster=self.aws.cluster,
            service_name=self.aws.service_name,
            container_name=self.aws.container_name,
            image=self.image,
            readiness_url=self.readiness_url,
            readiness_check=lambda url: None,
        )
        operations = [arguments[1] for arguments in self.aws.commands]
        self.assertLess(operations.index("run-task"), operations.index("update-service"))
        self.assertEqual(
            self.aws.run_task_network,
            {
                "awsvpcConfiguration": {
                    "subnets": ["subnet-a", "subnet-b"],
                    "securityGroups": ["sg-backend"],
                    "assignPublicIp": "DISABLED",
                }
            },
        )
        self.assertEqual(
            self.aws.run_task_overrides["containerOverrides"][0]["command"],
            ["alembic", "upgrade", "head"],
        )
        self.assertEqual(outputs["previous_task_definition"], self.aws.previous_task_definition)
        self.assertEqual(outputs["deployed_task_definition"], self.aws.deployed_task_definition)

    def test_release_gate_runs_after_migration_and_before_service_update(self) -> None:
        def check_release_gate() -> None:
            operations = [arguments[1] for arguments in self.aws.commands]
            self.assertIn("run-task", operations)
            self.assertIn("describe-tasks", operations)
            self.assertNotIn("update-service", operations)

        deploy_backend(
            self.aws,
            cluster=self.aws.cluster,
            service_name=self.aws.service_name,
            container_name=self.aws.container_name,
            image=self.image,
            readiness_url=self.readiness_url,
            release_gate_check=check_release_gate,
            readiness_check=lambda url: None,
        )

    def test_failed_release_gate_leaves_service_unchanged(self) -> None:
        def fail_release_gate() -> None:
            raise DeploymentError("release is stale")

        with self.assertRaisesRegex(DeploymentError, "release is stale"):
            deploy_backend(
                self.aws,
                cluster=self.aws.cluster,
                service_name=self.aws.service_name,
                container_name=self.aws.container_name,
                image=self.image,
                readiness_url=self.readiness_url,
                release_gate_check=fail_release_gate,
                readiness_check=lambda url: None,
            )
        self.assertNotIn("update-service", [arguments[1] for arguments in self.aws.commands])
        self.assertEqual(self.aws.current_task_definition, self.aws.previous_task_definition)

    def test_readiness_probe_rejects_redirects(self) -> None:
        with patch.object(
            _READINESS_OPENER,
            "open",
            side_effect=HTTPError(
                self.readiness_url,
                302,
                "Found",
                {},
                None,
            ),
        ):
            self.assertFalse(probe_readiness(self.readiness_url))



    def test_deploy_cli_uses_preflight_without_passing_region_to_deployer(self) -> None:
        image = f"example.dkr.ecr.us-east-1.amazonaws.com/backend@sha256:{'a' * 64}"
        environment = {
            "AWS_REGION": "us-east-1",
            "ECS_CLUSTER": "shopsmart-cluster",
            "ECS_SERVICE": "shopsmart-backend",
            "ECS_CONTAINER_NAME": "backend",
            "BACKEND_READINESS_URL": "https://api.example.invalid/readiness",
            "GITHUB_REPOSITORY": "NeerajaBandi25/shopsmart-ai",
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_SHA": "a" * 40,
            "GITHUB_TOKEN": "offline-test-token",
        }
        outputs = {
            "deployed_task_definition": "arn:aws:ecs:us-east-1:example:task-definition/backend:4",
            "image_digest": f"sha256:{'a' * 64}",
        }
        with (
            patch.dict(os.environ, environment, clear=True),
            patch.object(sys, "argv", ["deploy_ecs.py", "deploy", "--image", image]),
            patch(f"{__name__}.AwsCli") as aws_factory,
            patch(f"{__name__}.deploy_backend", return_value=outputs) as deploy,
            patch(f"{__name__}.run_preflight") as preflight,
        ):
            self.assertEqual(main(), 0)
            deploy_kwargs = deploy.call_args.kwargs
            self.assertNotIn("region", deploy_kwargs)
            self.assertIs(deploy_kwargs["release_gate_check"], verify_current_release)
            deploy_kwargs["release_gate_check"]()

        aws_factory.assert_called_once_with("us-east-1")
        preflight.assert_called_once_with(
            repository="NeerajaBandi25/shopsmart-ai",
            ref="refs/heads/main",
            sha="a" * 40,
            token="offline-test-token",
        )

    def test_failed_migration_never_updates_the_service(self) -> None:
        self.aws.migration_exit_code = 1
        with self.assertRaisesRegex(DeploymentError, "migration task failed"):
            deploy_backend(
                self.aws,
                cluster=self.aws.cluster,
                service_name=self.aws.service_name,
                container_name=self.aws.container_name,
                image=self.image,
                readiness_url=self.readiness_url,
                readiness_check=lambda url: None,
            )
        self.assertNotIn("update-service", [arguments[1] for arguments in self.aws.commands])
        self.assertEqual(self.aws.current_task_definition, self.aws.previous_task_definition)

    def test_readiness_failure_restores_the_previous_task_definition(self) -> None:
        readiness_attempts = 0

        def fail_readiness(url: str) -> None:
            nonlocal readiness_attempts
            readiness_attempts += 1
            if readiness_attempts == 1:
                raise DeploymentError("readiness unavailable")

        with self.assertRaisesRegex(DeploymentError, "previous task definition restored"):
            deploy_backend(
                self.aws,
                cluster=self.aws.cluster,
                service_name=self.aws.service_name,
                container_name=self.aws.container_name,
                image=self.image,
                readiness_url=self.readiness_url,
                readiness_check=fail_readiness,
            )
        updates = [
            arguments[arguments.index("--task-definition") + 1]
            for arguments in self.aws.commands
            if arguments[1] == "update-service"
        ]
        self.assertEqual(
            updates,
            [self.aws.deployed_task_definition, self.aws.previous_task_definition],
        )
        self.assertEqual(self.aws.current_task_definition, self.aws.previous_task_definition)

    def test_ecs_stability_failure_restores_the_previous_task_definition(self) -> None:
        self.aws.fail_service_wait_once = True
        with self.assertRaisesRegex(DeploymentError, "previous task definition restored"):
            deploy_backend(
                self.aws,
                cluster=self.aws.cluster,
                service_name=self.aws.service_name,
                container_name=self.aws.container_name,
                image=self.image,
                readiness_url=self.readiness_url,
                readiness_check=lambda url: None,
            )
        updates = [
            arguments[arguments.index("--task-definition") + 1]
            for arguments in self.aws.commands
            if arguments[1] == "update-service"
        ]
        self.assertEqual(
            updates,
            [self.aws.deployed_task_definition, self.aws.previous_task_definition],
        )
        self.assertEqual(self.aws.current_task_definition, self.aws.previous_task_definition)

    def test_rollback_refuses_to_overwrite_a_newer_service_revision(self) -> None:
        self.aws.current_task_definition = "arn:aws:ecs:us-east-1:example:task-definition/backend:5"
        with self.assertRaisesRegex(DeploymentError, "Refusing ECS rollback"):
            restore_task_definition(
                self.aws,
                cluster=self.aws.cluster,
                service_name=self.aws.service_name,
                expected_task_definition=self.aws.deployed_task_definition,
                previous_task_definition=self.aws.previous_task_definition,
            )
        self.assertNotIn("update-service", [arguments[1] for arguments in self.aws.commands])

    def test_existing_previous_revision_is_still_waited_and_checked(self) -> None:
        readiness_checks: list[str] = []
        restore_task_definition(
            self.aws,
            cluster=self.aws.cluster,
            service_name=self.aws.service_name,
            expected_task_definition=self.aws.deployed_task_definition,
            previous_task_definition=self.aws.previous_task_definition,
            readiness_url=self.readiness_url,
            readiness_check=readiness_checks.append,
        )
        self.assertEqual(len(self.aws.waits), 1)
        self.assertEqual(readiness_checks, [self.readiness_url])
        self.assertNotIn("update-service", [arguments[1] for arguments in self.aws.commands])


def self_test() -> int:
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(DeploymentTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    if sys.argv[1:] == ["--self-test"]:
        raise SystemExit(self_test())
    raise SystemExit(main())
