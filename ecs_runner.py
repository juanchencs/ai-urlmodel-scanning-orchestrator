#!/usr/bin/env python3
import time
import uuid
from dataclasses import dataclass

import boto3
from botocore.exceptions import BotoCoreError, ClientError


@dataclass
class ECSRunResult:
    task_arn: str
    task_definition_arn: str
    result_s3_key: str


class ECSRunner:
    def __init__(
        self,
        cluster_arn: str,
        task_execution_role_arn: str,
        task_role_arn: str,
        scanner_image_uri: str,
        subnets: list[str],
        security_groups: list[str],
        assign_public_ip: str = "ENABLED",
        cpu: str = "2048",
        memory: str = "4096",
        region_name: str = "eu-west-2",
    ):
        self.cluster_arn = cluster_arn
        self.task_execution_role_arn = task_execution_role_arn
        self.task_role_arn = task_role_arn
        self.scanner_image_uri = scanner_image_uri
        self.subnets = subnets
        self.security_groups = security_groups
        self.assign_public_ip = assign_public_ip
        self.cpu = cpu
        self.memory = memory
        self.ecs = boto3.client("ecs", region_name=region_name)

    def _register_task_definition(self, model_version: str) -> str:
        family = f"urlmodel-scan-{model_version}"
        model_image = f"scr.aaaaa.com/spoke/sai-url:model-version-{model_version}"

        response = self.ecs.register_task_definition(
            family=family,
            networkMode="awsvpc",
            requiresCompatibilities=["FARGATE"],
            cpu=self.cpu,
            memory=self.memory,
            executionRoleArn=self.task_execution_role_arn,
            taskRoleArn=self.task_role_arn,
            containerDefinitions=[
                {
                    "name": "urlmodel",
                    "image": model_image,
                    "essential": True,
                    "environment": [
                        {"name": "WORKERS", "value": "1"},
                        {"name": "THREADS", "value": "0"},
                        {"name": "SYSTEM", "value": "internal"},
                    ],
                    "portMappings": [{"containerPort": 8080, "protocol": "tcp"}],
                    "logConfiguration": {
                        "logDriver": "awslogs",
                        "options": {
                            "awslogs-group": "/ecs/urlmodel-scan",
                            "awslogs-region": self.ecs.meta.region_name,
                            "awslogs-stream-prefix": "urlmodel",
                        },
                    },
                },
                {
                    "name": "scanner",
                    "image": self.scanner_image_uri,
                    "essential": True,
                    "dependsOn": [{"containerName": "urlmodel", "condition": "START"}],
                    "logConfiguration": {
                        "logDriver": "awslogs",
                        "options": {
                            "awslogs-group": "/ecs/urlmodel-scan",
                            "awslogs-region": self.ecs.meta.region_name,
                            "awslogs-stream-prefix": "scanner",
                        },
                    },
                },
            ],
            runtimePlatform={"cpuArchitecture": "X86_64", "operatingSystemFamily": "LINUX"},
        )
        return response["taskDefinition"]["taskDefinitionArn"]

    def run_scan_task(
        self,
        model_version: str,
        url_txt: str,
        data_source: str,
        output_file: str,
        results_bucket: str,
        results_prefix: str,
        request_id: str,
    ) -> ECSRunResult:
        task_definition_arn = self._register_task_definition(model_version)

        # Fargate tasks are network-isolated with awsvpc, avoiding host NAME/PORT conflicts.
        run = self.ecs.run_task(
            cluster=self.cluster_arn,
            launchType="FARGATE",
            taskDefinition=task_definition_arn,
            networkConfiguration={
                "awsvpcConfiguration": {
                    "subnets": self.subnets,
                    "securityGroups": self.security_groups,
                    "assignPublicIp": self.assign_public_ip,
                }
            },
            overrides={
                "containerOverrides": [
                    {
                        "name": "scanner",
                        "environment": [
                            {"name": "MODEL_VERSION", "value": model_version},
                            {"name": "URL_TXT", "value": url_txt},
                            {"name": "DATA_SOURCE", "value": data_source},
                            {"name": "OUTPUT_FILE", "value": output_file},
                            {"name": "RESULTS_BUCKET", "value": results_bucket},
                            {"name": "RESULTS_PREFIX", "value": results_prefix},
                            {"name": "REQUEST_ID", "value": request_id},
                            {"name": "MODEL_PORT", "value": "8080"},
                        ],
                    }
                ]
            },
            startedBy=f"urlmodel0-{request_id[:18]}-{uuid.uuid4().hex[:6]}",
        )

        failures = run.get("failures", [])
        if failures:
            raise RuntimeError(f"ECS run_task failed: {failures}")

        task_arn = run["tasks"][0]["taskArn"]
        waiter = self.ecs.get_waiter("tasks_stopped")
        waiter.wait(cluster=self.cluster_arn, tasks=[task_arn], WaiterConfig={"Delay": 10, "MaxAttempts": 180})

        described = self.ecs.describe_tasks(cluster=self.cluster_arn, tasks=[task_arn])["tasks"][0]
        scanner = next((c for c in described["containers"] if c["name"] == "scanner"), None)
        if not scanner:
            raise RuntimeError("Scanner container status was not found in task description.")
        if scanner.get("exitCode", 1) != 0:
            reason = scanner.get("reason") or scanner.get("lastStatus")
            raise RuntimeError(f"Scanner container failed with exitCode={scanner.get('exitCode')}, reason={reason}")

        result_key = f"{results_prefix.rstrip('/')}/{output_file}"
        return ECSRunResult(task_arn=task_arn, task_definition_arn=task_definition_arn, result_s3_key=result_key)
