---
name: oci-sdk
description: |
  Oracle Cloud Infrastructure Python SDK 사용 패턴. "OCI launch_instance", "ComputeClient", "OCI 자격증명 검증", "AD 조회", "image OCID", "이미지 목록", "ARM A1 인스턴스 생성" 등에서 트리거.
  본 프로젝트 핵심 — Ampere A1 자동 신청에 사용. sync SDK 라 `asyncio.to_thread` 로 비동기 래핑.
---

# OCI Python SDK

본 프로젝트가 인스턴스 생성에 사용하는 공식 SDK 패턴.

## 자격증명 로딩

```python
import oci
from oci.config import validate_config

def build_config(cred: OciCredential, key_content: bytes, passphrase: str | None) -> dict:
    config = {
        "tenancy": cred.tenancy_ocid,
        "user": cred.user_ocid,
        "fingerprint": cred.fingerprint,
        "region": cred.region,
        "key_content": key_content.decode(),   # 또는 key_file 경로
        "pass_phrase": passphrase,
    }
    validate_config(config)
    return config
```

`private_key_path` 가 더 안전 (메모리에 키 안 둠):
```python
config = {
    "tenancy": cred.tenancy_ocid,
    ...,
    "key_file": cred.private_key_path,
    "pass_phrase": passphrase,
}
```

## 자격증명 유효성 검증

```python
def verify_credential(config: dict) -> tuple[bool, str | None]:
    try:
        client = oci.identity.IdentityClient(config)
        client.list_availability_domains(compartment_id=config["tenancy"])
        return True, None
    except oci.exceptions.ServiceError as e:
        return False, f"{e.code}: {e.message}"
    except Exception as e:
        return False, str(e)
```

## 인스턴스 생성 (LaunchInstance)

```python
import oci
from oci.core import ComputeClient
from oci.core.models import LaunchInstanceDetails, LaunchInstanceShapeConfigDetails, CreateVnicDetails

def build_launch_details(cfg: InstanceConfig, compartment_id: str) -> LaunchInstanceDetails:
    return LaunchInstanceDetails(
        availability_domain=cfg.availability_domain,
        compartment_id=compartment_id,
        display_name=cfg.name,
        shape=cfg.shape,                                        # "VM.Standard.A1.Flex"
        shape_config=LaunchInstanceShapeConfigDetails(
            ocpus=cfg.ocpus,
            memory_in_gbs=cfg.memory_gb,
        ),
        image_id=cfg.image_ocid,
        subnet_id=cfg.subnet_ocid,
        create_vnic_details=CreateVnicDetails(
            subnet_id=cfg.subnet_ocid,
            assign_public_ip=True,
        ),
        metadata={"ssh_authorized_keys": cfg.ssh_public_key},
    )

def launch(config: dict, details: LaunchInstanceDetails):
    client = ComputeClient(config)
    return client.launch_instance(details)   # returns Response with .data
```

## 예외 분기 (핵심)

```python
import oci.exceptions as oe

def classify(e: Exception) -> tuple[str, str]:
    """returns (status, message)"""
    if isinstance(e, oe.ServiceError):
        msg = (e.message or "").lower()
        if "out of host capacity" in msg or e.code == "InternalError" and "capacity" in msg:
            return "out_of_capacity", e.message
        if e.status == 429:
            return "rate_limited", e.message
        if e.code in {"NotAuthenticated", "NotAuthorizedOrNotFound", "InvalidParameter"} or e.status in {401, 403}:
            return "auth_error", f"{e.code}: {e.message}"
        return "other_error", f"{e.code}: {e.message}"
    return "other_error", str(e)
```

## 비동기 래핑

OCI SDK 는 sync. asyncio 환경에서:
```python
result = await asyncio.to_thread(client.launch_instance, details)
```

## 자주 쓰는 조회 API

| 작업 | 메서드 |
|---|---|
| AD 목록 | `IdentityClient.list_availability_domains(compartment_id)` |
| 이미지 목록 | `ComputeClient.list_images(compartment_id, operating_system="Canonical Ubuntu", shape="VM.Standard.A1.Flex")` |
| 서브넷 | `VirtualNetworkClient.list_subnets(compartment_id)` |
| compartment | tenancy_ocid 를 root compartment 로 사용 (단순 셋업) |

## ARM A1 이미지 OCID 찾기 (헬퍼)

```python
def find_ubuntu_a1_image(config: dict, compartment_id: str, version: str = "24.04") -> str | None:
    c = oci.core.ComputeClient(config)
    images = c.list_images(
        compartment_id=compartment_id,
        operating_system="Canonical Ubuntu",
        operating_system_version=version,
        shape="VM.Standard.A1.Flex",
        sort_by="TIMECREATED",
        sort_order="DESC",
    ).data
    return images[0].id if images else None
```

## 리전 vs Compartment

- `region` 은 config 의 일부 (`ap-chuncheon-1` 등)
- `compartment_id` 는 OCID — 기본은 tenancy OCID (root compartment)
- 다중 compartment 사용 시 별도 컬럼 필요 (현재 PRD 는 root 만 사용)

## 호출 빈도 / Rate Limit

- OCI 는 명시적 quota: tenancy + region 단위 (LaunchInstance 는 매우 보수적)
- 본 프로젝트: per-credential Semaphore(max=1) + 전역 Semaphore(max=10) + tenacity 백오프
- 같은 자격증명으로 동시에 다른 config 시도해도 직렬화됨

## 안티패턴

- private key 를 DB 에 평문 저장 → 파일로 저장 + passphrase 만 AES 암호화
- 자격증명 검증 없이 바로 launch_instance → 사전에 list_availability_domains 으로 ping
- `except Exception` 으로 묶음 처리 → `oci.exceptions.ServiceError` 명시적 분기
- 모든 호출 단일 ComputeClient 재사용 → 자격증명별로 빌드 (config dict 분리)
- compartment_id 를 user_ocid 로 혼동 → tenancy_ocid 가 root compartment
- 비동기 라우터에서 sync `client.launch_instance(...)` 직접 호출 → `asyncio.to_thread` 필수
