"""One bounded, non-publishing OODA build cycle. Invoked by CI, not a daemon."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
# Repository name can change after provisioning; derive the module from metadata.
import tomllib
PACKAGE = tomllib.loads((ROOT / 'pyproject.toml').read_text())['project']['name'].removeprefix('govdoss-')


def main():
    started = time.monotonic()
    report = {'schema': 1, 'observe': {'repository': os.getenv('GITHUB_REPOSITORY'),
              'source_sha': os.getenv('GITHUB_SHA'), 'run_id': os.getenv('GITHUB_RUN_ID'),
              'python': sys.version.split()[0]},
              'orient': {'scope': 'offline framework unit, CLI and package validation',
                         'limitations': 'No live identity, customer requests, hosting or evidence-truth verification'},
              'decide': {'budget_seconds': 900, 'allowed_action': 'tests and local package build only',
                         'stop': 'first failed check; review before any source promotion'},
              'act': [], 'verify': {'outcome': 'incomplete'},
              'learn': {'next': 'review evidence in the existing workspace operator',
                        'automatic_source_changes': False}}
    code = 1
    def check(name, command, cwd=ROOT):
        remaining = 900 - (time.monotonic() - started)
        if remaining <= 0:
            raise TimeoutError('Cycle budget exhausted')
        result = subprocess.run(command, cwd=cwd, capture_output=True, text=True,
                                timeout=min(300, remaining))
        report['act'].append({'check': name, 'exit_status': result.returncode,
                              'stdout_tail': result.stdout[-5000:], 'stderr_tail': result.stderr[-5000:]})
        if result.returncode:
            raise RuntimeError('Failed check: ' + name)
    try:
        check('unit-and-cli-tests', [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'])
        with tempfile.TemporaryDirectory(prefix='framework-build-') as tmp:
            out = Path(tmp) / 'dist'
            out.mkdir()
            build_code = 'import setuptools.build_meta as b; import sys; out = sys.argv[1]; b.build_wheel(out); b.build_sdist(out)'
            check('wheel-and-sdist', [sys.executable, '-c', build_code, str(out)])
            wheels = list(out.glob('*.whl'))
            sdists = list(out.glob('*.tar.gz'))
            if len(wheels) != 1 or len(sdists) != 1:
                raise RuntimeError('Expected one wheel and one sdist')
            report['verify']['packages'] = [{'name': p.name, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in wheels + sdists]
            venv = Path(tmp) / 'venv'
            check('isolated-environment', [sys.executable, '-m', 'venv', str(venv)])
            python = str(venv / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python'))
            check('offline-wheel-install', [python, '-m', 'pip', 'install', '--no-index', '--no-deps', str(wheels[0])])
            check('installed-unit-and-cli-tests', [python, '-I', '-m', 'unittest', 'discover', '-s', str(ROOT/'tests'), '-v'])
            smoke = 'import importlib,sys; m=importlib.import_module(sys.argv[1]); assert m.__version__ == "0.1.0"; assert sys.prefix in m.__file__; print(m.__version__)'
            check('installed-package-origin', [python, '-I', '-c', smoke, PACKAGE], cwd=tmp)
        report['verify']['outcome'] = 'passed'
        code = 0
    except (OSError, ValueError, RuntimeError, TimeoutError, subprocess.TimeoutExpired) as error:
        report['verify'].update(outcome='failed', error=str(error))
        report['learn']['next'] = 'Diagnose the failed check; propose a bounded reviewed repair, never alter gates to pass'
    finally:
        report['verify']['elapsed_seconds'] = round(time.monotonic() - started, 3)
        (ROOT/'cycle-result.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps({'outcome': report['verify']['outcome'], 'report': 'cycle-result.json'}))
    return code


if __name__ == '__main__':
    sys.exit(main())
