"""Test cases for the grpc-interceptor base ClientInterceptor."""

from collections import defaultdict
import itertools
from typing import List, Tuple

import grpc
import pytest

from grpc_interceptor import ClientInterceptor
from grpc_interceptor.testing import dummy_client, DummyRequest, raises


class MetadataInterceptor(ClientInterceptor):
    """A test interceptor that injects invocation metadata."""

    def __init__(self, metadata: List[Tuple[str, str]]):
        self._metadata = metadata

    def intercept(self, method, request_or_iterator, call_details):
        """Add invocation metadata to request."""
        new_details = call_details._replace(metadata=self._metadata)
        return method(new_details, request_or_iterator)


class CodeCountInterceptor(ClientInterceptor):
    """Test interceptor that counts status codes returned by the server."""

    def __init__(self):
        self.counts = defaultdict(int)

    def intercept(self, method, request_or_iterator, call_details):
        """Call continuation and count status codes."""
        future = method(call_details, request_or_iterator)
        self.counts[future.code()] += 1
        return future


class RetryInterceptor(ClientInterceptor):
    """Test interceptor that retries failed RPCs."""

    def __init__(self, retries):
        self._retries = retries

    def intercept(self, method, request_or_iterator, call_details):
        """Call the continuation and retry up to retries times if it fails."""
        tries_remaining = 1 + self._retries
        while 0 < tries_remaining:
            future = method(call_details, request_or_iterator)
            try:
                future.result()
                return future
            except Exception:
                tries_remaining -= 1

        return future


class CrashingService:
    """Special case function that raises a given number of times before succeeding."""

    DEFAULT_EXCEPTION = ValueError("oops")

    def __init__(self, num_crashes, success_value="OK", exception=DEFAULT_EXCEPTION):
        self._num_crashes = num_crashes
        self._success_value = success_value
        self._exception = exception

    def __call__(self, *args, **kwargs):
        """Raise the first num_crashes times called, then return success_value."""
        if 0 < self._num_crashes:
            self._num_crashes -= 1
            raise self._exception

        return self._success_value


class CachingInterceptor(ClientInterceptor):
    """A test interceptor that caches responses based on input string."""

    def __init__(self):
        self._cache = {}

    def intercept(self, method, request_or_iterator, call_details):
        """Cache responses based on input string."""
        if hasattr(request_or_iterator, "__iter__"):
            request_or_iterator, copy_iterator = itertools.tee(request_or_iterator)
            cache_key = tuple(r.input for r in copy_iterator)
        else:
            cache_key = request_or_iterator.input

        if cache_key not in self._cache:
            self._cache[cache_key] = method(call_details, request_or_iterator)

        return self._cache[cache_key]


@pytest.fixture
def metadata_string():
    """Expected joined metadata string."""
    return "this_key:this_value"


@pytest.fixture
def metadata_client():
    """Client with metadata interceptor."""
    intr = MetadataInterceptor([("this_key", "this_value")])
    interceptors = [intr]

    special_cases = {
        "metadata": lambda _, c: ",".join(
            f"{key}:{value}" for key, value in c.invocation_metadata()
        )
    }
    with dummy_client(
        special_cases=special_cases, client_interceptors=interceptors
    ) as client:
        yield client


def test_metadata_unary(metadata_client, metadata_string):
    """Invocation metadata should be added to the servicer context."""
    unary_output = metadata_client.Execute(DummyRequest(input="metadata")).output
    assert metadata_string in unary_output


def test_metadata_server_stream(metadata_client, metadata_string):
    """Invocation metadata should be added to the servicer context."""
    server_stream_output = [
        r.output
        for r in metadata_client.ExecuteServerStream(DummyRequest(input="metadata"))
    ]
    assert metadata_string in "".join(server_stream_output)


def test_metadata_client_stream(metadata_client, metadata_string):
    """Invocation metadata should be added to the servicer context."""
    client_stream_input = iter((DummyRequest(input="metadata"),))
    client_stream_output = metadata_client.ExecuteClientStream(
        client_stream_input
    ).output
    assert metadata_string in client_stream_output


def test_metadata_client_server_stream(metadata_client, metadata_string):
    """Invocation metadata should be added to the servicer context."""
    stream_stream_input = iter((DummyRequest(input="metadata"),))
    result = metadata_client.ExecuteClientServerStream(stream_stream_input)
    stream_stream_output = [r.output for r in result]
    assert metadata_string in "".join(stream_stream_output)


def test_code_counting():
    """Access to code on call details works correctly."""
    interceptor = CodeCountInterceptor()
    special_cases = {"error": raises(ValueError("oops"))}
    with dummy_client(
        special_cases=special_cases, client_interceptors=[interceptor]
    ) as client:
        assert interceptor.counts == {}
        client.Execute(DummyRequest(input="foo"))
        assert interceptor.counts == {grpc.StatusCode.OK: 1}
        with pytest.raises(grpc.RpcError):
            client.Execute(DummyRequest(input="error"))
        assert interceptor.counts == {grpc.StatusCode.OK: 1, grpc.StatusCode.UNKNOWN: 1}


def test_basic_retry():
    """Calling the continuation multiple times should work."""
    interceptor = RetryInterceptor(retries=1)
    special_cases = {"error_once": CrashingService(num_crashes=1)}
    with dummy_client(
        special_cases=special_cases, client_interceptors=[interceptor]
    ) as client:
        assert client.Execute(DummyRequest(input="error_once")).output == "OK"


def test_failed_retry():
    """The interceptor can return failed futures."""
    interceptor = RetryInterceptor(retries=1)
    special_cases = {"error_twice": CrashingService(num_crashes=2)}
    with dummy_client(
        special_cases=special_cases, client_interceptors=[interceptor]
    ) as client:
        with pytest.raises(grpc.RpcError):
            client.Execute(DummyRequest(input="error_twice"))


def test_chaining():
    """Chaining interceptors should work."""
    retry_interceptor = RetryInterceptor(retries=1)
    code_count_interceptor = CodeCountInterceptor()
    interceptors = [retry_interceptor, code_count_interceptor]
    special_cases = {"error_once": CrashingService(num_crashes=1)}
    with dummy_client(
        special_cases=special_cases, client_interceptors=interceptors
    ) as client:
        assert code_count_interceptor.counts == {}
        assert client.Execute(DummyRequest(input="error_once")).output == "OK"
        assert code_count_interceptor.counts == {
            grpc.StatusCode.OK: 1,
            grpc.StatusCode.UNKNOWN: 1,
        }


def test_caching():
    """Caching calls (not calling the continuation) should work."""
    caching_interceptor = CachingInterceptor()
    # Use this to test how many times the continuation is called.
    code_count_interceptor = CodeCountInterceptor()
    interceptors = [caching_interceptor, code_count_interceptor]
    with dummy_client(special_cases={}, client_interceptors=interceptors) as client:
        assert code_count_interceptor.counts == {}
        assert client.Execute(DummyRequest(input="hello")).output == "hello"
        assert code_count_interceptor.counts == {grpc.StatusCode.OK: 1}
        assert client.Execute(DummyRequest(input="hello")).output == "hello"
        assert code_count_interceptor.counts == {grpc.StatusCode.OK: 1}
        assert client.Execute(DummyRequest(input="goodbye")).output == "goodbye"
        assert code_count_interceptor.counts == {grpc.StatusCode.OK: 2}
        # Try streaming requests
        inputs = ["foo", "bar"]
        input_iter = (DummyRequest(input=input) for input in inputs)
        assert client.ExecuteClientStream(input_iter).output == "foobar"
        assert code_count_interceptor.counts == {grpc.StatusCode.OK: 3}
        input_iter = (DummyRequest(input=input) for input in inputs)
        assert client.ExecuteClientStream(input_iter).output == "foobar"
        assert code_count_interceptor.counts == {grpc.StatusCode.OK: 3}
