"""Test cases for ExceptionToStatusInterceptor."""

import grpc
import pytest

from grpc_interceptor import exceptions as gx
from grpc_interceptor.exception_to_status import ExceptionToStatusInterceptor
from grpc_interceptor.testing import dummy_client, DummyRequest, raises


@pytest.fixture
def interceptors():
    """The interceptor chain for this test suite."""
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


def _snake_to_camel(s: str) -> str:
    return "".join([p.title() for p in s.split("_")])


def test_not_ok():
    """We cannot create a GrpcException with an OK status code."""
    with pytest.raises(ValueError):
        gx.GrpcException(status_code=grpc.StatusCode.OK)
