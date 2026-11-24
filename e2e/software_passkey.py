import base64
from enum import StrEnum
import hashlib
import json
import secrets

import cbor2
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from pydantic import BaseModel, ConfigDict, Field, JsonValue

USER_PRESENT_FLAG = 0x01
USER_VERIFIED_FLAG = 0x04
ATTESTED_CREDENTIAL_DATA_FLAG = 0x40
COSE_KEY_TYPE_LABEL = 1
COSE_ALGORITHM_LABEL = 3
COSE_CURVE_LABEL = -1
COSE_X_COORDINATE_LABEL = -2
COSE_Y_COORDINATE_LABEL = -3
COSE_KEY_TYPE_EC2 = 2
COSE_ALGORITHM_ES256 = -7
COSE_CURVE_P256 = 1
P256_COORDINATE_BYTES = 32
CREDENTIAL_ID_BYTES = 32
EMPTY_AUTHENTICATOR_AAGUID = bytes(16)


class ClientDataType(StrEnum):
    CREATE = "webauthn.create"
    GET = "webauthn.get"


class RelyingPartyOptions(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str


class UserOptions(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str


class RegistrationOptions(BaseModel):
    model_config = ConfigDict(frozen=True)

    challenge: str
    rp: RelyingPartyOptions
    user: UserOptions


class AuthenticationOptions(BaseModel):
    model_config = ConfigDict(frozen=True)

    challenge: str
    relying_party_id: str = Field(validation_alias="rpId")


def encode_base64url(raw_bytes: bytes) -> str:
    return base64.urlsafe_b64encode(raw_bytes).rstrip(b"=").decode()


def decode_base64url(encoded_text: str) -> bytes:
    return base64.urlsafe_b64decode(encoded_text + "=" * (-len(encoded_text) % 4))


def hash_relying_party_id(relying_party_id: str) -> bytes:
    return hashlib.sha256(relying_party_id.encode()).digest()


class SoftwarePasskey:
    def __init__(self, *, origin: str) -> None:
        self.origin = origin
        self.private_key = ec.generate_private_key(ec.SECP256R1())
        self.credential_id = secrets.token_bytes(CREDENTIAL_ID_BYTES)
        self.sign_count = 0
        self.user_handle = b""

    def build_client_data_json(self, challenge: str, *, client_data_type: ClientDataType) -> bytes:
        client_data = {
            "type": client_data_type.value,
            "challenge": challenge,
            "origin": self.origin,
            "crossOrigin": False,
        }
        return json.dumps(client_data, separators=(",", ":")).encode()

    def build_cose_public_key(self) -> bytes:
        public_numbers = self.private_key.public_key().public_numbers()
        return cbor2.dumps(
            {
                COSE_KEY_TYPE_LABEL: COSE_KEY_TYPE_EC2,
                COSE_ALGORITHM_LABEL: COSE_ALGORITHM_ES256,
                COSE_CURVE_LABEL: COSE_CURVE_P256,
                COSE_X_COORDINATE_LABEL: public_numbers.x.to_bytes(P256_COORDINATE_BYTES, "big"),
                COSE_Y_COORDINATE_LABEL: public_numbers.y.to_bytes(P256_COORDINATE_BYTES, "big"),
            }
        )

    def create_registration_credential(self, registration_options: RegistrationOptions) -> dict[str, JsonValue]:
        self.user_handle = decode_base64url(registration_options.user.id)
        authenticator_data = (
            hash_relying_party_id(registration_options.rp.id)
            + bytes([USER_PRESENT_FLAG | USER_VERIFIED_FLAG | ATTESTED_CREDENTIAL_DATA_FLAG])
            + self.sign_count.to_bytes(4, "big")
            + EMPTY_AUTHENTICATOR_AAGUID
            + len(self.credential_id).to_bytes(2, "big")
            + self.credential_id
            + self.build_cose_public_key()
        )
        attestation_object = cbor2.dumps({"fmt": "none", "attStmt": {}, "authData": authenticator_data})
        client_data_json = self.build_client_data_json(
            registration_options.challenge, client_data_type=ClientDataType.CREATE
        )
        return {
            "id": encode_base64url(self.credential_id),
            "rawId": encode_base64url(self.credential_id),
            "type": "public-key",
            "authenticatorAttachment": "platform",
            "clientExtensionResults": {},
            "response": {
                "clientDataJSON": encode_base64url(client_data_json),
                "attestationObject": encode_base64url(attestation_object),
                "transports": ["internal"],
            },
        }

    def create_authentication_credential(self, authentication_options: AuthenticationOptions) -> dict[str, JsonValue]:
        self.sign_count += 1
        authenticator_data = (
            hash_relying_party_id(authentication_options.relying_party_id)
            + bytes([USER_PRESENT_FLAG | USER_VERIFIED_FLAG])
            + self.sign_count.to_bytes(4, "big")
        )
        client_data_json = self.build_client_data_json(
            authentication_options.challenge, client_data_type=ClientDataType.GET
        )
        signature = self.private_key.sign(
            authenticator_data + hashlib.sha256(client_data_json).digest(), ec.ECDSA(hashes.SHA256())
        )
        return {
            "id": encode_base64url(self.credential_id),
            "rawId": encode_base64url(self.credential_id),
            "type": "public-key",
            "authenticatorAttachment": "platform",
            "clientExtensionResults": {},
            "response": {
                "clientDataJSON": encode_base64url(client_data_json),
                "authenticatorData": encode_base64url(authenticator_data),
                "signature": encode_base64url(signature),
                "userHandle": encode_base64url(self.user_handle),
            },
        }
