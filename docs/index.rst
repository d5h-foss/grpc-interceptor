Simplified Python gRPC Interceptors
===================================

.. toctree::
   :hidden:
   :maxdepth: 1

   reference
   license

The primary aim of this project is to make Python gRPC interceptors simple.
The Python ``grpc`` package provides service interceptors, but they're a bit hard to
use because of their flexibility. The ``grpc`` interceptors don't have direct access
to the request and response objects, or the service context. Access to these are often
desired, to be able to log data in the request or response, or set status codes on the
context.

The secondary aim of this project is to keep the code small and simple. Code you can
read through and understand quickly gives you confidence and helps debug issues. When
you install this package, you also don't want a bunch of other packages that might
cause conflicts within your project. Too many dependencies also slow down installation
as well as runtime (fresh imports take time). Hence, a goal of this project is to keep
dependencies to a minimum. The only core dependency is the ``grpc`` package, and the
``testing`` extra includes ``protobuf`` as well.

The ``grpc_interceptor`` package provides the following:

* An ``Interceptor`` base class, to make it easy to define your own service interceptors.
* An ``ExceptionToStatusInterceptor`` interceptor, so your service can raise exceptions
  that set the gRPC status code correctly (rather than the default of every exception
  resulting in an ``UNKNOWN`` status code). This is something for which pretty much any
  service will have a use.
* An optional testing framework. If you're writing your own interceptors, this is useful.

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

To define your own interceptor (we can use ``ExceptionToStatusInterceptor`` as an example):

.. code-block:: python

   from grpc_interceptor.base import Interceptor

   class ExceptionToStatusInterceptor(Interceptor):

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

Testing
-------

The testing framework provides an actual gRPC service and client, which you can inject
interceptors into. This allows end-to-end testing, rather than mocking things out (such
as the context). This can catch interactions between your interceptors and the gRPC
framework, and also allows chaining interceptors.

The crux of the testing framework is the ``dummy_client`` context manager. It provides
a client to a gRPC service, which by defaults echos the ``input`` field of the request
to the ``output`` field of the response. You can also provide a ``special_cases`` dict
which tells the service to call arbitrary functions when the input matches a key in the
dict. This allows you to test things like exceptions being thrown. Here's an example
(again using ``ExceptionToStatusInterceptor``):

.. code-block:: python

   from grpc_interceptor.exceptions import NotFound
   from grpc_interceptor.exception_to_status import ExceptionToStatusInterceptor
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

These are the current limitations, although supporting these is possible. Contributions
or requests are welcome.

* ``Interceptor`` currently only supports unary-unary RPCs.
* The package only provides service interceptors.
