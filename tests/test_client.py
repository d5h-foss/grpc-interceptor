"""Test cases for the grpc-interceptor base ClientInterceptor."""

from typing import List, Tuple

import pytest

from grpc_interceptor import ClientCallDetails, ClientInterceptor
from grpc_interceptor.testing import dummy_client, DummyRequest


class MetadataInterceptor(ClientInterceptor):
    """A test interceptor that injects invocation metadata."""

    def __init__(self, metadata: List[Tuple[str, str]]):
        self._metadata = metadata

    def intercept(
        self, call_details, request_iterator, request_streaming, response_streaming
    ):
        """Add invocation metadata to request."""
        new_details = ClientCallDetails(
            call_details.method,
            call_details.timeout,
            self._metadata,
            call_details.credentials,
            call_details.wait_for_ready,
            call_details.compression,
        )

        return new_details, request_iterator, None


class PostprocessInterceptor(ClientInterceptor):
    """A test interceptor that logs results."""

    def __init__(self):
        import logging

        self._log = logging.getLogger(__name__)

    def intercept(
        self, call_details, request_iterator, request_streaming, response_streaming
    ):
        """Log response data."""

        def _unary_logger(outcome):
            self._log.warning(outcome.result().output)
            return outcome

        def _stream_logger(response_iterator):
            collected = ""
            for response in response_iterator:
                collected += response.output
                yield response

            self._log.warning(collected)

        postprocess = _unary_logger
        if response_streaming:
            postprocess = _stream_logger

        return call_details, request_iterator, postprocess


@pytest.fixture
def metadata_string():
    """Expected joined metadata string."""
    return "this_key:this_value"


@pytest.fixture
def metadata_client():
    """Client with metadata interceptor."""
    intr = MetadataInterceptor([("this_key", "this_value")])
    interceptors = [intr]

    context_cases = {
        "metadata": lambda c: ",".join(
            f"{key}:{value}" for key, value in c.invocation_metadata()
        )
    }
    with dummy_client(
        special_cases={}, context_cases=context_cases, client_interceptors=interceptors
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


@pytest.fixture
def logged_string():
    """Expected logged response string."""
    return "logthisthing"


@pytest.fixture
def postprocess_client():
    """Client with postprocess interceptor."""
    intr = PostprocessInterceptor()
    interceptors = [intr]

    with dummy_client(
        special_cases={}, context_cases={}, client_interceptors=interceptors
    ) as client:
        yield client


def test_postprocess_unary(caplog, postprocess_client, logged_string):
    """Response output field should be logged."""
    postprocess_client.Execute(DummyRequest(input=logged_string))
    assert logged_string in caplog.text


def test_postprocess_server_stream(caplog, postprocess_client, logged_string):
    """Response output fields should be concatenated and logged."""
    for _ in postprocess_client.ExecuteServerStream(DummyRequest(input=logged_string)):
        pass

    assert logged_string in caplog.text


def test_postprocess_client_stream(caplog, postprocess_client, logged_string):
    """Response output field should be logged."""
    client_stream_input = iter((DummyRequest(input=logged_string),))
    postprocess_client.ExecuteClientStream(client_stream_input)
    assert logged_string in caplog.text


def test_postprocess_client_server_stream(caplog, postprocess_client, logged_string):
    """Response output fields should be concatenated and logged."""
    stream_stream_input = iter((DummyRequest(input=logged_string),))
    for _ in postprocess_client.ExecuteClientServerStream(stream_stream_input):
        pass

    assert logged_string in caplog.text
