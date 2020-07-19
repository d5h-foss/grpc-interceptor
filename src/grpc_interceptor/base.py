import abc
from typing import Any, Callable

import grpc


class Interceptor(grpc.ServerInterceptor, metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def intercept(
        self,
        method: Callable,
        request: Any,
        context: grpc.ServicerContext,
        method_name: str,
    ) -> Any:
        return method(request, context)

    # Implementation of grpc.ServerInterceptor, do not override.
    def intercept_service(self, continuation, handler_call_details):
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
