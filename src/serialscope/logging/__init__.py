"""Raw serial logging services."""

from serialscope.logging.raw_logger import RawLogger, RawLoggerError
from serialscope.logging.event_logger import EventLogger, EventLoggerError
from serialscope.logging.session import (
    RecordingSession,
    RecordingSessionError,
    SessionConfig,
    sanitize_session_name,
)
from serialscope.logging.structured_csv_logger import (
    StructuredCsvLogger,
    StructuredCsvLoggerError,
)
from serialscope.logging.multi_session import (
    MultiSourceRecordingSession,
    RecordingSourceConfig,
)
from serialscope.logging.recovery import (
    InterruptedRecording,
    RecordingRecoveryError,
    discard_interrupted_recording,
    find_interrupted_recordings,
    inspect_interrupted_recording,
    is_interrupted_recording,
    recover_interrupted_recording,
)

__all__ = [
    "RawLogger",
    "RawLoggerError",
    "EventLogger",
    "EventLoggerError",
    "RecordingSession",
    "RecordingSessionError",
    "SessionConfig",
    "StructuredCsvLogger",
    "StructuredCsvLoggerError",
    "sanitize_session_name",
    "MultiSourceRecordingSession",
    "RecordingSourceConfig",
    "InterruptedRecording",
    "RecordingRecoveryError",
    "discard_interrupted_recording",
    "find_interrupted_recordings",
    "inspect_interrupted_recording",
    "is_interrupted_recording",
    "recover_interrupted_recording",
]
