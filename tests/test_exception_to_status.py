"""Test cases for ExceptionToStatusInterceptor."""
import re
from typing import Any, List, Optional, Union

import grpc
from grpc import aio as grpc_aio
import pytest

from grpc_interceptor import exceptions as gx
from grpc_interceptor.exception_to_status import (
    AsyncExceptionToStatusInterceptor,
    ExceptionToStatusInterceptor,
)
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


class AsyncExtendedExceptionToStatusInterceptor(AsyncExceptionToStatusInterceptor):
    """A test case for extending AsyncExceptionToStatusInterceptor."""

    def __init__(self):
        self.caught_custom_exception = False

    async def handle_exception(self, ex, request_or_iterator, context, method_name):
        """Handles NonGrpcException in a special way."""
        if isinstance(ex, NonGrpcException):
            self.caught_custom_exception = True
            await context.abort(
                NonGrpcException.TEST_STATUS_CODE, NonGrpcException.TEST_DETAILS
            )
        else:
            await super().handle_exception(
                ex, request_or_iterator, context, method_name
            )


def _get_interceptors(
    aio: bool, status_on_unknown_exception: Optional[grpc.StatusCode] = None
) -> List[Union[ExceptionToStatusInterceptor, AsyncExceptionToStatusInterceptor]]:
    return (
        [
            AsyncExceptionToStatusInterceptor(
                status_on_unknown_exception=status_on_unknown_exception
            )
        ]
        if aio
        else [
            ExceptionToStatusInterceptor(
                status_on_unknown_exception=status_on_unknown_exception
            )
        ]
    )


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


@pytest.mark.parametrize("aio", [False, True])
def test_no_exception(aio):
    """An RPC with no exceptions should work as if the interceptor wasn't there."""
    interceptors = _get_interceptors(aio)
    with dummy_client(
        special_cases={}, interceptors=interceptors, aio_server=aio
    ) as client:
        assert client.Execute(DummyRequest(input="foo")).output == "foo"


@pytest.mark.parametrize("aio", [False, True])
def test_custom_details(aio):
    """We can set custom details."""
    interceptors = _get_interceptors(aio)
    special_cases = {"error": raises(gx.NotFound(details="custom"))}
    with dummy_client(
        special_cases=special_cases, interceptors=interceptors, aio_server=aio
    ) as client:
        assert (
            client.Execute(DummyRequest(input="foo")).output == "foo"
        )  # Test a happy path too
        with pytest.raises(grpc.RpcError) as e:
            client.Execute(DummyRequest(input="error"))
        assert e.value.code() == grpc.StatusCode.NOT_FOUND
        assert e.value.details() == "custom"


@pytest.mark.parametrize("aio", [False, True])
def test_non_grpc_exception(aio):
    """Exceptions other than GrpcExceptions are ignored."""
    interceptors = _get_interceptors(aio)
    special_cases = {"error": raises(ValueError("oops"))}
    with dummy_client(
        special_cases=special_cases, interceptors=interceptors, aio_server=aio
    ) as client:
        with pytest.raises(grpc.RpcError) as e:
            client.Execute(DummyRequest(input="error"))
        assert e.value.code() == grpc.StatusCode.UNKNOWN


@pytest.mark.parametrize("aio", [False, True])
def test_non_grpc_exception_with_override(aio):
    """We can set a custom status code when non-GrpcExceptions are raised."""
    interceptors = _get_interceptors(
        aio, status_on_unknown_exception=grpc.StatusCode.INTERNAL
    )
    special_cases = {"error": raises(ValueError("oops"))}
    with dummy_client(
        special_cases=special_cases, interceptors=interceptors, aio_server=aio
    ) as client:
        with pytest.raises(grpc.RpcError) as e:
            client.Execute(DummyRequest(input="error"))
        assert e.value.code() == grpc.StatusCode.INTERNAL
        assert re.fullmatch(r"ValueError\('oops',?\)", e.value.details())


@pytest.mark.parametrize("aio", [False, True])
def test_aborted_context(aio):
    """If the context is aborted, the exception is propagated."""
    def error(request: Any, context: grpc.ServicerContext) -> None:
        context.abort(grpc.StatusCode.RESOURCE_EXHAUSTED, 'resource exhausted')

    async def async_error(request: Any, context: grpc_aio.ServicerContext) -> None:
        await context.abort(grpc.StatusCode.RESOURCE_EXHAUSTED, 'resource exhausted')

    interceptors = _get_interceptors(aio, grpc.StatusCode.INTERNAL)
    special_cases = {
        "error": async_error if aio else error
    }

    with dummy_client(
        special_cases=special_cases, interceptors=interceptors, aio_server=aio
    ) as client:
        with pytest.raises(grpc.RpcError) as e:
            client.Execute(DummyRequest(input="error"))
        assert e.value.code() == grpc.StatusCode.RESOURCE_EXHAUSTED


def test_override_with_ok():
    """We cannot set the default status code to OK."""
    with pytest.raises(ValueError):
        ExceptionToStatusInterceptor(status_on_unknown_exception=grpc.StatusCode.OK)
    with pytest.raises(ValueError):
        AsyncExceptionToStatusInterceptor(
            status_on_unknown_exception=grpc.StatusCode.OK
        )


@pytest.mark.parametrize("aio", [False, True])
def test_all_exceptions(aio):
    """Every gRPC status code is represented, and they each are unique.

    Make sure we aren't missing any status codes, and that we didn't copy paste the
    same status code or details into two different classes.
    """
    interceptors = _get_interceptors(aio)
    all_status_codes = {sc for sc in grpc.StatusCode if sc != grpc.StatusCode.OK}
    seen_codes = set()
    seen_details = set()

    for sc in all_status_codes:
        ex = getattr(gx, _snake_to_camel(sc.name))
        assert ex
        special_cases = {"error": raises(ex())}
        with dummy_client(
            special_cases=special_cases, interceptors=interceptors, aio_server=aio
        ) as client:
            with pytest.raises(grpc.RpcError) as e:
                client.Execute(DummyRequest(input="error"))
            assert e.value.code() == sc
            assert e.value.details() == ex.details
            seen_codes.add(sc)
            seen_details.add(ex.details)

    assert seen_codes == all_status_codes
    assert len(seen_details) == len(all_status_codes)


@pytest.mark.parametrize("aio", [False, True])
def test_exception_in_streaming_response(aio):
    """Exceptions are raised correctly from streaming responses."""
    interceptors = _get_interceptors(aio)
    with dummy_client(
        special_cases={"error": raises(gx.NotFound("not found!"))},
        interceptors=interceptors,
        aio_server=aio,
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


@pytest.mark.parametrize("aio", [False, True])
def test_extending(aio):
    """We can extend ExceptionToStatusInterceptor."""
    interceptor = (
        AsyncExtendedExceptionToStatusInterceptor()
        if aio
        else ExtendedExceptionToStatusInterceptor()
    )
    special_cases = {"error": raises(NonGrpcException())}
    with dummy_client(
        special_cases=special_cases, interceptors=[interceptor], aio_server=aio
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
