"""ExceptionToStatusInterceptor catches GrpcException and sets the gRPC context."""

from contextlib import contextmanager
from typing import Any, Callable, Generator, Optional

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

    def _generate_responses(self, context, responses):
        """Yield all the responses, but check for errors along the way."""
        with self._handle_exceptions(context, reraise=False):
            yield from responses

    @contextmanager
    def _handle_exceptions(self, context, *, reraise: bool):
        try:
            yield
        except GrpcException as e:
            context.set_code(e.status_code)
            context.set_details(e.details)
            if reraise:
                raise
        except Exception as e:
            if self._status_on_unknown_exception is not None:
                context.set_code(self._status_on_unknown_exception)
                context.set_details(repr(e))
                if reraise:
                    raise
            else:
                raise

    def intercept(
        self,
        method: Callable,
        request: Any,
        context: grpc.ServicerContext,
        method_name: str,
    ) -> Any:
        """Do not call this directly; use the interceptor kwarg on grpc.server()."""
        with self._handle_exceptions(context, reraise=True):
            responses = method(request, context)

        if isinstance(responses, Generator):
            # multiple responses; return a generator
            return self._generate_responses(context, responses)
        else:
            # return a single response
            return responses
