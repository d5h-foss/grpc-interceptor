"""Base class for client-side interceptors."""

import abc
from dataclasses import dataclass, field
from typing import Callable, Iterator, List, Optional, Tuple

from google.protobuf.message import Message
import grpc


@dataclass
class ClientCallDetails(grpc.ClientCallDetails):
    """Describes an RPC to be invoked.

    This is an EXPERIMENTAL API.

    Attributes:
    method: The method name of the RPC.
    timeout: An optional duration of time in seconds to allow for the RPC.
    metadata: Optional :term:`metadata` to be transmitted to
        the service-side of the RPC.
    credentials: An optional CallCredentials for the RPC.
    wait_for_ready: This is an EXPERIMENTAL argument. An optional
            flag to enable :term:`wait_for_ready` mechanism.
    compression: An element of grpc.compression, e.g.
        grpc.compression.Gzip. This is an EXPERIMENTAL option.
    """

    method: str
    timeout: Optional[int] = field(default=None)
    metadata: List[Tuple[str, str]] = field(default_factory=list)
    credentials: Optional[grpc.CallCredentials] = field(default=None)
    wait_for_ready: Optional[bool] = field(default=None)
    compression: Optional[grpc.Compression] = field(default=None)


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
        call_details: ClientCallDetails,
        request_iterator: Iterator[Message],
        request_streaming: bool,
        response_streaming: bool,
    ) -> Tuple[ClientCallDetails, Iterator[Message], Optional[Callable]]:
        """Override this method to implement a custom interceptor.

        This method is called for all unary and streaming RPCs with the
        appropriate boolean parameters set. The returned
        ClientCallDetails and request message(s) will be passed to
        either the next interceptor or RPC implementation. An optional
        callback function can be returned to perform postprocessing on RPC
        responses.

        Args:
            call_details (ClientCallDetails): Describes an RPC to be invoked
            request_iterator (Iterator[Message]): RPC request messages
            request_streaming (bool): True if RPC is client or bi-directional streaming
            response_streaming (bool): True if PRC is server or bi-directional streaming

        Returns:
            This should return a tuple of ClientCallDetails, RPC request
            message iterator, and a postprocessing callback function or None.
        """
        return call_details, request_iterator, None  # pragma: no cover

    def intercept_unary_unary(
        self, continuation: Callable, call_details: ClientCallDetails, request: Message,
    ):
        """Implementation of grpc.UnaryUnaryClientInterceptor.

        This is not part of the grpc_interceptor.ClientInterceptor API, but must have
        a public name. Do not override it, unless you know what you're doing.
        """
        new_details, new_request_iterator, postprocess = self.intercept(
            call_details=call_details,
            request_iterator=iter((request,)),
            request_streaming=False,
            response_streaming=False,
        )
        response = continuation(new_details, next(new_request_iterator))

        if postprocess:
            return postprocess(response)

        return response

    def intercept_unary_stream(
        self, continuation: Callable, call_details: ClientCallDetails, request: Message,
    ):
        """Implementation of grpc.UnaryStreamClientInterceptor.

        This is not part of the grpc_interceptor.ClientInterceptor API, but must have
        a public name. Do not override it, unless you know what you're doing.
        """
        new_details, new_request_iterator, postprocess = self.intercept(
            call_details=call_details,
            request_iterator=iter((request,)),
            request_streaming=False,
            response_streaming=True,
        )
        response_iterator = continuation(new_details, next(new_request_iterator))

        if postprocess:
            return postprocess(response_iterator)

        return response_iterator

    def intercept_stream_unary(
        self,
        continuation: Callable,
        call_details: ClientCallDetails,
        request_iterator: Iterator[Message],
    ):
        """Implementation of grpc.StreamUnaryClientInterceptor.

        This is not part of the grpc_interceptor.ClientInterceptor API, but must have
        a public name. Do not override it, unless you know what you're doing.
        """
        new_details, new_request_iterator, postprocess = self.intercept(
            call_details=call_details,
            request_iterator=iter((request_iterator,)),
            request_streaming=True,
            response_streaming=False,
        )
        response = continuation(new_details, new_request_iterator)

        if postprocess:
            return postprocess(response)

        return response

    def intercept_stream_stream(
        self,
        continuation: Callable,
        call_details: ClientCallDetails,
        request_iterator: Iterator[Message],
    ):
        """Implementation of grpc.StreamStreamClientInterceptor.

        This is not part of the grpc_interceptor.ClientInterceptor API, but must have
        a public name. Do not override it, unless you know what you're doing.
        """
        new_details, new_request_iterator, postprocess = self.intercept(
            call_details=call_details,
            request_iterator=iter((request_iterator,)),
            request_streaming=True,
            response_streaming=True,
        )
        response_iterator = continuation(new_details, new_request_iterator)

        if postprocess:
            return postprocess(response_iterator)

        return response_iterator
