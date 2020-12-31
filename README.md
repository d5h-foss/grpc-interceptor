[![Tests](https://github.com/d5h-foss/grpc-interceptor/workflows/Tests/badge.svg)](https://github.com/d5h-foss/grpc-interceptor/actions?workflow=Tests)
[![Codecov](https://codecov.io/gh/d5h-foss/grpc-interceptor/branch/master/graph/badge.svg)](https://codecov.io/gh/d5h-foss/grpc-interceptor)
[![Read the Docs](https://readthedocs.org/projects/grpc-interceptor/badge/)](https://grpc-interceptor.readthedocs.io/)
[![PyPI](https://img.shields.io/pypi/v/grpc-interceptor.svg)](https://pypi.org/project/grpc-interceptor/)

# Summary

Simplified Python gRPC interceptors.

The Python `grpc` package provides service interceptors, but they're a bit hard to
use because of their flexibility. The `grpc` interceptors don't have direct access
to the request and response objects, or the service context. Access to these are often
desired, to be able to log data in the request or response, or set status codes on the
context.

# Installation

To just get the interceptors (and probably not write your own):

```console
$ pip install grpc-interceptor
```

To also get the testing framework, which is good if you're writing your own interceptors:

```console
$ pip install grpc-interceptor[testing]
```

# Usage

## Server Interceptor

To define your own interceptor (we can use `ExceptionToStatusInterceptor` as an example):

```python
from grpc_interceptor import ServerInterceptor
from grpc_interceptor.exceptions import GrpcException

class ExceptionToStatusInterceptor(ServerInterceptor):
    def intercept(
        self,
        method: Callable,
        request: Any,
        context: grpc.ServicerContext,
        method_name: str,
    ) -> Any:
        """Override this method to implement a custom interceptor.
         You should call method(request, context) to invoke the
         next handler (either the RPC method implementation, or the
         next interceptor in the list).
         Args:
             method: The next interceptor, or method implementation.
             request: The RPC request, as a protobuf message.
             context: The ServicerContext pass by gRPC to the service.
             method_name: A string of the form
                 "/protobuf.package.Service/Method"
         Returns:
             This should generally return the result of
             method(request, context), which is typically the RPC
             method response, as a protobuf message. The interceptor
             is free to modify this in some way, however.
         """
        try:
            return method(request, context)
        except GrpcException as e:
            context.set_code(e.status_code)
            context.set_details(e.details)
            raise
```

Then inject your interceptor when you create the `grpc` server:

```python
interceptors = [ExceptionToStatusInterceptor()]
server = grpc.server(
    futures.ThreadPoolExecutor(max_workers=10),
    interceptors=interceptors
)
```

To use `ExceptionToStatusInterceptor`:

```python
from grpc_interceptor.exceptions import NotFound

class MyService(my_pb2_grpc.MyServiceServicer):
    def MyRpcMethod(
        self, request: MyRequest, context: grpc.ServicerContext
    ) -> MyResponse:
        thing = lookup_thing()
        if not thing:
            raise NotFound("Sorry, your thing is missing")
        ...
```

This results in the gRPC status status code being set to `NOT_FOUND`,
and the details `"Sorry, your thing is missing"`. This saves you the hassle of
catching exceptions in your service handler, or passing the context down into
helper functions so they can call `context.abort` or `context.set_code`. It allows
the more Pythonic approach of just raising an exception from anywhere in the code,
and having it be handled automatically.

## Client Interceptor

We will use an invocation metadata injecting interceptor as an example of defining
a client interceptor:

```python
from grpc_interceptor import ClientCallDetails, ClientInterceptor

class MetadataClientInterceptor(ClientInterceptor):

    def intercept(
        self,
        method: Callable,
        request_or_iterator: Any,
        call_details: grpc.ClientCallDetails,
    ):
        """Override this method to implement a custom interceptor.

        This method is called for all unary and streaming RPCs. The interceptor
        implementation should call `method` using a `grpc.ClientCallDetails` and the
        `request_or_iterator` object as parameters. The `request_or_iterator`
        parameter may be type checked to determine if this is a singluar request
        for unary RPCs or an iterator for client-streaming or client-server streaming
        RPCs.

        Args:
            method: A function that proceeds with the invocation by executing the next
                interceptor in the chain or invoking the actual RPC on the underlying
                channel.
            request_or_iterator: RPC request message or iterator of request messages
                for streaming requests.
            call_details: Describes an RPC to be invoked.

        Returns:
            The type of the return should match the type of the return value received
            by calling `method`. This is an object that is both a
            `Call <https://grpc.github.io/grpc/python/grpc.html#grpc.Call>`_ for the
            RPC and a `Future <https://grpc.github.io/grpc/python/grpc.html#grpc.Future>`_.

            The actual result from the RPC can be got by calling `.result()` on the
            value returned from `method`.
        """
        new_details = ClientCallDetails(
            call_details.method,
            call_details.timeout,
            [("authorization", "Bearer mysecrettoken")],
            call_details.credentials,
            call_details.wait_for_ready,
            call_details.compression,
        )

        return method(request_or_iterator, new_details)
```

Now inject your interceptor when you create the ``grpc`` channel:

```python
interceptors = [MetadataClientInterceptor()]
with grpc.insecure_channel("grpc-server:50051") as channel:
    channel = grpc.intercept_channel(channel, *interceptors)
    ...
```

Client interceptors can also be used to retry RPCs that fail due to specific errors, or
a host of other use cases. There are some basic approaches in the tests to get you
started.

# Documentation

Read the [complete documentation here](https://grpc-interceptor.readthedocs.io/).
