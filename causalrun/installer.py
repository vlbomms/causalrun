"""Install from a self-contained Python zipapp; preserve unrelated OpenCode settings."""
import argparse
import json
import os
import shutil
import sys
import tempfile
import zipfile
import zipapp
from pathlib import Path
from .contracts import Rejected

ROOT = Path(__file__).resolve().parents[1]


def write_private(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', dir=path.parent, delete=False) as stream:
        stream.write(text)
        temporary = stream.name
    os.replace(temporary, path)


def check_skill(source, config):
    source_file = source / 'skills/causalrun/SKILL.md'
    destination = config / 'skills/causalrun/SKILL.md'
    text = source_file.read_text()
    if destination.exists() and '\n  managed-by: causalrun\n' not in destination.read_text():
        raise Rejected('Refusing to overwrite an unrelated causalrun skill')
    return destination, text


def install_skill(source, config):
    destination, text = check_skill(source, config.resolve())
    write_private(destination, text)
    return {'skill': str(destination), 'next': 'Restart OpenCode. The skill requires the causalrun plugin or MCP tools.'}


def install(source, config, state):
    config, state = config.resolve(), state.resolve()
    if config == state or config in state.parents or state in config.parents:
        raise Rejected('Keep OpenCode configuration and private runtime state in separate directories')
    settings_path = config / 'opencode.json'
    # Preserve JSONC as-is rather than attempting to parse/rewrite comments incorrectly.
    if (config / 'opencode.jsonc').exists():
        raise Rejected('JSONC configuration detected; use a separate config directory or merge the plugin and ask permission manually')
    settings = json.loads(settings_path.read_text()) if settings_path.exists() else {}
    permissions = settings.get('permission', {})
    if not isinstance(permissions, dict):
        raise Rejected('Existing permission shorthand cannot be merged safely; use a separate config directory')
    if 'causalrun_approve' in permissions and permissions['causalrun_approve'] != 'ask':
        raise Rejected('Existing causalrun_approve rule must require ask')
    plugin = config / 'plugins/causalrun.ts'
    if plugin.exists() and not plugin.read_text().startswith('// causalrun managed bootstrap\n'):
        raise Rejected('Refusing to overwrite an unrelated causalrun.ts plugin')
    skill, skill_text = check_skill(source, config)
    from .native import running
    if running(state) is not None:
        raise Rejected('Quit OpenCode and stop its runtime with this installer --stop before updating executable files')
    runtime = state / 'runtime'
    state.mkdir(parents=True, exist_ok=True); os.chmod(state, 0o700)
    for folder in ('causalrun', 'examples', 'adapters', 'skills'):
        shutil.copytree(source / folder, runtime / folder, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('__pycache__', '*.sqlite*'))
    # Bootstrap in the host's normal plugin directory; SDK is supplied by OpenCode.
    bootstrap = ('// causalrun managed bootstrap\nimport { tool } from "@opencode-ai/plugin";\n'
                 'import { createPlugin } from ' + json.dumps(str(runtime / 'adapters/opencode/plugin.mjs')) + ';\n'
                 'export default async (ctx) => createPlugin(ctx, tool, ' + json.dumps({
                     'python': sys.executable, 'runtime': str(runtime), 'state': str(state)}) + ');\n')
    permissions['causalrun_approve'] = 'ask'
    settings['permission'] = permissions
    if settings_path.exists() and not (config / 'opencode.json.before-causalrun').exists():
        shutil.copy2(settings_path, config / 'opencode.json.before-causalrun')
    write_private(plugin, bootstrap)
    write_private(skill, skill_text)
    write_private(settings_path, json.dumps(settings, indent=2) + '\n')
    return {'installed': str(plugin), 'skill': str(skill), 'runtime': str(runtime), 'state': str(state),
            'next': 'Restart OpenCode. The plugin starts the service automatically. Use local gh auth login for GitHub; no secrets in chat.'}


def build(destination):
    with tempfile.TemporaryDirectory() as directory:
        staging = Path(directory)
        for folder in ('causalrun', 'examples', 'adapters', 'skills'):
            shutil.copytree(ROOT / folder, staging / folder, ignore=shutil.ignore_patterns('__pycache__', '*.sqlite*'))
        # zipapp's generated entry point discards main()'s status. Preserve it so
        # failed review, MCP startup, and installation are visible to callers.
        (staging / '__main__.py').write_text('from causalrun.installer import main\nraise SystemExit(main())\n')
        zipapp.create_archive(staging, target=destination, interpreter='/usr/bin/env python3')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    config_home = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config')))
    parser.add_argument('--config-dir', default=os.environ.get('OPENCODE_CONFIG_DIR', str(config_home / 'opencode')))
    parser.add_argument('--state-dir', default=str(Path.home() / '.local/share/causalrun'))
    parser.add_argument('--stop', action='store_true', help='Quit OpenCode first; stop only the authenticated local runtime')
    parser.add_argument('--review', metavar='DIGEST', help='Review and approve an exact prepared connector in a trusted terminal')
    parser.add_argument('--mcp', action='store_true', help='Serve MCP tools over stdio using the installed runtime')
    parser.add_argument('--build', help='Developer: build a distributable .pyz')
    parser.add_argument('--json', action='store_true', help='Return machine-readable installation results')
    parser.add_argument('--skill-only', action='store_true', help='Install only the discovery skill; plugin or MCP runtime is still required')
    args = parser.parse_args()
    success_message = ('The causalrun skill is installed.\nRestart OpenCode.\nThe skill requires causalrun tools.' if args.skill_only
                       else 'causalrun is installed.\nOpen a new OpenCode session.\nThe local service starts for you.')
    try:
        if os.name != 'posix' or sys.version_info < (3, 10):
            raise Rejected('This installer supports macOS/Linux with Python 3.10+')
        if args.mcp:
            import subprocess
            return subprocess.call([sys.executable, '-m', 'causalrun.mcp', '--state', str(Path(args.state_dir).resolve())],
                                   cwd=Path(args.state_dir).resolve() / 'runtime')
        elif args.review:
            import subprocess
            return subprocess.call([sys.executable, '-m', 'causalrun.native', 'review',
                                    '--state', str(Path(args.state_dir).resolve()), '--digest', args.review],
                                   cwd=Path(args.state_dir).resolve() / 'runtime')
        elif args.stop:
            from .native import stop
            result = stop(Path(args.state_dir).resolve())
            print(json.dumps(result) if args.json else ('The local service stopped.' if result['stopped'] else 'The local service is not running.'))
        elif args.build:
            build(args.build)
            print(json.dumps({'archive': args.build}))
        elif zipfile.is_zipfile(sys.argv[0]):
            with tempfile.TemporaryDirectory() as directory:
                with zipfile.ZipFile(sys.argv[0]) as archive:
                    # The archive is our own executable payload, not user-supplied connector data.
                    archive.extractall(directory)
                result = (install_skill(Path(directory), Path(args.config_dir)) if args.skill_only
                          else install(Path(directory), Path(args.config_dir), Path(args.state_dir)))
                print(json.dumps(result) if args.json else success_message)
        else:
            result = (install_skill(ROOT, Path(args.config_dir)) if args.skill_only
                      else install(ROOT, Path(args.config_dir), Path(args.state_dir)))
            print(json.dumps(result) if args.json else success_message)
    except (Rejected, OSError, ValueError) as error:
        print('Installation failed: ' + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
