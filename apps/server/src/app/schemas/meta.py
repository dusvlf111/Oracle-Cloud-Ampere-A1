"""OCI metadata lookup schemas (PRD §7.2, §8 /api/meta/*).

Used by the config-create form to populate image / subnet / availability-domain
dropdowns instead of manual OCID paste. Availability domains are returned as a
bare ``list[str]`` (no wrapper schema needed).
"""

from __future__ import annotations

from pydantic import BaseModel


class ImageOption(BaseModel):
    ocid: str
    display_name: str
    operating_system: str
    os_version: str


class SubnetOption(BaseModel):
    ocid: str
    display_name: str
    cidr_block: str
