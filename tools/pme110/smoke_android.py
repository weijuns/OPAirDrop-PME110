#!/usr/bin/env python3
"""Run uncached DexKit send/receive resolution on the connected phone.

Does not install APKs, start OShare, send files, or change LSPosed configuration.
Requires the source bridge build outputs produced by build.py bridge.
"""
import argparse
import os
from pathlib import Path
import shlex
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def run(*args):
    subprocess.run([str(x) for x in args], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sdk', default=os.environ.get('ANDROID_HOME', str(Path.home()/'Library/Android/sdk')))
    parser.add_argument('--bridge', type=Path, default=ROOT/'module/companion/OShareAirDrop.apk')
    args = parser.parse_args()
    sdk = Path(args.sdk)
    android = sdk/'platforms/android-36/android.jar'
    tools = sdk/'build-tools/37.0.0'
    build = ROOT/'build/pme110-bridge'
    target = subprocess.check_output(['adb', 'shell', '/system/bin/pm path com.coloros.oshare'], text=True)
    paths = [line.removeprefix('package:').strip() for line in target.splitlines() if line.startswith('package:')]
    if len(paths) != 1:
        raise SystemExit('This smoke test expects one OShare code APK')
    remote = f'/data/local/tmp/opairdrop-coldscan-{os.getpid()}'
    with tempfile.TemporaryDirectory(prefix='opairdrop-coldscan-') as folder:
        work = Path(folder)
        (work/'classes').mkdir()
        sources = [ROOT/'oshare/tests'/f'{name}.java' for name in ('OShareDexResolverTest', 'OShareReceiveResolverTest')]
        cp = os.pathsep.join(map(str, [android, build/'bridge.jar', build/'dexkit.jar',
            ROOT/'local-inputs/kotlin-stdlib.jar', ROOT/'local-inputs/flatbuffers.jar']))
        run('javac', '-source', '17', '-target', '17', '-cp', cp, '-d', work/'classes', *sources)
        run('jar', 'cf', work/'tests.jar', '-C', work/'classes', '.')
        run(tools/'d8', '--min-api', '35', '--lib', android, '--output', work/'test.jar', work/'tests.jar')
        run('adb', 'shell', 'mkdir', '-p', remote)
        try:
            run('adb', 'push', args.bridge, remote+'/bridge.apk')
            run('adb', 'push', work/'test.jar', remote+'/test.jar')
            for name, marker in [('OShareDexResolverTest', 'OSHARE_DEX_RESOLVER_PASSED'),
                                 ('OShareReceiveResolverTest', 'OSHARE_RECEIVE_DEX_RESOLVER_PASSED')]:
                command = (f'CLASSPATH={remote}/bridge.apk:{remote}/test.jar /system/bin/app_process /system/bin '
                           f'com.tlsu.oshareairdrop.{name} {remote}/bridge.apk {shlex.quote(paths[0])} scan')
                result = subprocess.run(['adb', 'shell', 'su -c '+shlex.quote(command)],
                    capture_output=True, text=True, errors='replace', timeout=60)
                print(result.stdout, end='')
                print(result.stderr, end='')
                result.check_returncode()
                if marker not in result.stdout:
                    raise RuntimeError('Missing actual Android execution marker: '+marker)
        finally:
            run('adb', 'shell', 'rm', '-rf', remote)


if __name__ == '__main__':
    main()
