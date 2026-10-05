"""A tiny test client for the actual stdio process, not a simulated tool function."""
import json
import os
import select
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Client:
    def __init__(self, state, env=None, archive=None):
        command = ([sys.executable, str(archive), '--mcp', '--state-dir', str(state)] if archive else
                   [sys.executable, '-m', 'causalrun.mcp', '--state', str(state)])
        self.process = subprocess.Popen(command, cwd=ROOT, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE, text=True, bufsize=1)
        self.counter = 0
        initialized = self.request('initialize', {'protocolVersion': '2025-11-25', 'capabilities': {},
                                                  'clientInfo': {'name': 'causalrun-test-harness', 'version': '1'}})
        assert 'result' in initialized, initialized
        self.notify('notifications/initialized')

    def notify(self, method, params=None):
        self.process.stdin.write(json.dumps({'jsonrpc': '2.0', 'method': method, 'params': params or {}}) + '\n')
        self.process.stdin.flush()

    def request(self, method, params=None):
        self.counter += 1
        self.process.stdin.write(json.dumps({'jsonrpc': '2.0', 'id': self.counter, 'method': method, 'params': params or {}}) + '\n')
        self.process.stdin.flush()
        if not select.select([self.process.stdout], [], [], 30)[0]:
            raise AssertionError('MCP response deadline exceeded')
        line = self.process.stdout.readline()
        if not line: raise AssertionError('MCP server exited: ' + self.process.stderr.read())
        response = json.loads(line)
        assert response['id'] == self.counter, response
        return response

    def call(self, name, arguments):
        result = self.request('tools/call', {'name': name, 'arguments': arguments})
        if 'error' in result: return result
        return result['result']

    def close(self):
        if self.process.poll() is None:
            self.process.stdin.close()
            try: self.process.wait(5)
            except subprocess.TimeoutExpired:
                self.process.kill(); self.process.wait(5)
        self.process.stdout.close(); self.process.stderr.close()
