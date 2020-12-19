"""Test cases for the grpc-interceptor base ClientInterceptor."""

from typing import List, Tuple

import pytest

from grpc_interceptor import ClientCallDetails, ClientInterceptor
from grpc_interceptor.testing import dummy_client, DummyRequest


class MetadataInterceptor(ClientInterceptor):
    """A test interceptor that injects invocation metadata."""

    def __init__(self, metadata: List[Tuple[str, str]]):
        self._metadata = metadata

    def intercept(self, method, request_or_iterator, call_details):
        """Add invocation metadata to request."""
        new_details = ClientCallDetails(
            call_details.method,
            call_details.timeout,
            self._metadata,
            call_details.credentials,
            call_details.wait_for_ready,
            call_details.compression,
        )

        return method(new_details, request_or_iterator)


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
    assert (
        "".join(server_stream_output[0 : len(metadata_string)])  # noqa E203
        == metadata_string
    )


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
    assert metadata_string in stream_stream_output[0]
