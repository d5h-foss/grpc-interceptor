"""Test cases for the grpc-interceptor base ServerInterceptor."""

from collections import defaultdict

import grpc
import pytest

from grpc_interceptor import MethodName, parse_method_name, ServerInterceptor
from grpc_interceptor.testing import dummy_client, DummyRequest
from grpc_interceptor.testing.dummy_client import dummy_channel


class CountingInterceptor(ServerInterceptor):
    """A test interceptor that counts calls and exceptions."""

    def __init__(self):
        self.num_calls = defaultdict(int)
        self.num_errors = defaultdict(int)

    def intercept(self, method, request, context, method_name):
        """Count each call and exception."""
        self.num_calls[method_name] += 1
        try:
            return method(request, context)
        except Exception:
            self.num_errors[method_name] += 1
            raise


class SideEffectInterceptor(ServerInterceptor):
    """A test interceptor that calls a function for the side effect."""

    def __init__(self, side_effect):
        self._side_effect = side_effect

    def intercept(self, method, request, context, method_name):
        """Call the side effect and then the RPC method."""
        self._side_effect()
        return method(request, context)


class UppercasingInterceptor(ServerInterceptor):
    """A test interceptor that modifies the request by uppercasing the input field."""

    def intercept(self, method, request, context, method_name):
        """Uppercases request.input."""
        request.input = request.input.upper()
        return method(request, context)


class AbortingInterceptor(ServerInterceptor):
    """A test interceptor that aborts before calling the handler."""

    def __init__(self, message):
        self._message = message

    def intercept(self, method, request, context, method_name):
        """Calls abort."""
        context.abort(grpc.StatusCode.ABORTED, self._message)


def test_call_counts():
    """The counts should be correct."""
    intr = CountingInterceptor()
    interceptors = [intr]

    special_cases = {"error": lambda r, c: 1 / 0}
    with dummy_client(special_cases=special_cases, interceptors=interceptors) as client:
        assert client.Execute(DummyRequest(input="foo")).output == "foo"
        assert len(intr.num_calls) == 1
        assert intr.num_calls["/DummyService/Execute"] == 1
        assert len(intr.num_errors) == 0

        with pytest.raises(grpc.RpcError):
            client.Execute(DummyRequest(input="error"))

        assert len(intr.num_calls) == 1
        assert intr.num_calls["/DummyService/Execute"] == 2
        assert len(intr.num_errors) == 1
        assert intr.num_errors["/DummyService/Execute"] == 1


def test_interceptor_chain():
    """Interceptors are called in the right order."""
    trace = []
    interceptor1 = SideEffectInterceptor(lambda: trace.append(1))
    interceptor2 = SideEffectInterceptor(lambda: trace.append(2))
    with dummy_client(
        special_cases={}, interceptors=[interceptor1, interceptor2]
    ) as client:
        assert client.Execute(DummyRequest(input="test")).output == "test"
        assert trace == [1, 2]


def test_modifying_interceptor():
    """Interceptors can modify requests."""
    interceptor = UppercasingInterceptor()
    with dummy_client(special_cases={}, interceptors=[interceptor]) as client:
        assert client.Execute(DummyRequest(input="test")).output == "TEST"


def test_aborting_interceptor():
    """context.abort called in an interceptor works."""
    interceptor = AbortingInterceptor("oh no")
    with dummy_client(special_cases={}, interceptors=[interceptor]) as client:
        with pytest.raises(grpc.RpcError) as e:
            client.Execute(DummyRequest(input="test"))
        assert e.value.code() == grpc.StatusCode.ABORTED
        assert e.value.details() == "oh no"


def test_method_not_found():
    """Calling undefined endpoints should return Unimplemented.

    Interceptors are not invoked when the RPC call is not handled.
    """
    intr = CountingInterceptor()
    interceptors = [intr]

    with dummy_channel(special_cases={}, interceptors=interceptors) as channel:
        with pytest.raises(grpc.RpcError) as e:
            channel.unary_unary(
                "/DummyService/Unimplemented",
            )(b'')
        assert e.value.code() == grpc.StatusCode.UNIMPLEMENTED
        assert len(intr.num_calls) == 0
        assert len(intr.num_errors) == 0


def test_method_name():
    """Fields are correct and fully_qualified_service work."""
    mn = MethodName("foo.bar", "SearchService", "Search")
    assert mn.package == "foo.bar"
    assert mn.service == "SearchService"
    assert mn.method == "Search"
    assert mn.fully_qualified_service == "foo.bar.SearchService"


def test_empty_package_method_name():
    """fully_qualified_service works when there's no package."""
    mn = MethodName("", "SearchService", "Search")
    assert mn.fully_qualified_service == "SearchService"


def test_parse_method_name():
    """parse_method_name parses fields when there's a package."""
    mn = parse_method_name("/foo.bar.SearchService/Search")
    assert mn.package == "foo.bar"
    assert mn.service == "SearchService"
    assert mn.method == "Search"


def test_parse_empty_package():
    """parse_method_name works with no package."""
    mn = parse_method_name("/SearchService/Search")
    assert mn.package == ""
    assert mn.service == "SearchService"
    assert mn.method == "Search"
