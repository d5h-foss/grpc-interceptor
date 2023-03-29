"""Defines a service and client for testing interceptors."""

import asyncio
from concurrent import futures
from contextlib import contextmanager
import errno
from itertools import chain, repeat, starmap
import os
from random import randrange
import socket
from threading import Event, Thread
from typing import (
    Any,
    AsyncGenerator,
    AsyncIterable,
    Callable,
    Dict,
    Iterable,
    List,
    Optional,
)

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


class AsyncReadWriteDummyService(
    dummy_pb2_grpc.DummyServiceServicer, _SpecialCaseMixin
):
    """Similar to AsyncDummyService except uses the read / write API.

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
        self, unused_request: Any, context: grpc_aio.ServicerContext,
    ) -> DummyResponse:
        """Iterate over the input and concatenates the strings into the output."""
        output = []
        while True:
            request = await context.read()
            if request == grpc_aio.EOF:
                break
            output.append(self._get_output(request, context))

        return DummyResponse(output="".join(output))

    async def ExecuteServerStream(
        self, request: DummyRequest, context: grpc_aio.ServicerContext
    ) -> None:
        """Stream one character at a time from the input."""
        for c in self._get_output(request, context):
            await context.write(DummyResponse(output=c))

    async def ExecuteClientServerStream(
        self,
        request_iter: AsyncIterable[DummyRequest],
        context: grpc_aio.ServicerContext,
    ) -> None:
        """Stream input to output."""
        while True:
            request = await context.read()
            if request == grpc_aio.EOF:
                break
            await context.write(
                DummyResponse(output=self._get_output(request, context))
            )


@contextmanager
def dummy_client(
    special_cases: Dict[str, SpecialCaseFunction],
    interceptors: Optional[List[ServerInterceptor]] = None,
    client_interceptors: Optional[List[ClientInterceptor]] = None,
    aio_server: bool = False,
    aio_client: bool = False,
    aio_read_write: bool = False,
):
    """A context manager that returns a gRPC client connected to a DummyService."""
    # Sanity check that the interceptors are async if using an async server,
    # otherwise the tests will just hang.
    for intr in interceptors or []:
        if aio_server != isinstance(intr, AsyncServerInterceptor):
            raise TypeError("Set aio_server correctly")
    with dummy_channel(
        special_cases,
        interceptors,
        client_interceptors,
        aio_server=aio_server,
        aio_client=aio_client,
        aio_read_write=aio_read_write,
    ) as channel:
        client = dummy_pb2_grpc.DummyServiceStub(channel)
        yield client


def _get_available_port() -> Optional[int]:
    """Check port 50051 and random others; return the first available port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sckt:
        for port in chain([50051], starmap(randrange, repeat((32768, 60999), 10))):
            if sckt.connect_ex(("localhost", port)) != 0:
                return port
    return None


@contextmanager
def dummy_channel(
    special_cases: Dict[str, SpecialCaseFunction],
    interceptors: Optional[List[ServerInterceptor]] = None,
    client_interceptors: Optional[List[ClientInterceptor]] = None,
    aio_server: bool = False,
    aio_client: bool = False,
    aio_read_write: bool = False,
):
    """A context manager that returns a gRPC channel connected to a DummyService."""
    if not interceptors:
        interceptors = []

    port = _get_available_port()
    if port is None:
        raise OSError(errno.EBADF, os.strerror(errno.EBADF))
    channel_descriptor = "localhost:" + str(port)

    if aio_client:
        channel = grpc_aio.insecure_channel(channel_descriptor)
        # Client interceptors might work, but I haven't tested them yet.
        if client_interceptors:
            raise TypeError("Client interceptors not supported with async channel")
    else:
        channel = grpc.insecure_channel(channel_descriptor)
        if client_interceptors:
            channel = grpc.intercept_channel(channel, *client_interceptors)

    if aio_server:
        service = (
            AsyncReadWriteDummyService(special_cases)
            if aio_read_write
            else AsyncDummyService(special_cases)
        )
        aio_loop = asyncio.new_event_loop()
        aio_thread = _AsyncServerThread(
            aio_loop,
            service,
            channel if aio_client else None,
            channel_descriptor,
            interceptors,
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

    try:
        yield channel
    finally:
        if not aio_client:
            # async channel is closed by _AsyncServerThread
            channel.close()
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
        optional_async_client_channel,
        channel_descriptor: str,
        interceptors: List[AsyncServerInterceptor],
    ):
        super().__init__()
        self.__loop = loop
        self.__service = service
        self.__optional_async_client_channel = optional_async_client_channel
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
        if self.__optional_async_client_channel:
            await self.__optional_async_client_channel.close()

    def wait_for_server(self):
        self.__started.wait()

    def stop(self):
        self.__loop.call_soon_threadsafe(
            lambda: asyncio.ensure_future(self.__shutdown())
        )

    async def __shutdown(self) -> None:
        await self.__server.stop(None)
        self.__loop.stop()
