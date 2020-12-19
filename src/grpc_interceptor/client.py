"""Base class for client-side interceptors."""

import abc
from typing import Any, Callable, Iterator, Optional, Tuple

import grpc


class ClientInterceptor(
    grpc.UnaryUnaryClientInterceptor,
    grpc.UnaryStreamClientInterceptor,
    grpc.StreamUnaryClientInterceptor,
    grpc.StreamStreamClientInterceptor,
    metaclass=abc.ABCMeta,
):
    """Base class for client-side interceptors.

    To implement an interceptor, subclass this class and override the intercept method.
    """

    @abc.abstractmethod
    def intercept(
        self,
        method: Callable,
        request_or_iterator: Any,
        call_details: grpc.ClientCallDetails,
    ) -> Tuple[grpc.ClientCallDetails, Iterator[Any], Optional[Callable]]:
        """Override this method to implement a custom interceptor.

        This method is called for all unary and streaming RPCs. The interceptor
        implementation should call `method` using a `grpc.ClientCallDetails` and the
        `request_or_iterator` object as parameters. The `request_or_iterator`
        parameter should be type checked to determine if this is a singluar request
        for unary RPCs or an iterator for client-streaming or client-server streaming
        RPCs.

        Args:
            method (Callable): A function that proceeds with the invocation by
            executing the next interceptor in chain or invoking the actual RPC on the
            underlying Channel.
            call_details (grpc.ClientCallDetails): Describes an RPC to be invoked
            request_or_iterator (Any): RPC request message(s)

        Returns:
            The return for an interceptor should match the return interface for a
            continuation. This is an object that is both a Call for the RPC and a
            Future.
        """
        return method(call_details, request_or_iterator)  # pragma: no cover

    def intercept_unary_unary(
        self,
        continuation: Callable,
        call_details: grpc.ClientCallDetails,
        request: Any,
    ):
        """Implementation of grpc.UnaryUnaryClientInterceptor.

        This is not part of the grpc_interceptor.ClientInterceptor API, but must have
        a public name. Do not override it, unless you know what you're doing.
        """
        response = self.intercept(continuation, request, call_details)

        return response

    def intercept_unary_stream(
        self,
        continuation: Callable,
        call_details: grpc.ClientCallDetails,
        request: Any,
    ):
        """Implementation of grpc.UnaryStreamClientInterceptor.

        This is not part of the grpc_interceptor.ClientInterceptor API, but must have
        a public name. Do not override it, unless you know what you're doing.
        """
        response = self.intercept(continuation, request, call_details)

        return response

    def intercept_stream_unary(
        self,
        continuation: Callable,
        call_details: grpc.ClientCallDetails,
        request_iterator: Iterator[Any],
    ):
        """Implementation of grpc.StreamUnaryClientInterceptor.

        This is not part of the grpc_interceptor.ClientInterceptor API, but must have
        a public name. Do not override it, unless you know what you're doing.
        """
        response = self.intercept(continuation, request_iterator, call_details)

        return response

    def intercept_stream_stream(
        self,
        continuation: Callable,
        call_details: grpc.ClientCallDetails,
        request_iterator: Iterator[Any],
    ):
        """Implementation of grpc.StreamStreamClientInterceptor.

        This is not part of the grpc_interceptor.ClientInterceptor API, but must have
        a public name. Do not override it, unless you know what you're doing.
        """
        response = self.intercept(continuation, request_iterator, call_details)

        return response
