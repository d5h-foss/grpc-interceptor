"""ExceptionToStatusInterceptor catches GrpcException and sets the gRPC context."""

from typing import Any, Callable

import grpc

from grpc_interceptor.base import Interceptor
from grpc_interceptor.exceptions import GrpcException


class ExceptionToStatusInterceptor(Interceptor):
    """An interceptor that catches exceptions and sets the RPC status and details.

    ExceptionToStatusInterceptor will catch any subclass of GrpcException and set the
    status code and details on the gRPC context.
    """

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
