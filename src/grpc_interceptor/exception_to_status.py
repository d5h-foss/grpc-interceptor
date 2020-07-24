"""ExceptionToStatusInterceptor catches GrpcException and sets the gRPC context."""

from typing import Any, Callable, Optional

import grpc

from grpc_interceptor.exceptions import GrpcException
from grpc_interceptor.server import ServerInterceptor


class ExceptionToStatusInterceptor(ServerInterceptor):
    """An interceptor that catches exceptions and sets the RPC status and details.

    ExceptionToStatusInterceptor will catch any subclass of GrpcException and set the
    status code and details on the gRPC context.

    Args:
        status_on_unknown_exception: Specify what to do if an exception which is
            not a subclass of GrpcException is raised. If None, do nothing (by
            default, grpc will set the status to UNKNOWN). If not None, then the
            status code will be set to this value. It must not be OK. The details
            will be set to the value of repr(e), where e is the exception. In any
            case, the exception will be propagated.

    Raises:
        ValueError: If status_code is OK.
    """

    def __init__(self, status_on_unknown_exception: Optional[grpc.StatusCode] = None):
        if status_on_unknown_exception == grpc.StatusCode.OK:
            raise ValueError("The status code for unknown exceptions cannot be OK")
        self._status_on_unknown_exception = status_on_unknown_exception

    def intercept(
        self,
        method: Callable,
        request: Any,
        context: grpc.ServicerContext,
        method_name: str,
    ) -> Any:
        """Do not call this directly; use the interceptor kwarg on grpc.server()."""
        try:
            return method(request, context)
        except GrpcException as e:
            context.set_code(e.status_code)
            context.set_details(e.details)
            raise
        except Exception as e:
            if self._status_on_unknown_exception is not None:
                context.set_code(self._status_on_unknown_exception)
                context.set_details(repr(e))
            raise
