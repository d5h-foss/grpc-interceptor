"""Test cases for streaming RPCs."""

import sys

import grpc
import pytest

from grpc_interceptor import AsyncServerInterceptor, ServerInterceptor
from grpc_interceptor.testing import dummy_client, DummyRequest


class StreamingInterceptor(ServerInterceptor):
    """A test interceptor that streams."""

    def intercept(self, method, request, context, method_name):
        """Doesn't do anything; just make sure we handle streaming RPCs."""
        return method(request, context)


class AsyncStreamingInterceptor(AsyncServerInterceptor):
    """A test interceptor that streams."""

    async def intercept(self, method, request, context, method_name):
        """Doesn't do anything; just make sure we handle streaming RPCs."""
        response_or_iterator = method(request, context)
        if hasattr(response_or_iterator, "__aiter__"):
            return response_or_iterator
        else:
            return await response_or_iterator


class ServerStreamingLoggingInterceptor(ServerInterceptor):
    """A test interceptor that logs a stream of server responses."""

    def __init__(self):
        self._logs = []

    def intercept(self, method, request, context, method_name):
        """Log each response object and re-yield."""
        for resp in method(request, context):
            self._logs.append(resp.output)
            yield resp


class AsyncServerStreamingLoggingInterceptor(AsyncServerInterceptor):
    """A test interceptor that logs a stream of server responses."""

    def __init__(self):
        self._logs = []

    async def intercept(self, method, request, context, method_name):
        """Log each response object and re-yield."""
        async for resp in method(request, context):
            self._logs.append(resp.output)
            yield resp


class ServerOmniLoggingInterceptor(ServerInterceptor):
    """A test interceptor that logs both unary and streaming server responses."""

    def __init__(self):
        self._logs = []

    def _log_and_yield(self, iterator):
        logs = []
        for resp in iterator:
            logs.append(resp.output)
            yield resp
        self._logs.append(logs)

    def intercept(self, method, request, context, method_name):
        """Log each response object and re-yield."""
        response_or_iterator = method(request, context)
        if hasattr(response_or_iterator, "__iter__"):
            return self._log_and_yield(response_or_iterator)
        else:
            self._logs.append(response_or_iterator.output)
            return response_or_iterator


class AsyncServerOmniLoggingInterceptor(AsyncServerInterceptor):
    """A test interceptor that logs both unary and streaming server responses."""

    def __init__(self):
        self._logs = []

    async def _log_and_yield(self, iterator):
        logs = []
        async for resp in iterator:
            logs.append(resp.output)
            yield resp
        self._logs.append(logs)

    async def intercept(self, method, request, context, method_name):
        """Log each response object and re-yield."""
        response_or_iterator = method(request, context)
        if hasattr(response_or_iterator, "__aiter__"):
            return self._log_and_yield(response_or_iterator)
        else:
            response_or_iterator = await response_or_iterator
            self._logs.append(response_or_iterator.output)
            return response_or_iterator


class ClientStreamingLoggingInterceptor(ServerInterceptor):
    """A test interceptor that logs a stream of server requests."""

    def __init__(self):
        self._logs = []

    def _log_and_yield(self, request):
        for r in request:
            self._logs.append(r.input)
            yield r

    def intercept(self, method, request, context, method_name):
        """Log each request object and pass through."""
        req = self._log_and_yield(request)
        return method(req, context)


class AsyncClientStreamingLoggingInterceptor(AsyncServerInterceptor):
    """A test interceptor that logs a stream of server requests."""

    def __init__(self):
        self._logs = []

    async def _log_and_yield(self, request):
        async for r in request:
            self._logs.append(r.input)
            yield r

    async def intercept(self, method, request, context, method_name):
        """Log each request object and pass through."""
        req = self._log_and_yield(request)
        return await method(req, context)


@pytest.mark.parametrize("aio", [False, True])
@pytest.mark.parametrize("aio_rw", [False, True])
def test_client_streaming(aio, aio_rw):
    """Client streaming should work."""
    intr = AsyncStreamingInterceptor() if aio else StreamingInterceptor()
    interceptors = [intr]
    special_cases = {"error": lambda r, c: 1 / 0}
    with dummy_client(
        special_cases=special_cases,
        interceptors=interceptors,
        aio_server=aio,
        aio_read_write=aio_rw,
    ) as client:
        inputs = ["foo", "bar"]
        input_iter = (DummyRequest(input=input) for input in inputs)
        assert client.ExecuteClientStream(input_iter).output == "foobar"

        inputs = ["foo", "error"]
        input_iter = (DummyRequest(input=input) for input in inputs)
        with pytest.raises(grpc.RpcError):
            client.ExecuteClientStream(input_iter)


@pytest.mark.parametrize("aio", [False, True])
def test_server_streaming(aio):
    """Server streaming should work."""
    intr = AsyncStreamingInterceptor() if aio else StreamingInterceptor()
    interceptors = [intr]
    with dummy_client(
        special_cases={}, interceptors=interceptors, aio_server=aio
    ) as client:
        output = [
            r.output for r in client.ExecuteServerStream(DummyRequest(input="foo"))
        ]
        assert output == ["f", "o", "o"]


@pytest.mark.parametrize("aio", [False, True])
def test_client_server_streaming(aio):
    """Bidirectional streaming should work."""
    intr = AsyncStreamingInterceptor() if aio else StreamingInterceptor()
    interceptors = [intr]
    with dummy_client(
        special_cases={}, interceptors=interceptors, aio_server=aio
    ) as client:
        inputs = ["foo", "bar"]
        input_iter = (DummyRequest(input=input) for input in inputs)
        response = client.ExecuteClientServerStream(input_iter)
        assert [r.output for r in response] == inputs


@pytest.mark.parametrize("aio", [False, True])
def test_interceptor_iterates_server_streaming(aio):
    """The iterator should be able to iterate over streamed server responses."""
    intr = (
        AsyncServerStreamingLoggingInterceptor()
        if aio
        else ServerStreamingLoggingInterceptor()
    )
    interceptors = [intr]
    with dummy_client(
        special_cases={}, interceptors=interceptors, aio_server=aio
    ) as client:
        output = [
            r.output for r in client.ExecuteServerStream(DummyRequest(input="foo"))
        ]
        assert output == ["f", "o", "o"]
        assert intr._logs == ["f", "o", "o"]


@pytest.mark.parametrize("aio", [False, True])
def test_interceptor_handles_both_unary_and_streaming(aio):
    """The iterator should be able to iterate over streamed server responses."""
    intr = (
        AsyncServerOmniLoggingInterceptor() if aio else ServerOmniLoggingInterceptor()
    )
    interceptors = [intr]
    with dummy_client(
        special_cases={}, interceptors=interceptors, aio_server=aio
    ) as client:
        output = [
            r.output for r in client.ExecuteServerStream(DummyRequest(input="foo"))
        ]
        assert output == ["f", "o", "o"]
        assert intr._logs == [["f", "o", "o"]]

        r = client.Execute(DummyRequest(input="bar"))
        assert r.output == "bar"
        assert intr._logs == [["f", "o", "o"], "bar"]


@pytest.mark.parametrize("aio", [False, True])
def test_client_log_streaming(aio):
    """Client streaming should work when re-yielding."""
    intr = (
        AsyncClientStreamingLoggingInterceptor()
        if aio
        else ClientStreamingLoggingInterceptor()
    )
    interceptors = [intr]
    with dummy_client(
        special_cases={}, interceptors=interceptors, aio_server=aio
    ) as client:
        inputs = ["foo", "bar"]
        input_iter = (DummyRequest(input=input) for input in inputs)
        assert client.ExecuteClientStream(input_iter).output == "foobar"
        assert intr._logs == inputs


@pytest.mark.skipif(sys.version_info < (3, 7), reason="requires Python 3.7")
@pytest.mark.asyncio
async def test_client_streaming_write_method():
    """Client streaming should work when using write()."""
    intr = AsyncClientStreamingLoggingInterceptor()
    interceptors = [intr]
    with dummy_client(
        special_cases={}, interceptors=interceptors, aio_server=True, aio_client=True
    ) as client:
        call = client.ExecuteClientStream()
        await call.write(DummyRequest(input="foo"))
        await call.write(DummyRequest(input="bar"))
        await call.done_writing()
        response = await call
        assert response.output == "foobar"
        assert intr._logs == ["foo", "bar"]
