from django.http import HttpResponse, JsonResponse


def manifest(request):
    response = JsonResponse(
        {
            "name": "سامانه روشنگران RSP",
            "short_name": "RSP",
            "description": "سامانه آموزشی روشنگران",
            "lang": "fa",
            "dir": "rtl",
            "start_url": "/dashboard/",
            "scope": "/",
            "display": "standalone",
            "background_color": "#ffffff",
            "theme_color": "#ffffff",
            "icons": [
                {"src": "/static/pwa/icon-192.png", "sizes": "192x192", "type": "image/png"},
                {"src": "/static/pwa/icon-512.png", "sizes": "512x512", "type": "image/png"},
            ],
        },
        json_dumps_params={"ensure_ascii": False},
    )
    response["Content-Type"] = "application/manifest+json"
    response["Cache-Control"] = "no-store"
    return response


def service_worker(request):
    response = HttpResponse(
        """// RSP PWA: no offline storage of private pages or user data.
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', event => {
  event.waitUntil(self.clients.claim());
});
""",
        content_type="text/javascript; charset=utf-8",
    )
    response["Cache-Control"] = "no-store"
    response["Service-Worker-Allowed"] = "/"
    return response
