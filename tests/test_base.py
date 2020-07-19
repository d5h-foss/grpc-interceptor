"""Test cases for the grpc-interceptor base Interceptor."""

from collections import defaultdict

import grpc
import pytest

from grpc_interceptor.base import Interceptor
from tests.dummy_client import dummy_client
from tests.protos.dummy_pb2 import DummyRequest


class CountingInterceptor(Interceptor):
    """A test interceptor that counts calls and exceptions."""

    def __init__(self):
        """Initialize counts to zero."""
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
