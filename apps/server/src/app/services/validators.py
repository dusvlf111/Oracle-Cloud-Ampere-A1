"""Input validation + normalisation helpers (hardening task §1).

Production logs showed users pasting OCID / fingerprint values with stray
whitespace and newlines (``'user': 'malformed'`` from OCI) and malformed
image / subnet OCIDs that made the worker retry an impossible request forever.

These helpers are the single source of truth for:

- ``normalize_str`` — strip leading/trailing whitespace AND collapse internal
  newlines (used by Pydantic ``mode="before"`` validators and the credentials
  multipart Form router, which does not go through a Pydantic body).
- the compiled regexes for each OCID flavour / fingerprint / region.

Both the Pydantic schemas (configs) and the Form-based credentials router
import from here so validation rules never drift between the two entry points.
"""

from __future__ import annotations

import re

# --- compiled patterns -----------------------------------------------------
TENANCY_OCID_RE = re.compile(r"^ocid1\.tenancy\.")
USER_OCID_RE = re.compile(r"^ocid1\.user\.")
IMAGE_OCID_RE = re.compile(r"^ocid1\.image\.")
SUBNET_OCID_RE = re.compile(r"^ocid1\.subnet\.")
FINGERPRINT_RE = re.compile(r"^([0-9a-f]{2}:){15}[0-9a-f]{2}$")
REGION_RE = re.compile(r"^[a-z]{2}-[a-z]+-\d$")
# SSH public key: ssh-rsa / ssh-ed25519 / ecdsa-sha2-* then a base64 blob.
SSH_PUBLIC_KEY_RE = re.compile(r"^(ssh-(rsa|ed25519)|ecdsa-sha2-\S+) \S+")


def normalize_str(value: object) -> object:
    """Strip surrounding whitespace and remove internal CR/LF.

    Used as a Pydantic ``mode="before"`` validator and by the credentials Form
    router. Non-str values pass through untouched so Pydantic can raise its own
    type error.
    """
    if not isinstance(value, str):
        return value
    # Drop CR/LF anywhere (pasted multi-line secrets) then strip the rest.
    collapsed = value.replace("\r", "").replace("\n", "")
    return collapsed.strip()


def normalize_ssh_key(value: object) -> object:
    """Like :func:`normalize_str` but joins a multi-line key into one line.

    Some clients wrap the key blob; OCI wants a single line. Internal newlines
    become a single space, then collapse repeated whitespace.
    """
    if not isinstance(value, str):
        return value
    joined = re.sub(r"\s+", " ", value.replace("\r", "").replace("\n", " "))
    return joined.strip()


def validate_pattern(value: str, pattern: re.Pattern[str], message: str) -> str:
    if not pattern.match(value):
        raise ValueError(message)
    return value
