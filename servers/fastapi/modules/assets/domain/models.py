from enum import Enum


class AssetState(str, Enum):
    UPLOADING = "UPLOADING"
    QUARANTINED = "QUARANTINED"
    SCANNING = "SCANNING"
    READY = "READY"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    DELETING = "DELETING"
    DELETED = "DELETED"


class MalwareScanStatus(str, Enum):
    PENDING = "PENDING"
    CLEAN = "CLEAN"
    INFECTED = "INFECTED"
    ERROR = "ERROR"
    UNAVAILABLE = "UNAVAILABLE"


class RetentionClass(str, Enum):
    TEMPORARY = "TEMPORARY"
    WORKSPACE = "WORKSPACE"
    DERIVED = "DERIVED"
    EXPORT = "EXPORT"


class UploadState(str, Enum):
    CREATED = "CREATED"
    UPLOADING = "UPLOADING"
    COMPLETED = "COMPLETED"
    ABORTED = "ABORTED"
    EXPIRED = "EXPIRED"
