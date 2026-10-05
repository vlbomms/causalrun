"""One HTTP attempt, with a deadline and no redirects or retry loop."""
import json
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
from .contracts import canonical


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        return None


def request_with_headers(target, path, token, body=None, *, method=None, headers=None, allow_missing=False):
    data = None if body is None else canonical(body).encode()
    call_headers = {'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'}
    call_headers.update(headers or {})
    call = Request(target + path, data=data, headers=call_headers, method=method)
    # Do not send credentials through environment-configured proxies.
    opener = build_opener(ProxyHandler({}), NoRedirect())
    try:
        with opener.open(call, timeout=5) as response:
            data = response.read(65537)
            if len(data) > 65536:
                raise ValueError('Provider response exceeds 64 KiB')
            return response.status, json.loads(data), dict(response.headers)
    except HTTPError as error:
        if error.code == 404 and allow_missing:
            return 404, None, {}
        raise


def request(target, path, token, body=None, *, allow_missing=False):
    status, value, _ = request_with_headers(target, path, token, body, allow_missing=allow_missing)
    return status, value
