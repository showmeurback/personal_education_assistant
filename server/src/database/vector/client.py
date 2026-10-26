import functools
from contextlib import contextmanager

import weaviate

from settings import settings


def connect():
    return weaviate.connect_to_local(
        host=settings.weaviate_host,
        port=settings.weaviate_port,
        grpc_port=settings.weaviate_grpc_port,
    )


@contextmanager
def weaviate_client():
    client = connect()
    try:
        yield client
    finally:
        client.close()


def wvt_client(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if kwargs.get("client") is not None:
            return func(*args, **kwargs)
        with weaviate_client() as client:
            kwargs["client"] = client
            return func(*args, **kwargs)
    return wrapper
