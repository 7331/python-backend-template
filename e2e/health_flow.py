import sys

from flow_report import FlowReport
from flow_run import FlowStage, play_flow
from http_client import send_http_request

EXPECTED_HEALTH_BODY = b'{"status":"ok"}'


def check_health(flow_report: FlowReport, *, api_publish_port: int) -> None:
    health_reply = send_http_request("/health", api_publish_port=api_publish_port, method="GET", headers={}, body=None)
    flow_report.record_check(
        "health",
        passed=health_reply.status_code == 200 and health_reply.body == EXPECTED_HEALTH_BODY,
        detail=f"{health_reply.status_code} {health_reply.body!r}",
    )
    readiness_reply = send_http_request(
        "/ready", api_publish_port=api_publish_port, method="GET", headers={}, body=None
    )
    flow_report.record_check(
        "readiness",
        passed=readiness_reply.status_code == 200 and readiness_reply.body == EXPECTED_HEALTH_BODY,
        detail=f"{readiness_reply.status_code} {readiness_reply.body!r}",
    )


def walk_health_journey(flow_stage: FlowStage) -> None:
    check_health(flow_stage.flow_report, api_publish_port=flow_stage.api_publish_port)


if __name__ == "__main__":
    sys.exit(0 if play_flow("health", flow_environment_lines=(), walk_journey=walk_health_journey) else 1)
