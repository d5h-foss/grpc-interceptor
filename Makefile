TEST_PROTOS := src/grpc_interceptor/testing/protos/dummy.proto
TEST_PROTO_GEN := $(shell echo $(TEST_PROTOS) | sed 's/\.proto/_pb2.py/g') \
				  $(shell echo $(TEST_PROTOS) | sed 's/\.proto/_pb2_grpc.py/g')

$(TEST_PROTO_GEN): $(TEST_PROTOS)
	cd src && \
	printf "%s\n" $(TEST_PROTOS) | \
	sed 's|^src/||' | \
	xargs poetry run python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. --mypy_out=.

.PHONY: test
test: $(TEST_PROTO_GEN)
	poetry run pytest --cov

.PHONY: nox-test
nox-test: $(TEST_PROTO_GEN)
	nox -r
