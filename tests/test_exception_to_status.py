import grpc
import pytest

from grpc_interceptor import exceptions as gx
from grpc_interceptor.exception_to_status import ExceptionToStatusInterceptor
from tests.dummy_client import dummy_client
from tests.protos.dummy_pb2 import DummyRequest


@pytest.fixture
def interceptors():
    return [ExceptionToStatusInterceptor()]


def _raise(e: Exception):
    raise e


def test_repr():
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


def test_no_exception(interceptors):
    with dummy_client(special_cases={}, interceptors=interceptors) as client:
        assert client.Execute(DummyRequest(input="foo")).output == "foo"


def test_custom_details(interceptors):
    special_cases = {"error": lambda _: _raise(gx.NotFound(details="custom"))}
    with dummy_client(special_cases=special_cases, interceptors=interceptors) as client:
        assert (
            client.Execute(DummyRequest(input="foo")).output == "foo"
        )  # Test a happy path too
        with pytest.raises(grpc.RpcError) as e:
            client.Execute(DummyRequest(input="error"))
        assert e.value.code() == grpc.StatusCode.NOT_FOUND
        assert e.value.details() == "custom"


def test_all_exceptions(interceptors):
    # Make sure we cover every status code,
    # and they each produce unique codes and details
    all_status_codes = {sc for sc in grpc.StatusCode if sc != grpc.StatusCode.OK}
    seen_codes = set()
    seen_details = set()

    for sc in all_status_codes:
        ex = getattr(gx, _snake_to_camel(sc.name))
        assert ex
        special_cases = {"error": lambda _: _raise(ex())}
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
    with pytest.raises(ValueError):
        gx.GrpcException(status_code=grpc.StatusCode.OK)
