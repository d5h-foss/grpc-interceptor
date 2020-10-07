"""Test cases for streaming RPCs."""

import grpc
import pytest

from grpc_interceptor import ServerInterceptor
from grpc_interceptor.testing import dummy_client, DummyRequest


class StreamingInterceptor(ServerInterceptor):
    """A test interceptor that streams."""

    def intercept(self, method, request, context, method_name):
        """Doesn't do anything; just make sure we handle streaming RPCs."""
        return method(request, context)


@pytest.fixture
def interceptors():
    """The interceptor chain for this test suite."""
    intr = StreamingInterceptor()
    return [intr]


def test_client_streaming(interceptors):
    """Client streaming should work."""
    special_cases = {"error": lambda r, c: 1 / 0}
    with dummy_client(special_cases=special_cases, interceptors=interceptors) as client:
        inputs = ["foo", "bar"]
        input_iter = (DummyRequest(input=input) for input in inputs)
        assert client.ExecuteClientStream(input_iter).output == "foobar"

        inputs = ["foo", "error"]
        input_iter = (DummyRequest(input=input) for input in inputs)
        with pytest.raises(grpc.RpcError):
            client.ExecuteClientStream(input_iter)


def test_server_streaming(interceptors):
    """Server streaming should work."""
    with dummy_client(special_cases={}, interceptors=interceptors) as client:
        output = [
            r.output for r in client.ExecuteServerStream(DummyRequest(input="foo"))
        ]
        assert output == ["f", "o", "o"]


def test_client_server_streaming(interceptors):
    """Bidirectional streaming should work."""
    with dummy_client(special_cases={}, interceptors=interceptors) as client:
        inputs = ["foo", "bar"]
        input_iter = (DummyRequest(input=input) for input in inputs)
        response = client.ExecuteClientServerStream(input_iter)
        assert [r.output for r in response] == inputs
