"""Defines a service and client for testing interceptors."""

import asyncio
from concurrent import futures
from contextlib import contextmanager
import os
from tempfile import gettempdir
from threading import Event, Thread
from typing import (
    AsyncGenerator,
    AsyncIterable,
    Callable,
    Dict,
    Iterable,
    List,
    Optional,
)
from uuid import uuid4

import grpc

from grpc_interceptor.client import ClientInterceptor
from grpc_interceptor.server import AsyncServerInterceptor, grpc_aio, ServerInterceptor
from grpc_interceptor.testing.protos import dummy_pb2_grpc
from grpc_interceptor.testing.protos.dummy_pb2 import DummyRequest, DummyResponse

SpecialCaseFunction = Callable[[str, grpc.ServicerContext], str]


class _SpecialCaseMixin:
    _special_cases: Dict[str, SpecialCaseFunction]

    def _get_output(self, request: DummyRequest, context: grpc.ServicerContext) -> str:
        input = request.input

        output = input
        if input in self._special_cases:
            output = self._special_cases[input](input, context)

        return output


class DummyService(dummy_pb2_grpc.DummyServiceServicer, _SpecialCaseMixin):
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


class AsyncDummyService(dummy_pb2_grpc.DummyServiceServicer, _SpecialCaseMixin):
    """A gRPC service used for testing, similar to DummyService except async.

    See DummyService for more info.
    """

    def __init__(
        self, special_cases: Dict[str, SpecialCaseFunction],
    ):
        self._special_cases = special_cases

    async def Execute(
        self, request: DummyRequest, context: grpc_aio.ServicerContext
    ) -> DummyResponse:
        """Echo the input, or take on of the special cases actions."""
        return DummyResponse(output=self._get_output(request, context))

    async def ExecuteClientStream(
        self,
        request_iter: AsyncIterable[DummyRequest],
        context: grpc_aio.ServicerContext,
    ) -> DummyResponse:
        """Iterate over the input and concatenates the strings into the output."""
        output = "".join(
            [self._get_output(request, context) async for request in request_iter]
        )
        return DummyResponse(output=output)

    async def ExecuteServerStream(
        self, request: DummyRequest, context: grpc_aio.ServicerContext
    ) -> AsyncGenerator[DummyResponse, None]:
        """Stream one character at a time from the input."""
        for c in self._get_output(request, context):
            yield DummyResponse(output=c)

    async def ExecuteClientServerStream(
        self,
        request_iter: AsyncIterable[DummyRequest],
        context: grpc_aio.ServicerContext,
    ) -> AsyncGenerator[DummyResponse, None]:
        """Stream input to output."""
        async for request in request_iter:
            yield DummyResponse(output=self._get_output(request, context))


@contextmanager
def dummy_client(
    special_cases: Dict[str, SpecialCaseFunction],
    interceptors: Optional[List[ServerInterceptor]] = None,
    client_interceptors: Optional[List[ClientInterceptor]] = None,
    aio_server: bool = False,
):
    """A context manager that returns a gRPC client connected to a DummyService."""
    # Sanity check that the interceptors are async if using an async server,
    # otherwise the tests will just hang.
    for intr in (interceptors or []):
        assert aio_server == isinstance(
            intr, AsyncServerInterceptor
        ), "Set aio_server correctly"
    with dummy_channel(
        special_cases, interceptors, client_interceptors, aio_server
    ) as channel:
        client = dummy_pb2_grpc.DummyServiceStub(channel)
        yield client


@contextmanager
def dummy_channel(
    special_cases: Dict[str, SpecialCaseFunction],
    interceptors: Optional[List[ServerInterceptor]] = None,
    client_interceptors: Optional[List[ClientInterceptor]] = None,
    aio_server: bool = False,
):
    """A context manager that returns a gRPC channel connected to a DummyService."""
    if not interceptors:
        interceptors = []

    if os.name == "nt":  # pragma: no cover
        # We use Unix domain sockets when they're supported, to avoid port conflicts.
        # However, on Windows, just pick a port.
        channel_descriptor = "localhost:50051"
    else:
        channel_descriptor = f"unix://{gettempdir()}/{uuid4()}.sock"

    if aio_server:
        aio_loop = asyncio.new_event_loop()
        aio_thread = _AsyncServerThread(
            aio_loop, AsyncDummyService(special_cases), channel_descriptor, interceptors
        )
        aio_thread.start()
        aio_thread.wait_for_server()
    else:
        dummy_service = DummyService(special_cases)
        server = grpc.server(
            futures.ThreadPoolExecutor(max_workers=1), interceptors=interceptors
        )
        dummy_pb2_grpc.add_DummyServiceServicer_to_server(dummy_service, server)
        server.add_insecure_port(channel_descriptor)
        server.start()

    channel = grpc.insecure_channel(channel_descriptor)
    if client_interceptors:
        channel = grpc.intercept_channel(channel, *client_interceptors)

    try:
        yield channel
    finally:
        if aio_server:
            aio_thread.stop()
            aio_thread.join()
        else:
            server.stop(None)


class _AsyncServerThread(Thread):
    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        service,
        channel_descriptor: str,
        interceptors: List[AsyncServerInterceptor],
    ):
        super().__init__()
        self.__loop = loop
        self.__service = service
        self.__channel_descriptor = channel_descriptor
        self.__interceptors = interceptors
        self.__started = Event()

    def run(self):
        asyncio.set_event_loop(self.__loop)
        self.__loop.run_until_complete(self.__run_server())

    async def __run_server(self):
        self.__server = grpc_aio.server(interceptors=tuple(self.__interceptors))
        dummy_pb2_grpc.add_DummyServiceServicer_to_server(self.__service, self.__server)
        self.__server.add_insecure_port(self.__channel_descriptor)
        await self.__server.start()
        self.__started.set()
        await self.__server.wait_for_termination()

    def wait_for_server(self):
        self.__started.wait()

    def stop(self):
        self.__loop.call_soon_threadsafe(
            lambda: asyncio.ensure_future(self.__shutdown())
        )

    async def __shutdown(self) -> None:
        await self.__server.stop(None)
        self.__loop.stop()
