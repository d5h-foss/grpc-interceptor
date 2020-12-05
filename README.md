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

To define your own client interceptor, we will use a simple invocation
metadata injecting interceptor as an example:

```python
from grpc_interceptor import ClientCallDetails, ClientInterceptor

class MetadataClientInterceptor(ClientInterceptor):

    def intercept(
        self,
        call_details: ClientCallDetails,
        request_iterator: Iterator[Message],
        request_streaming: bool,
        response_streaming: bool,
    ) -> Tuple[ClientCallDetails, Iterator[Message], Optional[Callable]]:
        """Override this method to implement a custom interceptor.

        This method is called for all unary and streaming RPCs with the
        appropriate boolean parameters set. The returned
        ClientCallDetails and request message(s) will be passed to
        either the next interceptor or RPC implementation. An optional
        callback function can be returned to perform postprocessing on RPC
        responses.

        Args:
            call_details (ClientCallDetails): Describes an RPC to be invoked
            request_iterator (Iterator[Message]): RPC request messages
            request_streaming (bool): True if RPC is client or bi-directional streaming
            response_streaming (bool): True if PRC is server or bi-directional streaming

        Returns:
            This should return a tuple of ClientCallDetails, RPC request
            message iterator, and a postprocessing callback function or None.
        """
        call_details.metadata.append(
            ("authorization", "Bearer mysecrettoken")
        )

        return call_details, request_iterator, None
```

An optional callback function can be included as the third element of the
`intercept` function's return tuple. This can be used for additional
post-processing of the intercepted call.

Now inject your interceptor when you create the ``grpc`` channel:

```python
interceptors = [MetadataClientInterceptor()]
with grpc.insecure_channel("grpc-server:50051") as channel:
    channel = grpc.intercept_channel(channel, *interceptors)
    ...
```

# Documentation

Read the [complete documentation here](https://grpc-interceptor.readthedocs.io/).
