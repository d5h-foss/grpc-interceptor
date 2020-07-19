"""Base class for server-side interceptors."""

import abc
from typing import Any, Callable

import grpc


class Interceptor(grpc.ServerInterceptor, metaclass=abc.ABCMeta):
    """Base class for server-side interceptors.

    To implement an interceptor, subclass this class and override the intercept method.
    """

    @abc.abstractmethod
    def intercept(
        self,
        method: Callable,
        request: Any,
        context: grpc.ServicerContext,
        method_name: str,
    ) -> Any:
        """Override this method to implement a custom interceptor.

        You should call method(request, context) to invoke the next handler (either the
        RPC method implementation, or the next interceptor in the list).

        Args:
            method: Either the RPC method implementation, or the next interceptor in
                the chain.
            request: The RPC request, as a protobuf message.
            context: The ServicerContext pass by gRPC to the service.
            method_name: A string of the form "protobuf.package.Service/Method"

        Returns:
            This should generally return the result of method(request, context), which
            is typically the RPC method response, as a protobuf message. The
            interceptor is free to modify this in some way, however.
        """
        return method(request, context)

    # Implementation of grpc.ServerInterceptor, do not override.
    def intercept_service(self, continuation, handler_call_details):
        """Implementation of grpc.ServerInterceptor.

        This is not part of the Interceptor API, but must have a public name. Do not
        override it, unless you know what you're doing.
        """
        next_handler = continuation(handler_call_details)
        # Make sure it's unary_unary:
        if next_handler.request_streaming or next_handler.response_streaming:
            raise ValueError("Interceptor only handles unary_unary")

        def invoke_intercept_method(request, context):
            next_interceptor_or_implementation = next_handler.unary_unary
            method_name = handler_call_details.method
            return self.intercept(
                next_interceptor_or_implementation, request, context, method_name,
            )

        return grpc.unary_unary_rpc_method_handler(
            invoke_intercept_method,
            request_deserializer=next_handler.request_deserializer,
            response_serializer=next_handler.response_serializer,
        )
