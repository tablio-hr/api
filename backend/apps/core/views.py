from django.db import connection
from django.http import JsonResponse
from django.conf import settings


def health(_request):
    return JsonResponse({"status": "ok"})


def ready(_request):
    checks = {"database": "ok", "redis": "ok"}
    status = 200
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        if connection.settings_dict.get("NAME") in (None, "", ":memory:"):
            pass
    except Exception:
        checks["database"] = "unavailable"
        status = 503

    try:
        import redis

        client = redis.from_url(settings.REDIS_URL, socket_connect_timeout=1, socket_timeout=1)
        if client.ping() is not True:
            raise RuntimeError("redis ping failed")
    except Exception:
        checks["redis"] = "unavailable"
        status = 503

    payload = {"status": "ok" if status == 200 else "unavailable", "checks": checks}
    return JsonResponse(payload, status=status)
