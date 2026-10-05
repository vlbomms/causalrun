"""A controlled application: the value and its receipt commit atomically."""
import argparse
import json
import os
import socket
import threading
from pathlib import Path
import sqlite3
import uuid
from http.server import ThreadingHTTPServer
from causalrun.contracts import Rejected, canonical, check_payload, digest
from causalrun.server import JSONHandler


class ProviderHandler(JSONHandler):
    def dispatch(self):
        if self.command == 'GET' and self.path == '/health':
            return {'status': 'ready'}
        if self.command == 'GET' and self.path == '/openapi.json':
            return json.loads(Path(__file__).with_name('openapi.json').read_text())
        self.authorized(self.server.receipt_token if self.command == 'GET' else self.server.token)
        if self.command == 'POST' and self.path == '/values':
            body = self.read_json()
            if set(body) != {'action_id', 'payload'}:
                raise Rejected('Expected action_id and payload', 400)
            if str(uuid.UUID(body['action_id'])) != body['action_id']:
                raise Rejected('Invalid action ID', 400)
            check_payload(body['payload'])
            mode = self.server.fault_mode
            if mode == 'delay_commit':
                self.server.request_received.set()
                if not self.server.allow_commit.wait(timeout=10):
                    raise Rejected('Controlled delayed commit still pending', 503)
            receipt = {'action_id': body['action_id'],
                       'payload_digest': digest(body['payload']),
                       'result': {'value': body['payload']['value']}}
            with sqlite3.connect(self.server.db_path, timeout=5) as db:
                db.execute('BEGIN IMMEDIATE')
                db.execute('INSERT INTO requests(action_id) VALUES(?)', (body['action_id'],))
                existing = db.execute('SELECT receipt FROM values_and_receipts WHERE action_id=?',
                                      (body['action_id'],)).fetchone()
                if existing:
                    if existing[0] != canonical(receipt):
                        raise Rejected('Action ID was used with a different payload')
                else:
                    db.execute('INSERT INTO values_and_receipts VALUES(?,?,?)',
                               (body['action_id'], body['payload']['value'], canonical(receipt)))
            if mode == 'drop_response':
                self.close_connection = True
                self.connection.shutdown(socket.SHUT_RDWR)
                raise ConnectionAbortedError('Controlled response loss after commit')
            return receipt
        if self.command == 'GET' and self.path.startswith('/receipts/'):
            mode = self.server.fault_mode
            if mode == 'missing_receipt':
                raise Rejected('Controlled absent evidence', 404)
            if mode == 'verifier_error':
                raise Rejected('Controlled evidence unavailable', 503)
            action_id = self.path.removeprefix('/receipts/')
            with sqlite3.connect(self.server.db_path) as db:
                row = db.execute('SELECT receipt FROM values_and_receipts WHERE action_id=?',
                                 (action_id,)).fetchone()
            if row is None:
                raise Rejected('Receipt not found; this does not prove non-execution', 404)
            receipt = json.loads(row[0])
            if mode == 'wrong_action':
                receipt['action_id'] = str(uuid.uuid4())
            elif mode == 'wrong_payload':
                receipt['payload_digest'] = 'unrelated payload'
            elif mode == 'wrong_value':
                receipt['result']['value'] = 'unrelated value'
            return receipt
        raise Rejected('Endpoint not found', 404)


def create_server(path, port, token, fault_mode='none', receipt_token=None):
    if len(token) < 16:
        raise Rejected('Provider token must have at least 16 characters', 400)
    if receipt_token is not None and (len(receipt_token) < 16 or receipt_token == token):
        raise Rejected('Receipt credential must be distinct and at least 16 characters', 400)
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    os.close(descriptor)
    os.chmod(path, 0o600)
    with sqlite3.connect(path) as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.executescript('''
            CREATE TABLE IF NOT EXISTS values_and_receipts (
                action_id TEXT PRIMARY KEY, value TEXT NOT NULL, receipt TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS requests (
                sequence INTEGER PRIMARY KEY, action_id TEXT NOT NULL
            );
        ''')
    server = ThreadingHTTPServer(('127.0.0.1', port), ProviderHandler)
    server.db_path = path
    server.token = token
    server.receipt_token = receipt_token or token
    server.fault_mode = fault_mode
    server.request_received = threading.Event()
    server.allow_commit = threading.Event()
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', required=True)
    parser.add_argument('--port', type=int, default=8090)
    parser.add_argument('--fault', choices=['none', 'drop_response', 'missing_receipt',
                                         'wrong_action', 'wrong_payload', 'wrong_value', 'verifier_error'],
                        default='none', help='Disposable demonstration targets only')
    args = parser.parse_args()
    server = create_server(args.db, args.port, os.environ['CAUSALRUN_PROVIDER_TOKEN'], args.fault,
                           os.environ.get('CAUSALRUN_RECEIPT_TOKEN'))
    print(json.dumps({'listening': server.server_address}), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
