"""Defines a service and client for testing interceptors."""

from concurrent import futures
from contextlib import contextmanager
import os
from tempfile import gettempdir
from typing import Callable, Dict, Iterable, List, Optional
from uuid import uuid4

import grpc

from grpc_interceptor.client import ClientInterceptor
from grpc_interceptor.server import ServerInterceptor
from grpc_interceptor.testing.protos import dummy_pb2_grpc
from grpc_interceptor.testing.protos.dummy_pb2 import DummyRequest, DummyResponse

SpecialCaseFunction = Callable[[str, grpc.ServicerContext], str]


class DummyService(dummy_pb2_grpc.DummyServiceServicer):
    """A gRPC service used for testing.

    Args:
        special_cases: A dictionary where the keys are strings, and the values are
            functions that take and return strings. The functions can also raise
            exceptions. When the Execute method is given a string in the dict, it
            will call the function with that string instead, and return the result.
            This allows testing special cases, like raising exceptions.
    """

    def __init__(
        self, special_cases: Dict[str, SpecialCaseFunction],
    ):
        self._special_cases = special_cases

    def Execute(
        self, request: DummyRequest, context: grpc.ServicerContext
    ) -> DummyResponse:
        """Echo the input, or take on of the special cases actions."""
        return DummyResponse(output=self._get_output(request, context))

    def ExecuteClientStream(
        self, request_iter: Iterable[DummyRequest], context: grpc.ServicerContext
    ) -> DummyResponse:
        """Iterate over the input and concatenates the strings into the output."""
        output = "".join(self._get_output(request, context) for request in request_iter)
        return DummyResponse(output=output)

    def ExecuteServerStream(
        self, request: DummyRequest, context: grpc.ServicerContext
    ) -> Iterable[DummyResponse]:
        """Stream one character at a time from the input."""
        for c in self._get_output(request, context):
            yield DummyResponse(output=c)

    def ExecuteClientServerStream(
        self, request_iter: Iterable[DummyRequest], context: grpc.ServicerContext
    ) -> Iterable[DummyResponse]:
        """Stream input to output."""
        for request in request_iter:
            yield DummyResponse(output=self._get_output(request, context))

    def _get_output(self, request: DummyRequest, context: grpc.ServicerContext) -> str:
        input = request.input

        output = input
        if input in self._special_cases:
            output = self._special_cases[input](input, context)

        return output


@contextmanager
def dummy_client(
    special_cases: Dict[str, SpecialCaseFunction],
    interceptors: Optional[List[ServerInterceptor]] = None,
    client_interceptors: Optional[List[ClientInterceptor]] = None,
):
    """A context manager that returns a gRPC client connected to a DummyService."""
    with dummy_channel(special_cases, interceptors, client_interceptors) as channel:
        client = dummy_pb2_grpc.DummyServiceStub(channel)
        yield client


@contextmanager
def dummy_channel(
    special_cases: Dict[str, SpecialCaseFunction],
    interceptors: Optional[List[ServerInterceptor]] = None,
    client_interceptors: Optional[List[ClientInterceptor]] = None,
):
    """A context manager that returns a gRPC channel connected to a DummyService."""
    if not interceptors:
        interceptors = []

    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=1), interceptors=interceptors
    )
    dummy_service = DummyService(special_cases)
    dummy_pb2_grpc.add_DummyServiceServicer_to_server(dummy_service, server)

    if os.name == "nt":  # pragma: no cover
        # We use Unix domain sockets when they're supported, to avoid port conflicts.
        # However, on Windows, just pick a port.
        channel_descriptor = "localhost:50051"
    else:
        channel_descriptor = f"unix://{gettempdir()}/{uuid4()}.sock"

    server.add_insecure_port(channel_descriptor)
    server.start()

    channel = grpc.insecure_channel(channel_descriptor)
    if client_interceptors:
        channel = grpc.intercept_channel(channel, *client_interceptors)

    try:
        yield channel
    finally:
        server.stop(None)
