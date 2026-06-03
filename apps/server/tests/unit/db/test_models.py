"""Domain model relationship tests (PRD §6).

Covers relationship navigation:
  - credential -> configs (one-to-many)
  - config <-> channels (many-to-many via ConfigChannelLink)
  - attempt -> config (many-to-one)

Factories are defined with polyfactory (PRD §4 test stack).
"""

from __future__ import annotations

import pytest
from polyfactory.factories.pydantic_factory import ModelFactory
from sqlmodel import Session, select

from app.db.models import (
    Attempt,
    ConfigChannelLink,
    InstanceConfig,
    NotificationChannel,
    OciCredential,
)


class OciCredentialFactory(ModelFactory[OciCredential]):
    __model__ = OciCredential
    __set_as_default_factory_for_type__ = False

    id = None
    passphrase_enc = None


class InstanceConfigFactory(ModelFactory[InstanceConfig]):
    __model__ = InstanceConfig

    id = None
    max_attempts = None


def _make_credential(session: Session, **overrides) -> OciCredential:
    cred = OciCredentialFactory.build(**overrides)
    cred.id = None
    session.add(cred)
    session.commit()
    session.refresh(cred)
    return cred


def _make_config(session: Session, credential_id: int, **overrides) -> InstanceConfig:
    cfg = InstanceConfigFactory.build(credential_id=credential_id, **overrides)
    cfg.id = None
    session.add(cfg)
    session.commit()
    session.refresh(cfg)
    return cfg


def test_credential_to_configs_relationship(session: Session) -> None:
    cred = _make_credential(session, name="acct-a")
    _make_config(session, cred.id, name="cfg-1")
    _make_config(session, cred.id, name="cfg-2")

    session.refresh(cred)
    assert {c.name for c in cred.configs} == {"cfg-1", "cfg-2"}
    # back-reference resolves
    assert cred.configs[0].credential.id == cred.id


def test_config_channel_many_to_many(session: Session) -> None:
    cred = _make_credential(session, name="acct-b")
    cfg = _make_config(session, cred.id, name="cfg-m2m")

    ch1 = NotificationChannel(name="disc", type="discord", config_enc="x")
    ch2 = NotificationChannel(name="ntfy", type="ntfy", config_enc="y")
    cfg.notification_channels.extend([ch1, ch2])
    session.add(cfg)
    session.commit()
    session.refresh(cfg)

    assert {c.name for c in cfg.notification_channels} == {"disc", "ntfy"}
    # reverse navigation: channel -> configs
    session.refresh(ch1)
    assert cfg in ch1.configs

    # link rows exist
    links = session.exec(select(ConfigChannelLink)).all()
    assert len(links) == 2


def test_attempt_to_config_relationship(session: Session) -> None:
    cred = _make_credential(session, name="acct-c")
    cfg = _make_config(session, cred.id, name="cfg-attempts")

    a = Attempt(config_id=cfg.id, status="out_of_capacity", message="no capacity")
    session.add(a)
    session.commit()
    session.refresh(a)
    session.refresh(cfg)

    assert a.config.id == cfg.id
    assert cfg.attempts[0].status == "out_of_capacity"


def test_channel_name_unique(session: Session) -> None:
    from sqlalchemy.exc import IntegrityError

    session.add(NotificationChannel(name="dup", type="ntfy", config_enc="a"))
    session.commit()
    session.add(NotificationChannel(name="dup", type="discord", config_enc="b"))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_credential_name_unique(session: Session) -> None:
    from sqlalchemy.exc import IntegrityError

    _make_credential(session, name="only-one")
    with pytest.raises(IntegrityError):
        _make_credential(session, name="only-one")
    session.rollback()
