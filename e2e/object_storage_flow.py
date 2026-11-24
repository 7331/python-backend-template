from collections.abc import Mapping
import secrets
import sys
import time
import urllib.error
import urllib.request

from pydantic import BaseModel, ConfigDict, JsonValue

from flow_report import FlowReport
from flow_run import FlowStage, play_flow
from http_client import HttpReply, send_http_request, send_json_request
from software_passkey import RegistrationOptions, SoftwarePasskey
from stack_commands import (
    ComposeStack,
    StackCommandFailedError,
    build_public_base_url,
    read_database_value,
    run_compose,
)

DOWNLOAD_URL_LIFETIME_SECONDS = 5
OBJECT_STORAGE_FLOW_ENVIRONMENT_LINES = (
    f"STARTER_OBJECT_STORAGE_DOWNLOAD_URL_LIFETIME_SECONDS={DOWNLOAD_URL_LIFETIME_SECONDS}",
)
API_REQUEST_BODY_LIMIT_BYTES = 64 * 1024
FILE_SIZE_BYTES = 200_000
MAXIMUM_FILE_SIZE_BYTES = 10 * 1024 * 1024
FILE_CONTENT_TYPE = "image/png"
REFUSED_CONTENT_TYPE = "text/html"
BUCKET_REQUEST_TIMEOUT_SECONDS = 20
COMPOSE_COMMAND_TIMEOUT_SECONDS = 60
BUCKET_DIRECTORY = "/var/tmp/starter-app"  # noqa: S108  # the bucket server's data volume is mounted there
API_PREFIX = "/api/v1"
ACCOUNT_SESSION_COOKIE_NAME = "__Host-starter_account_session"
OWNER_USERNAME = "file_owner"
OTHER_USERNAME = "other_account"
DELETE_OWNER_ACCOUNT_AND_ROLL_BACK_STATEMENT = "BEGIN; DELETE FROM accounts WHERE username = 'file_owner'; ROLLBACK;"
FILE_UPLOAD_URLS_PER_WINDOW_PER_IP = 10
UPLOAD_SIGNED = "201"
FILE_STORED = "201"
FILE_READ = "200"
FILE_DELETED = "204"
SIGN_IN_REQUIRED = "401 unauthorized"
UPLOAD_NOT_SIGNED = "400 validation_error"
UPLOAD_NOT_FOUND = "404 upload_not_found"
FILE_NOT_FOUND = "404 file_not_found"
RATE_LIMITED = "429 rate_limited"


class BucketReply(BaseModel):
    model_config = ConfigDict(frozen=True)

    status_code: int
    content_type: str | None
    content_disposition: str | None
    body: bytes


class FileUploadBody(BaseModel):
    model_config = ConfigDict(frozen=True)

    upload_id: str
    upload_url: str
    upload_headers: dict[str, str]


class FileBody(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    file_id: str
    content_type: str
    size_bytes: int
    download_url: str


class FilesReply(BaseModel):
    model_config = ConfigDict(frozen=True)

    outcome: str
    body: bytes

    def read_file_upload(self) -> FileUploadBody:
        return FileUploadBody.model_validate_json(self.body)

    def read_file(self) -> FileBody:
        return FileBody.model_validate_json(self.body)


class ErrorBody(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    code: str


class ErrorReplyBody(BaseModel):
    model_config = ConfigDict(frozen=True)

    error: ErrorBody


class AccountBody(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    username: str


def build_files_reply(reply: HttpReply) -> FilesReply:
    if reply.status_code < 400:
        return FilesReply(outcome=str(reply.status_code), body=reply.body)
    return FilesReply(
        outcome=f"{reply.status_code} {ErrorReplyBody.model_validate_json(reply.body).error.code}", body=reply.body
    )


class FilesClient:
    def __init__(self, *, api_publish_port: int, session_cookie_value: str | None) -> None:
        self.api_publish_port = api_publish_port
        self.headers = {"Origin": build_public_base_url(api_publish_port), "Accept": "application/json"}
        if session_cookie_value is not None:
            self.headers["Cookie"] = f"{ACCOUNT_SESSION_COOKIE_NAME}={session_cookie_value}"

    def post_json(self, path: str, *, json_body: dict[str, JsonValue]) -> HttpReply:
        return send_json_request(
            f"{API_PREFIX}{path}",
            api_publish_port=self.api_publish_port,
            method="POST",
            headers=self.headers,
            json_body=json_body,
        )

    def send_file_request(self, file_id: str, *, method: str) -> FilesReply:
        return build_files_reply(
            send_http_request(
                f"{API_PREFIX}/files/{file_id}",
                api_publish_port=self.api_publish_port,
                method=method,
                headers=self.headers,
                body=None,
            )
        )

    def request_file_upload(self, content_type: str, *, size_bytes: int) -> FilesReply:
        return build_files_reply(
            self.post_json("/file-uploads", json_body={"content_type": content_type, "size_bytes": size_bytes})
        )

    def store_uploaded_file(self, upload_id: str) -> FilesReply:
        return build_files_reply(self.post_json("/files", json_body={"upload_id": upload_id}))

    def read_file(self, file_id: str) -> FilesReply:
        return self.send_file_request(file_id, method="GET")

    def delete_file(self, file_id: str) -> FilesReply:
        return self.send_file_request(file_id, method="DELETE")


def sign_up(flow_report: FlowReport, *, api_publish_port: int, username: str) -> FilesClient:
    signed_out_client = FilesClient(api_publish_port=api_publish_port, session_cookie_value=None)
    options_reply = signed_out_client.post_json(
        "/accounts/passkey/registration-options", json_body={"username": username}
    )
    flow_report.require_check(
        f"registration options for {username}",
        passed=options_reply.status_code == 200,
        detail=str(options_reply.status_code),
    )
    passkey = SoftwarePasskey(origin=build_public_base_url(api_publish_port))
    registration_reply = signed_out_client.post_json(
        "/accounts/passkey/registration",
        json_body={
            "credential": passkey.create_registration_credential(
                RegistrationOptions.model_validate_json(options_reply.body)
            )
        },
    )
    session_cookie_value = registration_reply.find_set_cookie_value(ACCOUNT_SESSION_COOKIE_NAME)
    flow_report.require_check(
        f"{username} signed up and signed in",
        passed=registration_reply.status_code == 201
        and AccountBody.model_validate_json(registration_reply.body).username == username
        and bool(session_cookie_value),
        detail=f"{registration_reply.status_code}, session cookie {'set' if session_cookie_value else 'missing'}",
    )
    return FilesClient(api_publish_port=api_publish_port, session_cookie_value=session_cookie_value)


def send_bucket_request(url: str, *, method: str, headers: Mapping[str, str], body: bytes | None) -> BucketReply:
    try:
        with urllib.request.urlopen(  # noqa: S310  # the URL is one the API signed for the stack's own bucket
            urllib.request.Request(url, data=body, headers=dict(headers), method=method),  # noqa: S310  # same URL
            timeout=BUCKET_REQUEST_TIMEOUT_SECONDS,
        ) as response:
            return BucketReply(
                status_code=response.status,
                content_type=response.headers.get("Content-Type"),
                content_disposition=response.headers.get("Content-Disposition"),
                body=response.read(),
            )
    except urllib.error.HTTPError as error_response:
        return BucketReply(
            status_code=error_response.code, content_type=None, content_disposition=None, body=error_response.read()
        )


def create_file_upload(flow_report: FlowReport, *, files_client: FilesClient, check_name: str) -> FileUploadBody:
    upload_reply = files_client.request_file_upload(FILE_CONTENT_TYPE, size_bytes=FILE_SIZE_BYTES)
    flow_report.require_check(
        check_name,
        passed=upload_reply.outcome == UPLOAD_SIGNED,
        detail=f"{upload_reply.outcome} for a {FILE_SIZE_BYTES} byte {FILE_CONTENT_TYPE}",
    )
    return upload_reply.read_file_upload()


def list_bucket_files(compose_stack: ComposeStack) -> list[str]:
    return run_compose(
        ["exec", "-T", "object-storage", "find", BUCKET_DIRECTORY, "-type", "f"],
        compose_stack=compose_stack,
        timeout_seconds=COMPOSE_COMMAND_TIMEOUT_SECONDS,
    ).split()


def check_api_refuses_what_it_would_not_sign(flow_report: FlowReport, *, files_client: FilesClient) -> None:
    wrong_type_reply = files_client.request_file_upload(REFUSED_CONTENT_TYPE, size_bytes=FILE_SIZE_BYTES)
    flow_report.record_check(
        "no upload is signed for a content type off the list",
        passed=wrong_type_reply.outcome == UPLOAD_NOT_SIGNED,
        detail=f"{wrong_type_reply.outcome} for {REFUSED_CONTENT_TYPE}",
    )
    oversized_reply = files_client.request_file_upload(FILE_CONTENT_TYPE, size_bytes=MAXIMUM_FILE_SIZE_BYTES + 1)
    flow_report.record_check(
        "no upload is signed over the size limit",
        passed=oversized_reply.outcome == UPLOAD_NOT_SIGNED,
        detail=f"{oversized_reply.outcome} for {MAXIMUM_FILE_SIZE_BYTES + 1} bytes",
    )
    never_uploaded = create_file_upload(
        flow_report, files_client=files_client, check_name="upload signed and then never used"
    )
    never_uploaded_reply = files_client.store_uploaded_file(never_uploaded.upload_id)
    flow_report.record_check(
        "an upload that never reached the bucket can't be stored",
        passed=never_uploaded_reply.outcome == UPLOAD_NOT_FOUND,
        detail=never_uploaded_reply.outcome,
    )


def check_bucket_refuses_what_was_not_signed(
    flow_report: FlowReport, *, file_upload: FileUploadBody, file_bytes: bytes
) -> None:
    oversized_reply = send_bucket_request(
        file_upload.upload_url, method="PUT", headers=file_upload.upload_headers, body=file_bytes + b"\x00"
    )
    flow_report.record_check(
        "the bucket refuses one byte more than was signed",
        passed=oversized_reply.status_code == 403,
        detail=f"{oversized_reply.status_code} for {len(file_bytes) + 1} bytes on a URL signed for {len(file_bytes)}",
    )
    wrong_type_reply = send_bucket_request(
        file_upload.upload_url, method="PUT", headers={"Content-Type": REFUSED_CONTENT_TYPE}, body=file_bytes
    )
    flow_report.record_check(
        "the bucket refuses another content type than was signed",
        passed=wrong_type_reply.status_code == 403,
        detail=f"{wrong_type_reply.status_code} for {REFUSED_CONTENT_TYPE} on a URL signed for {FILE_CONTENT_TYPE}",
    )
    other_key_reply = send_bucket_request(
        file_upload.upload_url.replace(file_upload.upload_id, secrets.token_urlsafe(24)),
        method="PUT",
        headers=file_upload.upload_headers,
        body=file_bytes,
    )
    flow_report.record_check(
        "the bucket refuses an upload URL moved to another key",
        passed=other_key_reply.status_code == 403,
        detail=f"{other_key_reply.status_code}",
    )


def check_upload_and_download(
    flow_report: FlowReport,
    *,
    compose_stack: ComposeStack,
    files_client: FilesClient,
    file_upload: FileUploadBody,
    file_bytes: bytes,
) -> FileBody:
    upload_reply = send_bucket_request(
        file_upload.upload_url, method="PUT", headers=file_upload.upload_headers, body=file_bytes
    )
    flow_report.require_check(
        "upload straight to the bucket",
        passed=upload_reply.status_code == 200,
        detail=(
            f"{upload_reply.status_code} for {len(file_bytes)} bytes, over the API's "
            f"{API_REQUEST_BODY_LIMIT_BYTES} byte body limit"
        ),
    )
    stored_reply = files_client.store_uploaded_file(file_upload.upload_id)
    flow_report.require_check(
        "uploaded file stored", passed=stored_reply.outcome == FILE_STORED, detail=stored_reply.outcome
    )
    stored_file = stored_reply.read_file()
    flow_report.record_check(
        "the stored size and content type are the bucket's",
        passed=stored_file.size_bytes == len(file_bytes) and stored_file.content_type == FILE_CONTENT_TYPE,
        detail=f"{stored_file.size_bytes} bytes, {stored_file.content_type}",
    )
    repeated_reply = files_client.store_uploaded_file(file_upload.upload_id)
    flow_report.record_check(
        "storing the same upload twice gives the same file",
        passed=repeated_reply.outcome == FILE_STORED
        and repeated_reply.read_file().file_id == stored_file.file_id
        and read_database_value("SELECT count(*) FROM files;", compose_stack=compose_stack) == "1",
        detail=f"{repeated_reply.outcome}, one row",
    )
    download_reply = send_bucket_request(stored_file.download_url, method="GET", headers={}, body=None)
    flow_report.record_check(
        "download returns the uploaded bytes as an attachment",
        passed=download_reply.status_code == 200
        and download_reply.body == file_bytes
        and download_reply.content_type == FILE_CONTENT_TYPE
        and download_reply.content_disposition == "attachment",
        detail=(
            f"{download_reply.status_code}, {len(download_reply.body)} bytes, same bytes: "
            f"{download_reply.body == file_bytes}, {download_reply.content_type}, {download_reply.content_disposition}"
        ),
    )
    repeated_upload_reply = send_bucket_request(
        file_upload.upload_url,
        method="PUT",
        headers=file_upload.upload_headers,
        body=secrets.token_bytes(len(file_bytes)),
    )
    unchanged_download_reply = send_bucket_request(stored_file.download_url, method="GET", headers={}, body=None)
    flow_report.record_check(
        "the upload URL used again after the file is stored can't change the file",
        passed=unchanged_download_reply.status_code == 200 and unchanged_download_reply.body == file_bytes,
        detail=(
            f"second upload {repeated_upload_reply.status_code}, download {unchanged_download_reply.status_code}, "
            f"still the first bytes: {unchanged_download_reply.body == file_bytes}"
        ),
    )
    return stored_file


def check_download_urls_are_refused(
    flow_report: FlowReport, *, files_client: FilesClient, stored_file: FileBody
) -> None:
    unsigned_reply = send_bucket_request(stored_file.download_url.split("?", 1)[0], method="GET", headers={}, body=None)
    flow_report.record_check(
        "the bucket refuses a download without a signature",
        passed=unsigned_reply.status_code == 403,
        detail=f"{unsigned_reply.status_code}",
    )
    tampered_reply = send_bucket_request(
        stored_file.download_url.replace(f"files/{stored_file.file_id}", f"pending/{stored_file.file_id}"),
        method="GET",
        headers={},
        body=None,
    )
    flow_report.record_check(
        "the bucket refuses a download URL moved to another key",
        passed=tampered_reply.status_code == 403,
        detail=f"{tampered_reply.status_code}",
    )
    time.sleep(DOWNLOAD_URL_LIFETIME_SECONDS + 2)
    expired_reply = send_bucket_request(stored_file.download_url, method="GET", headers={}, body=None)
    flow_report.record_check(
        "the bucket refuses an expired download URL",
        passed=expired_reply.status_code == 403,
        detail=f"{expired_reply.status_code}, {DOWNLOAD_URL_LIFETIME_SECONDS + 2} s after a {DOWNLOAD_URL_LIFETIME_SECONDS} s URL was signed",
    )
    fresh_file_reply = files_client.read_file(stored_file.file_id)
    flow_report.require_check(
        "file read again", passed=fresh_file_reply.outcome == FILE_READ, detail=fresh_file_reply.outcome
    )
    fresh_download_reply = send_bucket_request(
        fresh_file_reply.read_file().download_url, method="GET", headers={}, body=None
    )
    flow_report.record_check(
        "a newly signed download URL works",
        passed=fresh_download_reply.status_code == 200,
        detail=f"download {fresh_download_reply.status_code}",
    )


def check_delete_removes_object_and_row(
    flow_report: FlowReport, *, compose_stack: ComposeStack, files_client: FilesClient, stored_file: FileBody
) -> None:
    file_reply = files_client.read_file(stored_file.file_id)
    flow_report.require_check(
        "file read before the delete", passed=file_reply.outcome == FILE_READ, detail=file_reply.outcome
    )
    unexpired_download_url = file_reply.read_file().download_url
    delete_reply = files_client.delete_file(stored_file.file_id)
    flow_report.require_check("file deleted", passed=delete_reply.outcome == FILE_DELETED, detail=delete_reply.outcome)
    deleted_download_reply = send_bucket_request(unexpired_download_url, method="GET", headers={}, body=None)
    flow_report.record_check(
        "an unexpired download URL finds no object after the delete",
        passed=deleted_download_reply.status_code == 404,
        detail=f"{deleted_download_reply.status_code}",
    )
    missing_file_reply = files_client.read_file(stored_file.file_id)
    repeated_delete_reply = files_client.delete_file(stored_file.file_id)
    flow_report.record_check(
        "the API no longer knows the file",
        passed=missing_file_reply.outcome == FILE_NOT_FOUND and repeated_delete_reply.outcome == FILE_NOT_FOUND,
        detail=f"read {missing_file_reply.outcome}, second delete {repeated_delete_reply.outcome}",
    )
    row_count = read_database_value("SELECT count(*) FROM files;", compose_stack=compose_stack)
    bucket_files = list_bucket_files(compose_stack)
    flow_report.record_check(
        "the row and every copy of the object are gone",
        passed=row_count == "0" and not bucket_files,
        detail=f"{row_count} rows in files, {len(bucket_files)} objects left in {BUCKET_DIRECTORY}",
    )


def check_signed_out_requests_are_refused(
    flow_report: FlowReport, *, api_publish_port: int, stored_file: FileBody, file_upload: FileUploadBody
) -> None:
    signed_out_client = FilesClient(api_publish_port=api_publish_port, session_cookie_value=None)
    signed_out_outcomes = {
        "sign an upload": signed_out_client.request_file_upload(FILE_CONTENT_TYPE, size_bytes=FILE_SIZE_BYTES).outcome,
        "store": signed_out_client.store_uploaded_file(file_upload.upload_id).outcome,
        "read": signed_out_client.read_file(stored_file.file_id).outcome,
        "delete": signed_out_client.delete_file(stored_file.file_id).outcome,
    }
    flow_report.record_check(
        "without a session every file route answers 401",
        passed=all(outcome == SIGN_IN_REQUIRED for outcome in signed_out_outcomes.values()),
        detail=", ".join(f"{route_name} {outcome}" for route_name, outcome in signed_out_outcomes.items()),
    )


def check_other_account_finds_no_file(
    flow_report: FlowReport, *, other_client: FilesClient, stored_file: FileBody, file_upload: FileUploadBody
) -> None:
    other_read_reply = other_client.read_file(stored_file.file_id)
    flow_report.record_check(
        "another account can't read the file or get a download URL",
        passed=other_read_reply.outcome == FILE_NOT_FOUND and b"download_url" not in other_read_reply.body,
        detail=f"{other_read_reply.outcome}, the same answer as for a file that does not exist",
    )
    other_store_reply = other_client.store_uploaded_file(file_upload.upload_id)
    flow_report.record_check(
        "another account can't store the owner's upload",
        passed=other_store_reply.outcome == UPLOAD_NOT_FOUND,
        detail=other_store_reply.outcome,
    )
    other_delete_reply = other_client.delete_file(stored_file.file_id)
    flow_report.record_check(
        "another account can't delete the file",
        passed=other_delete_reply.outcome == FILE_NOT_FOUND,
        detail=other_delete_reply.outcome,
    )


def find_account_delete_refusal(compose_stack: ComposeStack) -> str | None:
    try:
        run_compose(
            [
                "exec",
                "-T",
                "postgres",
                "psql",
                "--no-psqlrc",
                "--quiet",
                "--set",
                "ON_ERROR_STOP=1",
                "--username",
                "starterapp",
                "--dbname",
                "starterapp",
            ],
            compose_stack=compose_stack,
            timeout_seconds=COMPOSE_COMMAND_TIMEOUT_SECONDS,
            input_text=DELETE_OWNER_ACCOUNT_AND_ROLL_BACK_STATEMENT,
        )
    except StackCommandFailedError as delete_refusal:
        return str(delete_refusal)
    return None


def check_account_with_files_can_not_be_deleted(flow_report: FlowReport, *, compose_stack: ComposeStack) -> None:
    delete_refusal = find_account_delete_refusal(compose_stack)
    flow_report.record_check(
        "Postgres refuses to delete an account that still owns a file",
        passed=delete_refusal is not None and "files_account_id_fkey" in delete_refusal,
        detail="foreign key files_account_id_fkey" if delete_refusal else "the delete went through",
    )


def check_account_without_files_can_be_deleted(flow_report: FlowReport, *, compose_stack: ComposeStack) -> None:
    delete_refusal = find_account_delete_refusal(compose_stack)
    flow_report.record_check(
        "the same delete goes through once the account's files are deleted",
        passed=delete_refusal is None,
        detail="deleted in a transaction that was rolled back" if delete_refusal is None else delete_refusal[-200:],
    )


def check_upload_urls_have_their_own_budget(
    flow_report: FlowReport, *, compose_stack: ComposeStack, files_client: FilesClient
) -> None:
    upload_outcomes: list[str] = []
    while len(upload_outcomes) <= FILE_UPLOAD_URLS_PER_WINDOW_PER_IP and RATE_LIMITED not in upload_outcomes:
        upload_outcomes.append(files_client.request_file_upload(FILE_CONTENT_TYPE, size_bytes=FILE_SIZE_BYTES).outcome)
    other_route_reply = files_client.read_file(secrets.token_urlsafe(24))
    budget_scope_count = read_database_value(
        "SELECT count(*) FROM rate_limit_scopes WHERE scope LIKE 'file_upload_url:%';", compose_stack=compose_stack
    )
    flow_report.record_check(
        "signing upload URLs has its own budget per address, kept in Postgres",
        passed=upload_outcomes[-1] == RATE_LIMITED
        and other_route_reply.outcome == FILE_NOT_FOUND
        and budget_scope_count == "1",
        detail=(
            f"{upload_outcomes[-1]} after {len(upload_outcomes) - 1} more signed in a row, another route still answers "
            f"{other_route_reply.outcome}, {budget_scope_count} file_upload_url scope in rate_limit_scopes"
        ),
    )


def walk_file_journey(flow_stage: FlowStage) -> None:
    flow_report = flow_stage.flow_report
    compose_stack = flow_stage.compose_stack
    api_publish_port = flow_stage.api_publish_port
    file_bytes = secrets.token_bytes(FILE_SIZE_BYTES)
    files_client = sign_up(flow_report, api_publish_port=api_publish_port, username=OWNER_USERNAME)
    other_client = sign_up(flow_report, api_publish_port=api_publish_port, username=OTHER_USERNAME)
    check_api_refuses_what_it_would_not_sign(flow_report, files_client=files_client)
    file_upload = create_file_upload(flow_report, files_client=files_client, check_name="upload signed")
    check_bucket_refuses_what_was_not_signed(flow_report, file_upload=file_upload, file_bytes=file_bytes)
    stored_file = check_upload_and_download(
        flow_report,
        compose_stack=compose_stack,
        files_client=files_client,
        file_upload=file_upload,
        file_bytes=file_bytes,
    )
    check_signed_out_requests_are_refused(
        flow_report, api_publish_port=api_publish_port, stored_file=stored_file, file_upload=file_upload
    )
    check_other_account_finds_no_file(
        flow_report, other_client=other_client, stored_file=stored_file, file_upload=file_upload
    )
    check_account_with_files_can_not_be_deleted(flow_report, compose_stack=compose_stack)
    check_download_urls_are_refused(flow_report, files_client=files_client, stored_file=stored_file)
    check_delete_removes_object_and_row(
        flow_report, compose_stack=compose_stack, files_client=files_client, stored_file=stored_file
    )
    check_account_without_files_can_be_deleted(flow_report, compose_stack=compose_stack)
    check_upload_urls_have_their_own_budget(flow_report, compose_stack=compose_stack, files_client=files_client)


if __name__ == "__main__":
    sys.exit(
        0
        if play_flow(
            "object_storage",
            flow_environment_lines=OBJECT_STORAGE_FLOW_ENVIRONMENT_LINES,
            walk_journey=walk_file_journey,
        )
        else 1
    )
