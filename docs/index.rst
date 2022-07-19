Simplified Python gRPC Interceptors
===================================

.. toctree::
   :hidden:
   :maxdepth: 1

   reference
   license

.. contents::

The primary aim of this project is to make Python gRPC interceptors simple.
The Python ``grpc`` package provides service interceptors, but they're a bit hard to
use because of their flexibility. The ``grpc`` interceptors don't have direct access
to the request and response objects, or the service context. Access to these are often
desired, to be able to log data in the request or response, or set status codes on the
context.

The secondary aim of this project is to keep the code small and simple. Code you can
read through and understand quickly gives you confidence and helps debug issues. When
you install this package, you also don't want a bunch of other packages that might
cause conflicts within your project. Too many dependencies slow down installation
as well as runtime (fresh imports take time). Hence, a goal of this project is to keep
dependencies to a minimum. The only core dependency is the ``grpc`` package, and the
``testing`` extra includes ``protobuf`` as well.

The ``grpc_interceptor`` package provides the following:

* A ``ServerInterceptor`` base class, to make it easy to define your own server-side
  interceptors. Do not confuse this with the ``grpc.ServerInterceptor`` class.
* An ``AsyncServerInterceptor`` base class, which is the analogy for async server-side
  interceptors.
* An ``ExceptionToStatusInterceptor`` interceptor, so your service can raise exceptions
  that set the gRPC status code correctly (rather than the default of every exception
  resulting in an ``UNKNOWN`` status code). This is something for which pretty much any
  service will have a use.
* An ``AsyncExceptionToStatusInterceptor`` interceptor, which is the analogy for async
  ``ExceptionToStatusInterceptor``.
* A ``ClientInterceptor`` base class, to make it easy to define your own client-side interceptors.
  Do not confuse this with the ``grpc.ClientInterceptor`` class. (Note, there is currently no
  async analogy to ``ClientInterceptor``, though contributions are welcome.)
* An optional testing framework. If you're writing your own interceptors, this is useful.
  If you're just using ``ExceptionToStatusInterceptor`` then you don't need this.

Installation
------------

To install just the interceptors:

.. code-block:: console

   $ pip install grpc-interceptor

To also install the testing framework:

.. code-block:: console

   $ pip install grpc-interceptor[testing]

Usage
-----

Server Interceptors
^^^^^^^^^^^^^^^^^^^

To define your own server interceptor (we can use a simplified version of
``ExceptionToStatusInterceptor`` as an example):

.. code-block:: python

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

Then inject your interceptor when you create the ``grpc`` server:

.. code-block:: python

   interceptors = [ExceptionToStatusInterceptor()]
   server = grpc.server(
       futures.ThreadPoolExecutor(max_workers=10),
       interceptors=interceptors
   )

To use ``ExceptionToStatusInterceptor``:

.. code-block:: python

   from grpc_interceptor.exceptions import NotFound

   class MyService(my_pb2_grpc.MyServiceServicer):
       def MyRpcMethod(
           self, request: MyRequest, context: grpc.ServicerContext
       ) -> MyResponse:
           thing = lookup_thing()
           if not thing:
               raise NotFound("Sorry, your thing is missing")
           ...

This results in the gRPC status status code being set to ``NOT_FOUND``,
and the details ``"Sorry, your thing is missing"``. This saves you the hassle of
catching exceptions in your service handler, or passing the context down into
helper functions so they can call ``context.abort`` or ``context.set_code``. It allows
the more Pythonic approach of just raising an exception from anywhere in the code,
and having it be handled automatically.

Server Streaming Interceptors
"""""""""""""""""""""""""""""

The above example shows how to write an interceptor for a unary-unary RPC. Server
streaming RPCs need to be handled a little differently because ``method(request, context)``
will return a generator. Hence, the code won't actually run until you iterate over it.
Hence, if we were to continue the example of catching exceptions from RPCs, we would
need to do something like this:

.. code-block:: python

    class ExceptionToStatusInterceptor(ServerInterceptor):

        def intercept(
            self,
            method: Callable,
            request: Any,
            context: grpc.ServicerContext,
            method_name: str,
        ) -> Any:
            try:
                for response in method(request, context):
                    yield response
            except GrpcException as e:
                context.set_code(e.status_code)
                context.set_details(e.details)
                raise

However, this will *only* work for server streaming RPCs. In order to work with both
unary and streaming RPCs, you'll need to handle the unary case and streaming case
separately, like this:

.. code-block:: python

    class ExceptionToStatusInterceptor(ServerInterceptor):

        def intercept(self, method, request, context, method_name):
            # Call the RPC. It could be either unary or streaming
            try:
                response_or_iterator = method(request, context)
            except GrpcException as e:
                # If it was unary, then any exception raised would be caught
                # immediately, so handle it here.
                context.set_code(e.status_code)
                context.set_details(e.details)
                raise
            # Check if it's streaming
            if hasattr(response_or_iterator, "__iter__"):
                # Now we know it's a server streaming RPC, so the actual RPC method
                # hasn't run yet. Delegate to a helper to iterate over it so it runs.
                # The helper needs to re-yield the responses, and we need to return
                # the generator that produces.
                return self._intercept_streaming(response_or_iterator)
            else:
                # For unary cases, we are done, so just return the response.
                return response_or_iterator

        def _intercept_streaming(self, iterator):
            try:
                for resp in iterator:
                    yield resp
            except GrpcException as e:
                context.set_code(e.status_code)
                context.set_details(e.details)
                raise

Async Server Interceptors
"""""""""""""""""""""""""

Async interceptors are similar to sync ones, but there two things of which you need to
be aware.

First, async server streaming RPCs that are implemented with ``async def + yield``
cannot be awaited. When you call such a method, you get back an ``async_generator``.
This is not ``await``-able (though you can ``async for`` loop over it). This is
contrary to a unary RPC is implemented with ``async def + return``. That results in a
coroutine when called, which you *can* ``await``.

All this is to say that you mustn't await ``method(request, context)`` in an async
interceptor immediately. First, check if it's an ``async_generator``. You can do this
by checking for the presence of the ``__aiter__`` attribute.

Here's an async version of our running ``ExceptionToStatusInterceptor`` example:

.. code-block:: python

    from grpc_interceptor.exceptions import GrpcException
    from grpc_interceptor.server import AsyncServerInterceptor

    class AsyncExceptionToStatusInterceptor(AsyncServerInterceptor):

        async def intercept(
            self,
            method: Callable,
            request_or_iterator: Any,
            context: grpc.ServicerContext,
            method_name: str,
        ) -> Any:
            try:
                response_or_iterator = method(request_or_iterator, context)
                if not hasattr(response_or_iterator, "__aiter__"):
                    # Unary, just await and return the response
                    return await response_or_iterator
            except GrpcException as e:
                await context.set_code(e.status_code)
                await context.set_details(e.details)
                raise

            # Server streaming responses, delegate to an async generator helper.
            # Note that we do NOT await this.
            return self._intercept_streaming(response_or_iterator, context)

        async def _intercept_streaming(self, iterator):
            try:
                async for r in iterator:
                    yield r
            except GrpcException as e:
                await context.set_code(e.status_code)
                await context.set_details(e.details)
                raise

The second thing you must be aware of with async RPCs, is that an
`alternate streaming API <https://github.com/lidizheng/proposal/blob/grpc-python-async-api/L58-python-async-api.md#new-streaming-api---reader--writer-api>`_
was added. With this API, instead of writing a server streaming RPC with
``async def + yield``, you write it as ``async def + return``, but it returns ``None``.
The way it streams responses is by calling ``await context.write(...)`` for each response
it streams. Similarly, client streaming can be achieved by calling
``await context.read()`` instead of iterating over the request object.

If you must support RPC services written using this new API, then you must be aware that
a server streaming RPC could return ``None``. In that case it will not be an
``async_generator`` even though it's streaming. You will also need your own solution to
get access to the streaming response objects. For example, you could wrap the
``context`` object that you pass to ``method(request, context)``, so that you can
capture ``read`` and ``write`` calls.

Client Interceptors
^^^^^^^^^^^^^^^^^^^

We will use an invocation metadata injecting interceptor as an example of defining
a client interceptor:

.. code-block:: python

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

Now inject your interceptor when you create the ``grpc`` channel:

.. code-block:: python

    interceptors = [MetadataClientInterceptor()]
    with grpc.insecure_channel("grpc-server:50051") as channel:
        channel = grpc.intercept_channel(channel, *interceptors)
        ...

Client interceptors can also be used to retry RPCs that fail due to specific errors, or
a host of other use cases. There are some basic approaches in the tests to get you
started.

Testing
-------

The testing framework provides an actual gRPC service and client, which you can inject
interceptors into. This allows end-to-end testing, rather than mocking things out (such
as the context). This can catch interactions between your interceptors and the gRPC
framework, and also allows chaining interceptors.

The crux of the testing framework is the ``dummy_client`` context manager. It provides
a client to a gRPC service, which by defaults echos the ``input`` field of the request
to the ``output`` field of the response.

You can also provide a ``special_cases`` dict which tells the service to call arbitrary
functions when the input matches a key in the dict. This allows you to test things like
exceptions being thrown.

Here's an example (again using ``ExceptionToStatusInterceptor``):

.. code-block:: python

   from grpc_interceptor import ExceptionToStatusInterceptor
   from grpc_interceptor.exceptions import NotFound
   from grpc_interceptor.testing import dummy_client, DummyRequest, raises

   def test_exception():
       special_cases = {"error": raises(NotFound())}
       interceptors = [ExceptionToStatusInterceptor()]
       with dummy_client(special_cases=special_cases, interceptors=interceptors) as client:
           # Test a happy path first
           assert client.Execute(DummyRequest(input="foo")).output == "foo"
           # And now a special case
           with pytest.raises(grpc.RpcError) as e:
               client.Execute(DummyRequest(input="error"))
           assert e.value.code() == grpc.StatusCode.NOT_FOUND

Limitations
-----------

Known limitations:

* Async client interceptors are not implemented.
* The ``read`` / ``write`` API for async streaming technically works,
  but you'll need to roll your own solution to get access to streaming
  request and response objects.

Contributions or requests are welcome for any limitations you may find.
