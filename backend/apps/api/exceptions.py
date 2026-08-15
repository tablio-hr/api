from rest_framework.exceptions import NotFound
from rest_framework.views import exception_handler as drf_exception_handler


def exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is not None and isinstance(exc, NotFound):
        response.data = {"detail": "Not found.", "code": "not_found"}
    return response
