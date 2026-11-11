from pydantic import BaseModel, ConfigDict, JsonValue


class ClaimedJob(BaseModel):
    model_config = ConfigDict(frozen=True)

    job_id: int
    job_kind: str
    payload: dict[str, JsonValue]
    attempt_count: int
    maximum_attempts: int

    def has_attempts_left(self) -> bool:
        return self.attempt_count < self.maximum_attempts


class ExpiredJob(BaseModel):
    model_config = ConfigDict(frozen=True)

    job_id: int
    job_kind: str
    attempt_count: int
