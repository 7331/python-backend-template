from collections.abc import Mapping
import json
import urllib.error
import urllib.request

from pydantic import BaseModel, ConfigDict

REQUEST_TIMEOUT_SECONDS = 5


class HttpReply(BaseModel):
    model_config = ConfigDict(frozen=True)

    status_code: int
    set_cookie_headers: tuple[str, ...]
    body: bytes

    def find_set_cookie_value(self, cookie_name: str) -> str | None:
        for set_cookie_header in self.set_cookie_headers:
            name, separator, value = set_cookie_header.split(";", 1)[0].partition("=")
            if separator and name.strip() == cookie_name:
                return value.strip()
        return None


def send_http_request(
    path: str, *, api_publish_port: int, method: str, headers: Mapping[str, str], body: bytes | None
) -> HttpReply:
    try:
        with urllib.request.urlopen(
            urllib.request.Request(
                f"http://127.0.0.1:{api_publish_port}{path}", data=body, headers=dict(headers), method=method
            ),
            timeout=REQUEST_TIMEOUT_SECONDS,
        ) as response:
            return HttpReply(
                status_code=response.status,
                set_cookie_headers=tuple(response.headers.get_all("Set-Cookie") or ()),
                body=response.read(),
            )
    except urllib.error.HTTPError as error_response:
        return HttpReply(
            status_code=error_response.code,
            set_cookie_headers=tuple(error_response.headers.get_all("Set-Cookie") or ()),
            body=error_response.read(),
        )


def send_json_request(
    path: str, *, api_publish_port: int, method: str, headers: Mapping[str, str], json_body: object
) -> HttpReply:
    return send_http_request(
        path,
        api_publish_port=api_publish_port,
        method=method,
        headers={**headers, "Content-Type": "application/json"},
        body=json.dumps(json_body).encode(),
    )
