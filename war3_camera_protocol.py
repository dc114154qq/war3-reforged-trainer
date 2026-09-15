"""Current-engine 24268 camera and screen snapshot ABI."""
import math
import struct


WORK_SIZE = 256
ABI = struct.pack("<3I", 0x2426801B, 216, WORK_SIZE)
SIGNATURES = (
    ("GetCameraTargetPositionX", "()R"),
    ("GetCameraTargetPositionY", "()R"),
    ("GetCameraTargetPositionZ", "()R"),
    ("GetCameraEyePositionX", "()R"),
    ("GetCameraEyePositionY", "()R"),
    ("GetCameraEyePositionZ", "()R"),
    ("GetCameraField", "(Hcamerafield;)R"),
    ("ConvertCameraField", "(I)Hcamerafield;"),
    ("GetCameraMargin", "(I)R"),
    ("BlzGetMouseScreenPosX", "()I"),
    ("BlzGetMouseScreenPosY", "()I"),
)


def build_work(entries, tls):
    pointers = []
    for name, signature in SIGNATURES:
        entry = entries.get(name)
        if entry is None or entry.name != name or entry.signature != signature:
            raise ValueError("Camera native signature differs: " + name)
        pointers.append(entry.handler)
    payload = struct.pack(
        "<12Q18f6I",
        *pointers, tls,
        *([0.0] * 18),
        0, 0, 0, 0, 0, 0,
    ) + bytes(WORK_SIZE - 192)
    validate_work(payload)
    return payload


def _finite(value):
    return math.isfinite(float(value)) and abs(float(value)) <= 1_000_000_000.0


def validate_work(payload):
    if len(payload) != WORK_SIZE:
        raise ValueError("CameraWork must contain exactly 256 bytes")
    pointers = struct.unpack_from("<11Q", payload, 0)
    tls = struct.unpack_from("<Q", payload, 88)[0]
    if (any(not 0x10000 <= pointer < 0x800000000000 for pointer in pointers)
            or len(set(pointers)) != len(pointers)
            or not 0x10000 <= tls < 0x800000000000 or tls % 8
            or any(payload[192:])):
        raise ValueError("CameraWork contains invalid pointers or nonzero outputs")


def decode_work(payload, _expected_count=None):
    if len(payload) != WORK_SIZE:
        raise ValueError("Incomplete camera snapshot")
    floats = struct.unpack_from("<18f", payload, 96)
    target_x, target_y, target_z, eye_x, eye_y, eye_z = floats[:6]
    fields = tuple(floats[6:14])
    margins = tuple(floats[14:18])
    screen_x, screen_y, changed, error, completed, reserved = struct.unpack_from(
        "<6I", payload, 168,
    )
    if (error or reserved or completed != 1 or changed != 1
            or not all(_finite(value) for value in floats)):
        raise ValueError(
            f"Camera snapshot incomplete: error={error}, completed={completed}, changed={changed}"
        )
    return dict(target=(target_x, target_y, target_z), eye=(eye_x, eye_y, eye_z),
                fields=fields, margins=margins, screen=(screen_x, screen_y), changed=changed,
                count=1, completed=completed)
