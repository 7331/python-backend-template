import logging

from app.shared.logging import LogEvent


class AccountSignedUp(LogEvent):
    message = "Account signed up with a passkey"
    operation = "account_sign_up"
    account_id: int


class AccountSignedIn(LogEvent):
    message = "Account signed in"
    operation = "account_sign_in"
    account_id: int
    account_passkey_id: int
    account_session_id: int


class AccountSignedOut(LogEvent):
    message = "Account signed out"
    operation = "account_sign_out"
    account_session_id: int


class PasskeyCeremonyRefused(LogEvent):
    level = logging.WARNING
    message = "Passkey ceremony refused"
    operation = "account_passkey_ceremony"
    ceremony: str
    reason: str
