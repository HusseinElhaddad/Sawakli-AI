from enum import StrEnum


class JobStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    ERROR = "ERROR"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    CANCELLED = "CANCELLED"


class ConnectorType(StrEnum):
    CSV = "csv"
    GA4 = "ga4"


class JobType(StrEnum):
    ANALYSIS = "ANALYSIS"
    SYNC = "SYNC"
