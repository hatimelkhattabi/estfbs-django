import json
from functools import lru_cache
from django.conf import settings
from django.db import DatabaseError


@lru_cache(maxsize=1)
def formations():
    return json.loads(
        (settings.BASE_DIR / "data/formations.json").read_text(encoding="utf-8")
    )


def site_context(request):
    from .views import visitor_stats

    try:
        stats = visitor_stats(request)
    except DatabaseError:
        stats = {
            "total_consultations": 0,
            "unique_visitors": 0,
            "today_consultations": 0,
            "visitor_consultations": 0,
        }
    return {
        "formations": formations(),
        "stats": stats,
        "counter_digits": str(stats["total_consultations"]).zfill(6),
        "current_route": (
            request.resolver_match.url_name if request.resolver_match else ""
        ),
        "query": request.GET,
        "django_messages": list(
            __import__(
                "django.contrib.messages", fromlist=["get_messages"]
            ).get_messages(request)
        ),
    }
