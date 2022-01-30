"""Test cases for streaming RPCs."""

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
        res = method(request, context)
        if hasattr(res, "__aiter__"):
            async for r in res:
                yield r
        else:
            yield res


@pytest.mark.parametrize("aio", [False, True])
def test_client_streaming(aio):
    """Client streaming should work."""
    intr = AsyncStreamingInterceptor() if aio else StreamingInterceptor()
    interceptors = [intr]
    special_cases = {"error": lambda r, c: 1 / 0}
    with dummy_client(special_cases=special_cases, interceptors=interceptors, aio_server=aio) as client:
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
    with dummy_client(special_cases={}, interceptors=interceptors, aio_server=aio) as client:
        output = [
            r.output for r in client.ExecuteServerStream(DummyRequest(input="foo"))
        ]
        assert output == ["f", "o", "o"]


@pytest.mark.parametrize("aio", [False, True])
def test_client_server_streaming(aio):
    """Bidirectional streaming should work."""
    intr = AsyncStreamingInterceptor() if aio else StreamingInterceptor()
    interceptors = [intr]
    with dummy_client(special_cases={}, interceptors=interceptors, aio_server=aio) as client:
        inputs = ["foo", "bar"]
        input_iter = (DummyRequest(input=input) for input in inputs)
        response = client.ExecuteClientServerStream(input_iter)
        assert [r.output for r in response] == inputs
