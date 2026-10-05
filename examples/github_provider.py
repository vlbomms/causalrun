"""Disposable GitHub-shaped provider. Deliberately does not deduplicate POSTs."""
import copy
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit
import json


def create_server(repository='sandbox/issues', author='tester'):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def respond(self, status, value, link=None):
            data = json.dumps(value).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            if link:
                self.send_header('Link', link)
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):
            server = self.server
            if self.path != '/repos/' + repository + '/issues':
                return self.respond(404, {})
            if self.headers.get('Authorization') != 'Bearer fixture-write':
                return self.respond(403, {})
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            with server.lock:
                server.posts += 1
                number = server.posts
                url = server.target + '/repos/' + repository
                issue = dict(body, id=number, number=number, repository_url=url,
                             url=url + '/issues/' + str(number), user={'login': author})
                server.issues.append(issue)
            if server.drop_response:
                self.close_connection = True
                return
            self.respond(201, issue)

        def do_GET(self):
            server = self.server
            server.reads += 1
            if self.headers.get('Authorization') != 'Bearer fixture-read' or server.denied:
                return self.respond(403, {})
            parsed = urlsplit(self.path)
            if parsed.path != '/repos/' + repository + '/issues':
                return self.respond(404, {})
            page = int(parse_qs(parsed.query)['page'][0])
            with server.lock:
                issues = copy.deepcopy(server.issues)
            chunk = issues[(page - 1) * 100:page * 100]
            link = None
            if page * 100 < len(issues):
                link = ('<' + server.target + parsed.path +
                        '?state=all&per_page=100&sort=created&direction=asc&page=' + str(page + 1) + '>; rel="next"')
            if server.untrusted_link:
                link = '<https://untrusted.invalid/issues?page=2>; rel="next"'
            self.respond(200, chunk, link)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.target = 'http://127.0.0.1:' + str(server.server_port)
    server.lock = threading.Lock()
    server.posts = server.reads = 0
    server.issues = []
    server.drop_response = server.denied = server.untrusted_link = False
    return server
