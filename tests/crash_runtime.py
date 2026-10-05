"""Test-only process exits at protocol boundaries; no production fault controls."""
import argparse
import json
import os
from causalrun import runtime, storage
from causalrun.server import create_server


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--db', required=True)
    parser.add_argument('--phase', choices=['before_authorization_commit', 'after_authorization_commit',
                                           'after_provider_commit', 'after_receipt_commit'], required=True)
    args = parser.parse_args()
    if args.phase == 'before_authorization_commit':
        original = runtime.event
        def crash_event(db, action_id, kind, detail):
            original(db, action_id, kind, detail)
            if kind == 'AUTHORIZED':
                os._exit(71)
        runtime.event = crash_event
    elif args.phase in ('after_authorization_commit', 'after_provider_commit'):
        original = runtime.request
        def crash_request(*positional, **keywords):
            if args.phase == 'after_authorization_commit':
                os._exit(71)
            original(*positional, **keywords)
            os._exit(71)
        runtime.request = crash_request
    else:
        original = runtime.commit_receipt
        def crash_receipt(*positional, **keywords):
            original(*positional, **keywords)
            os._exit(71)
        runtime.commit_receipt = crash_receipt
    storage.initialize(args.db)
    server = create_server(args.db, 0, os.environ['CAUSALRUN_AGENT_TOKEN'],
                           os.environ['CAUSALRUN_PROVIDER_TOKEN'], os.environ['CAUSALRUN_RECEIPT_TOKEN'])
    print(json.dumps({'listening': server.server_address}), flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
