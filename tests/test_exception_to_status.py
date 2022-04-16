"""Test cases for ExceptionToStatusInterceptor."""
import re

import grpc
import pytest

from grpc_interceptor import exceptions as gx
from grpc_interceptor.exception_to_status import ExceptionToStatusInterceptor
from grpc_interceptor.testing import dummy_client, DummyRequest, raises


class NonGrpcException(Exception):
    """An exception that does not derive from GrpcException."""

    TEST_STATUS_CODE = grpc.StatusCode.DATA_LOSS
    TEST_DETAILS = "Here's some custom details"


class ExtendedExceptionToStatusInterceptor(ExceptionToStatusInterceptor):
    """A test case for extending ExceptionToStatusInterceptor."""

    def __init__(self):
        self.caught_custom_exception = False

    def handle_exception(self, ex, request_or_iterator, context, method_name):
        """Handles NonGrpcException in a special way."""
        if isinstance(ex, NonGrpcException):
            self.caught_custom_exception = True
            context.abort(
                NonGrpcException.TEST_STATUS_CODE, NonGrpcException.TEST_DETAILS
            )
        else:
            super().handle_exception(ex, request_or_iterator, context, method_name)


@pytest.fixture
def interceptors():
    """The interceptor chain for the majority of this test suite."""
    return [ExceptionToStatusInterceptor()]


def test_repr():
    """repr() should display the class name, status code, and details."""
    assert (
        repr(gx.GrpcException(details="oops"))
        == "GrpcException(status_code=UNKNOWN, details='oops')"
    )
    assert (
        repr(gx.GrpcException(status_code=grpc.StatusCode.NOT_FOUND, details="oops"))
        == "GrpcException(status_code=NOT_FOUND, details='oops')"
    )
    assert (
        repr(gx.NotFound(details="?")) == "NotFound(status_code=NOT_FOUND, details='?')"
    )


def test_status_string():
    """status_string should be the string version of the status code."""
    assert gx.GrpcException().status_string == "UNKNOWN"
    assert (
        gx.GrpcException(status_code=grpc.StatusCode.NOT_FOUND).status_string
        == "NOT_FOUND"
    )
    assert gx.NotFound().status_string == "NOT_FOUND"


def test_no_exception(interceptors):
    """An RPC with no exceptions should work as if the interceptor wasn't there."""
    with dummy_client(special_cases={}, interceptors=interceptors) as client:
        assert client.Execute(DummyRequest(input="foo")).output == "foo"


def test_custom_details(interceptors):
    """We can set custom details."""
    special_cases = {"error": raises(gx.NotFound(details="custom"))}
    with dummy_client(special_cases=special_cases, interceptors=interceptors) as client:
        assert (
            client.Execute(DummyRequest(input="foo")).output == "foo"
        )  # Test a happy path too
        with pytest.raises(grpc.RpcError) as e:
            client.Execute(DummyRequest(input="error"))
        assert e.value.code() == grpc.StatusCode.NOT_FOUND
        assert e.value.details() == "custom"


def test_non_grpc_exception(interceptors):
    """Exceptions other than GrpcExceptions are ignored."""
    special_cases = {"error": raises(ValueError("oops"))}
    with dummy_client(special_cases=special_cases, interceptors=interceptors) as client:
        with pytest.raises(grpc.RpcError) as e:
            client.Execute(DummyRequest(input="error"))
        assert e.value.code() == grpc.StatusCode.UNKNOWN


def test_non_grpc_exception_with_override():
    """We can set a custom status code when non-GrpcExceptions are raised."""
    interceptors = [
        ExceptionToStatusInterceptor(
            status_on_unknown_exception=grpc.StatusCode.INTERNAL
        )
    ]
    special_cases = {"error": raises(ValueError("oops"))}
    with dummy_client(special_cases=special_cases, interceptors=interceptors) as client:
        with pytest.raises(grpc.RpcError) as e:
            client.Execute(DummyRequest(input="error"))
        assert e.value.code() == grpc.StatusCode.INTERNAL
        assert re.fullmatch(r"ValueError\('oops',?\)", e.value.details())


def test_override_with_ok():
    """We cannot set the default status code to OK."""
    with pytest.raises(ValueError):
        ExceptionToStatusInterceptor(status_on_unknown_exception=grpc.StatusCode.OK)


def test_all_exceptions(interceptors):
    """Every gRPC status code is represented, and they each are unique.

    Make sure we aren't missing any status codes, and that we didn't copy paste the
    same status code or details into two different classes.
    """
    all_status_codes = {sc for sc in grpc.StatusCode if sc != grpc.StatusCode.OK}
    seen_codes = set()
    seen_details = set()

    for sc in all_status_codes:
        ex = getattr(gx, _snake_to_camel(sc.name))
        assert ex
        special_cases = {"error": raises(ex())}
        with dummy_client(
            special_cases=special_cases, interceptors=interceptors
        ) as client:
            with pytest.raises(grpc.RpcError) as e:
                client.Execute(DummyRequest(input="error"))
            assert e.value.code() == sc
            assert e.value.details() == ex.details
            seen_codes.add(sc)
            seen_details.add(ex.details)

    assert seen_codes == all_status_codes
    assert len(seen_details) == len(all_status_codes)


def test_exception_in_streaming_response(interceptors):
    """Exceptions are raised correctly from streaming responses."""
    with dummy_client(
        special_cases={"error": raises(gx.NotFound("not found!"))},
        interceptors=interceptors,
    ) as client:
        with pytest.raises(grpc.RpcError) as e:
            list(client.ExecuteServerStream(DummyRequest(input="error")))
        assert e.value.code() == grpc.StatusCode.NOT_FOUND
        assert e.value.details() == "not found!"


def _snake_to_camel(s: str) -> str:
    return "".join([p.title() for p in s.split("_")])


def test_not_ok():
    """We cannot create a GrpcException with an OK status code."""
    with pytest.raises(ValueError):
        gx.GrpcException(status_code=grpc.StatusCode.OK)


def test_extending():
    """We can extend ExceptionToStatusInterceptor."""
    interceptor = ExtendedExceptionToStatusInterceptor()
    special_cases = {"error": raises(NonGrpcException())}
    with dummy_client(
        special_cases=special_cases, interceptors=[interceptor]
    ) as client:
        assert (
            client.Execute(DummyRequest(input="foo")).output == "foo"
        )  # Test a happy path too
        assert not interceptor.caught_custom_exception
        with pytest.raises(grpc.RpcError) as e:
            client.Execute(DummyRequest(input="error"))
        assert e.value.code() == NonGrpcException.TEST_STATUS_CODE
        assert e.value.details() == NonGrpcException.TEST_DETAILS
        assert interceptor.caught_custom_exception
