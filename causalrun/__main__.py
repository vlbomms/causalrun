"""Operator CLI. Do not expose this command or its database to agent tools."""
import argparse
import json
import os
import sys
from pathlib import Path
from . import runtime, storage, validation, discovery, generation
from .contracts import Rejected, example_artifact
from .server import create_server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', default='.local/causalrun.sqlite')
    commands = parser.add_subparsers(dest='command', required=True)
    artifact = commands.add_parser('artifact', help='Emit a controlled connector artifact')
    artifact.add_argument('--target', required=True)
    discover = commands.add_parser('discover', help='Inspect API descriptions; stdout only')
    discover.add_argument('--spec', required=True)
    interview = commands.add_parser('interview', help='Ask only for intent and missing details')
    interview.add_argument('--spec', required=True)
    interview.add_argument('--target', required=True)
    interview.add_argument('--output', required=True, help='Save contract inputs, not discovery findings')
    build = commands.add_parser('build', help='Package source written by the host agent')
    build.add_argument('--interview', required=True)
    build.add_argument('--verifier', required=True)
    build.add_argument('--output', required=True)
    github_build = commands.add_parser('github-build', help='Package a GitHub issue verifier with completed user answers')
    github_build.add_argument('--repository', required=True)
    github_build.add_argument('--author', required=True)
    github_build.add_argument('--interview', required=True)
    github_build.add_argument('--verifier', required=True)
    github_build.add_argument('--output', required=True)
    http_build = commands.add_parser('http-build', help='Bind a declarative HTTP/JSON contract to a pure verifier')
    http_build.add_argument('--contract', required=True)
    http_build.add_argument('--verifier', required=True)
    http_build.add_argument('--output', required=True)
    register = commands.add_parser('register')
    register.add_argument('file')
    for command in ('validate', 'approve'):
        commands.add_parser(command).add_argument('digest')
    serve = commands.add_parser('serve')
    serve.add_argument('--port', type=int, default=8080)
    commands.add_parser('init')
    args = parser.parse_args()
    try:
        if args.command == 'artifact':
            print(json.dumps(example_artifact(args.target), indent=2))
            return
        if args.command == 'discover':
            print(json.dumps(discovery.inspect_api(args.spec), indent=2))
            return 0
        if args.command == 'interview':
            if not sys.stdin.isatty():
                raise Rejected('Interview requires a terminal; harnesses can render discovery.questions()')
            contract = discovery.interview(args.spec, args.target)
            Path(args.output).write_text(json.dumps(contract, indent=2) + '\n')
            print('Saved connector inputs: ' + args.output)
            return 0
        if args.command == 'build':
            artifact = generation.build_contract(json.loads(Path(args.interview).read_text()),
                                                  Path(args.verifier).read_text())
            Path(args.output).write_text(json.dumps(artifact, indent=2) + '\n')
            print(json.dumps({'connector_digest': runtime.digest(artifact), 'artifact': args.output}))
            return 0
        if args.command == 'github-build':
            artifact = generation.build_github_contract(
                args.repository, args.author, Path(args.verifier).read_text(),
                json.loads(Path(args.interview).read_text()))
            Path(args.output).write_text(json.dumps(artifact, indent=2) + '\n')
            print(json.dumps({'connector_digest': runtime.digest(artifact), 'artifact': args.output}))
            return 0
        if args.command == 'http-build':
            artifact = generation.build_http_contract(json.loads(Path(args.contract).read_text()),
                                                      Path(args.verifier).read_text())
            Path(args.output).write_text(json.dumps(artifact, indent=2) + '\n')
            print(json.dumps({'connector_digest': runtime.digest(artifact), 'artifact': args.output}))
            return 0
        storage.initialize(args.db)
        if args.command == 'init':
            output = {'database': args.db}
        elif args.command == 'register':
            output = {'connector_digest': runtime.register(args.db, json.loads(Path(args.file).read_text()))}
        elif args.command == 'validate':
            output = validation.validate(args.db, args.digest)
            if output['failed']:
                print(json.dumps(output))
                return 1
        elif args.command == 'approve':
            if not sys.stdin.isatty():
                raise Rejected('Approval requires an interactive operator terminal')
            with storage.connect(args.db) as db:
                artifact = runtime.load_connector(db, args.digest)
                record = db.execute('SELECT report,report_digest FROM validations WHERE digest=?', (args.digest,)).fetchone()
            if record is None:
                raise Rejected('Validate before approval')
            print(json.dumps({'connector': artifact, 'validation': json.loads(record['report'])}, indent=2))
            print('Only approve the exact target, observable behavior, and evidence assumptions you reviewed.')
            confirmation = input('Type the full connector digest to approve: ').strip()
            runtime.approve(args.db, args.digest, confirmation, record['report_digest'])
            output = {'approved': args.digest}
        else:
            server = create_server(args.db, args.port, os.environ['CAUSALRUN_AGENT_TOKEN'],
                                   os.environ['CAUSALRUN_PROVIDER_TOKEN'], os.environ.get('CAUSALRUN_RECEIPT_TOKEN'))
            print(json.dumps({'listening': server.server_address}), flush=True)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
            finally:
                server.server_close()
            return
        print(json.dumps(output, indent=2))
    except (Rejected, ValueError, TypeError, KeyError, OSError) as error:
        # This is an operator terminal, never an agent API response.
        print('Error: ' + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
