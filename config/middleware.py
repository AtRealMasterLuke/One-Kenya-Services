CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self'",
        # Map tiles come from OpenStreetMap; photos are served from our own views.
        "img-src 'self' data: https://tile.openstreetmap.org",
        "connect-src 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
        "base-uri 'self'",
        "object-src 'none'",
    ]
)


class SecurityHeadersMiddleware:
    """Headers Django 5.2 does not set itself: CSP, Permissions-Policy and the cross-origin
    policies. COEP is deliberately absent: require-corp would block OpenStreetMap tiles, and the
    app uses nothing that needs cross-origin isolation."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.headers.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
        response.headers.setdefault("Permissions-Policy", "geolocation=(self), camera=(), microphone=()")
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        return response
