from typing import Optional

from grpc import StatusCode


class GrpcException(Exception):
    status_code: StatusCode = StatusCode.UNKNOWN
    details: str = "Unknown exception occurred"

    def __init__(
        self, status_code: Optional[StatusCode] = None, details: Optional[str] = None
    ):
        if status_code is not None:
            if status_code == StatusCode.OK:
                raise ValueError("The status code for an exception cannot be OK")
            self.status_code = status_code
        if details is not None:
            self.details = details

    def __repr__(self):
        clsname = self.__class__.__name__
        sc = self.status_code.name
        return f"{clsname}(status_code={sc}, details={self.details!r})"


class Aborted(GrpcException):
    status_code = StatusCode.ABORTED
    details = "The operation was aborted"


class AlreadyExists(GrpcException):
    status_code = StatusCode.ALREADY_EXISTS
    details = "The entity attempted to be created already exists"


class Cancelled(GrpcException):
    status_code = StatusCode.CANCELLED
    details = "The operation was cancelled"


class DataLoss(GrpcException):
    status_code = StatusCode.DATA_LOSS
    details = "There was unrecoverable data loss or corruption"


class DeadlineExceeded(GrpcException):
    status_code = StatusCode.DEADLINE_EXCEEDED
    details = "Deadline expired before operation could complete"


class FailedPrecondition(GrpcException):
    status_code = StatusCode.FAILED_PRECONDITION
    details = (
        "The operation was rejected because the system is not"
        " in a state required for execution"
    )


class InvalidArgument(GrpcException):
    status_code = StatusCode.INVALID_ARGUMENT
    details = "The client specified an invalid argument"


class Internal(GrpcException):
    status_code = StatusCode.INTERNAL
    details = "Internal error"


class OutOfRange(GrpcException):
    status_code = StatusCode.OUT_OF_RANGE
    details = "The operation was attempted past the valid range"


class NotFound(GrpcException):
    status_code = StatusCode.NOT_FOUND
    details = "The requested entity was not found"


class PermissionDenied(GrpcException):
    status_code = StatusCode.PERMISSION_DENIED
    details = "The caller does not have permission to execute the specified operation"


class ResourceExhausted(GrpcException):
    status_code = StatusCode.RESOURCE_EXHAUSTED
    details = "A resource has been exhausted"


class Unauthenticated(GrpcException):
    status_code = StatusCode.UNAUTHENTICATED
    details = (
        "The request does not have valid authentication credentials for the operation"
    )


class Unavailable(GrpcException):
    status_code = StatusCode.UNAVAILABLE
    details = "The service is currently unavailable"


class Unimplemented(GrpcException):
    status_code = StatusCode.UNIMPLEMENTED
    details = (
        "The operation is not implemented or not supported/enabled in this service"
    )


class Unknown(GrpcException):
    pass
