import threading

from django.utils.deprecation import MiddlewareMixin

_thread_locals = threading.local()


def get_current_user():
    return getattr(_thread_locals, "user", None)


class CurrentUserMiddleware(MiddlewareMixin):
    def process_request(self, request):
        user = getattr(request, "user", None)
        _thread_locals.user = user if (user and user.is_authenticated) else None
