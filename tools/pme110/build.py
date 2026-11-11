#!/usr/bin/env python3
"""Build bridge and migration ZIP from source; no device operations or vendor blobs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[2]
PROPS = dict(line.split('=', 1) for line in (ROOT/'module/module.prop').read_text().splitlines() if '=' in line)
VERSION, CODE = PROPS['version'], int(PROPS['versionCode'])
DEPS = {
    'api.aar': ('https://repo.maven.apache.org/maven2/io/github/libxposed/api/102.0.0/api-102.0.0.aar', '423484a6e1807e7a423c4b88fcd8176d104318259d91791877fed88fe91479d0'),
    'dexkit.aar': ('https://repo.maven.apache.org/maven2/org/luckypray/dexkit/2.3.0/dexkit-2.3.0.aar', '8df532c4126b58490667f71127dc57aef62ccf3578d1d17330f2a1cb8836218e'),
    'kotlin-stdlib.jar': ('https://repo.maven.apache.org/maven2/org/jetbrains/kotlin/kotlin-stdlib/2.2.21/kotlin-stdlib-2.2.21.jar', '6558a3d233da56a20934b32159f9db5f86ed5816ef098f78a2c223dc6abb79dd'),
}


def run(*args):
    subprocess.run([str(a) for a in args], check=True)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build_bridge(args):
    sdk = Path(args.sdk).expanduser()
    android = sdk / 'platforms/android-36/android.jar'
    tools = sdk / 'build-tools/37.0.0'
    if not android.exists():
        raise SystemExit('Install Android SDK platform 36 and build-tools 37.0.0; pass --sdk')
    work = ROOT / 'build/pme110-bridge'
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    deps = ROOT / 'local-inputs'
    deps.mkdir(exist_ok=True)
    for name, (url, sha) in DEPS.items():
        target = deps / name
        if not target.exists():
            urllib.request.urlretrieve(url, target)
        if digest(target) != sha:
            raise SystemExit(f'Dependency hash mismatch: {name}')
    for name in ['api', 'dexkit']:
        with zipfile.ZipFile(deps / f'{name}.aar') as archive:
            (work / f'{name}.jar').write_bytes(archive.read('classes.jar'))
    classes, dex = work / 'classes', work / 'dex'
    classes.mkdir(); dex.mkdir()
    config = work / 'BuildConfig.java'
    config.write_text('package com.tlsu.oshareairdrop; public final class BuildConfig {'
                      'public static final boolean DEBUG=false;'
                      'public static final String APPLICATION_ID="com.tlsu.oshareairdrop";'
                      'public static final String BUILD_TYPE="release";'
                      f'public static final int VERSION_CODE={CODE};'
                      f'public static final String VERSION_NAME="{VERSION}";}}')
    src = ROOT / 'oshare/app/src/main'
    cp = os.pathsep.join(map(str, [android, work/'api.jar', work/'dexkit.jar', deps/'kotlin-stdlib.jar']))
    run('javac', '-source', '17', '-target', '17', '-encoding', 'UTF-8', '-nowarn', '-cp', cp,
        '-d', classes, *sorted((src/'java').rglob('*.java')), config)
    jar = work / 'bridge.jar'
    run('jar', 'cf', jar, '-C', classes, '.')
    run(tools/'d8', '--release', '--min-api', '35', '--lib', android, '--output', dex,
        jar, work/'dexkit.jar', deps/'kotlin-stdlib.jar')
    run(tools/'aapt2', 'compile', '--dir', src/'res', '-o', work/'resources.zip')
    manifest = work/'AndroidManifest.xml'
    manifest.write_text((src/'AndroidManifest.xml').read_text().replace(
        '<manifest ', '<manifest package="com.tlsu.oshareairdrop" ', 1))
    run(tools/'aapt2', 'link', '-I', android, '--manifest', manifest,
        '--min-sdk-version', '35', '--target-sdk-version', '37', '--version-code', CODE,
        '--version-name', VERSION, '-o', work/'resources.apk', work/'resources.zip')
    unsigned = work / 'unsigned.apk'
    shutil.copy2(work/'resources.apk', unsigned)
    with zipfile.ZipFile(unsigned, 'a') as out:
        out.write(dex/'classes.dex', 'classes.dex', compress_type=zipfile.ZIP_DEFLATED)
        for file in sorted((src/'resources').rglob('*')):
            if file.is_file():
                out.write(file, file.relative_to(src/'resources'), compress_type=zipfile.ZIP_DEFLATED)
        with zipfile.ZipFile(deps/'dexkit.aar') as dep:
            for name in dep.namelist():
                if name.startswith('jni/arm64-v8a/') and name.endswith('.so'):
                    out.writestr('lib/'+name.removeprefix('jni/'), dep.read(name), compress_type=zipfile.ZIP_STORED)
    run(tools/'zipalign', '-P', '16', '-f', '4', unsigned, work/'aligned.apk')
    output = ROOT / 'module/companion/OShareAirDrop.apk'
    output.parent.mkdir(exist_ok=True)
    sign = [tools/'apksigner', 'sign', '--v1-signing-enabled', 'false', '--v2-signing-enabled', 'false',
            '--v3-signing-enabled', 'true', '--v4-signing-enabled', 'false', '--ks', args.keystore, '--ks-pass', f'file:{args.password_file}',
            '--ks-key-alias', 'opairdrop', '--out', output]
    if args.lineage:
        sign += ['--lineage', args.lineage, '--rotation-min-sdk-version', '28']
    run(*sign, work/'aligned.apk')
    run(tools/'apksigner', 'verify', '--verbose', '--print-certs', output)
    run(tools/'zipalign', '-c', '-P', '16', '4', output)
    # Stock Android SQLite is used by the narrow, transaction-based installer.
    helper = work/'helper'
    helper.mkdir()
    run('javac', '-source', '17', '-target', '17', '-cp', android, '-d', helper,
        ROOT/'native/OPAirShareLSPosed.java')
    run('jar', 'cf', work/'helper.jar', '-C', helper, '.')
    native = ROOT/'module/payload/native'
    native.mkdir(parents=True, exist_ok=True)
    run(tools/'d8', '--min-api', '35', '--lib', android, '--output', native/'lsposed-setup.jar', work/'helper.jar')
    print(f'Built bridge {VERSION}: {digest(output)}')


def package():
    module = ROOT/'module'
    for required in ['companion/OShareAirDrop.apk', 'kernel/mtk_wonder_bind.ko',
                     'payload/native/lsposed-setup.jar', 'webroot/index.html']:
        if not (module/required).is_file():
            raise SystemExit(f'Missing build output: {required}')
    # Never publish private migration backups, device APKs or vendor binaries.
    for forbidden in ['runtime', 'system', 'product', 'gms']:
        if (module/forbidden).exists():
            raise SystemExit(f'Local vendor/runtime directory must not enter public ZIP: {forbidden}')
    license_dir = module/'licenses'
    license_dir.mkdir(exist_ok=True)
    for name in ['LICENSE', 'LICENSING.md', 'THIRD_PARTY_NOTICES.md']:
        shutil.copy2(ROOT/name, license_dir/name)
    shutil.copytree(ROOT/'LICENSES', license_dir/'LICENSES', dirs_exist_ok=True)
    files = sorted(p for p in module.rglob('*') if p.is_file() and p.name != 'SHA256SUMS' and p.suffix != '.idsig')
    (module/'SHA256SUMS').write_text(''.join(f'{digest(p)}  {p.relative_to(module)}\n' for p in files))
    output = ROOT/f'build/OPAirDrop-PME110-v{VERSION}-migration.zip'
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as out:
        for file in files+[module/'SHA256SUMS']:
            out.write(file, file.relative_to(module))
    (output.with_suffix('.zip.sha256')).write_text(f'{digest(output)}  {output.name}\n')
    url = f'https://github.com/weijuns/OPAirDrop-PME110/releases/download/v{VERSION}/{output.name}'
    (ROOT/'build/update.json').write_text(json.dumps(dict(version=VERSION, versionCode=CODE,
        zipUrl=url, changelog=f'https://github.com/weijuns/OPAirDrop-PME110/releases/download/v{VERSION}/changelog.md'), indent=2)+'\n')
    print(f'Packaged {output.name}: {digest(output)}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['bridge', 'package'])
    parser.add_argument('--sdk', default=os.environ.get('ANDROID_HOME', str(Path.home()/'Library/Android/sdk')))
    parser.add_argument('--keystore', default=os.environ.get('OPAIR_KEYSTORE'))
    parser.add_argument('--password-file', default=os.environ.get('OPAIR_PASSWORD_FILE'))
    parser.add_argument('--lineage', default=os.environ.get('OPAIR_LINEAGE'))
    args = parser.parse_args()
    if args.action == 'bridge':
        if not args.keystore or not args.password_file:
            parser.error('Signing requires --keystore and --password-file; private keys stay outside the repo')
        build_bridge(args)
    else:
        package()
