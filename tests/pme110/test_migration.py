#!/usr/bin/env python3
"""Exercise the real installer in an isolated filesystem; never invokes adb/root."""
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.mod = self.root/'package'
        shutil.copytree(ROOT/'module', self.mod)
        (self.mod/'system/product').mkdir(parents=True, exist_ok=True)
        (self.mod/'system/product/product').symlink_to('./system/product')
        # Relocate every absolute device path before running any shell code.
        for file in self.mod.rglob('*'):
            if file.suffix in ('.sh', '.txt'):
                file.write_text(file.read_text().replace('/data/', str(self.root)+'/data/')
                                .replace('/my_product/', str(self.root)+'/my_product/')
                                .replace('/system/bin/pm ', 'pm ')
                                .replace('/system/bin/dumpsys ', 'dumpsys '))
        old = self.root/'data/adb/modules'
        for name in ['com.fei_ke.unlockcngms', 'mosey_pme110', 'mosey_stack_pme110']:
            (old/name).mkdir(parents=True)
            (old/name/'module.prop').write_text(f'id={name}\n')
        (old/'mosey_stack_pme110/uninstall.sh').write_text('# obsolete global cleanup\nexit 99\n')
        app = old/'mosey_pme110/product/priv-app/MoseyApp'
        app.mkdir(parents=True)
        (old/'mosey_pme110/product/product').symlink_to('./system/product')
        for rel in ['etc/permissions/privapp-permissions-mosey-vivo.xml',
                    'etc/permissions/mosey-hiddenapi-vivo.xml', 'etc/vintf/manifest/manifest_mosey.xml']:
            config = old/'mosey_pme110/product'/rel
            config.parent.mkdir(parents=True, exist_ok=True)
            config.write_text('<fixture/>')
        inputs = {
            'ac3b59b776570aa673aed462bd7dbb08cc1486adea5f5f884f848230ddf6a4be': app/'base.apk',
            'cd2213488b5fa107966755c3dfcb435c85a06d94549c7965a83d5bca5932b49c': app/'split_config.arm64_v8a.apk',
            '1170711ad580850869de8e52934b2331abb3ab6fd08dceb84ac986c0daf93b5f': app/'split_config.en.apk',
            'a1a1f058353547ec199888124e58bbc1821a0634076effe82937a6c06a59babd': app/'split_config.xxhdpi.apk',
            'c56a69c00500d3bf91063560e2452b4d6e216ff63b659831b3cae2f01e75d827': self.root/'data/moapp/mosey_server',
            'ec8f58c686046788bacb628793c83c28f7659e524cf23afaf5511bf32af5447a': self.root/'data/moapp/lib64/libmosey_daemon_ffi.so',
        }
        for original, path in inputs.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f'fixture {path.name}')
            for name in ['customize.sh', 'bin/common.sh']:
                file = self.mod/name
                file.write_text(file.read_text().replace(original, sha(path)))
        self.original_bridge = self.root/'bridge.apk'
        self.original_bridge.write_bytes(b'existing bridge')
        db = self.root/'data/adb/lspd/config/modules_config.db'
        db.parent.mkdir(parents=True)
        db.touch()
        config = self.root/'data/adb/hybrid-mount/config.toml'
        config.parent.mkdir(parents=True)
        config.write_text('[global]\n')
        xml = self.root/'my_product/etc/permissions/oplus_google_cn_gms_features.xml'
        xml.parent.mkdir(parents=True)
        xml.write_text('<permissions><feature name="cn.google.services"/><feature name="keep.me"/></permissions>')
        (self.mod/'bin/gms-paths.txt').write_text(str(xml)+'\n')
        self.environment = os.environ | dict(MODPATH=str(self.mod), BOOTMODE='true',
            TEST_MODEL='PME110', TEST_KERNEL='6.12.69-android16-6-g242e1a07f878-ab15865446-4k')
        self.wrapper = self.root/'run.sh'
        self.wrapper.write_text('''#!/bin/sh
ui_print() { echo "$@"; }
abort() { echo "ABORT: $*"; exit 1; }
set_perm() { :; }
set_perm_recursive() { :; }
getprop() { case "$1" in ro.product.model) echo "$TEST_MODEL";; ro.board.platform) echo mt6993;; esac; }
uname() { echo "$TEST_KERNEL"; }
pm() { [ "$1" = path ] || exit 99; echo "package:$TEST_BRIDGE"; }
dumpsys() { echo 'versionCode=27391 minSdk=36'; }
. "$MODPATH/customize.sh"
''')
        self.environment['TEST_BRIDGE'] = str(self.original_bridge)
        self.refresh_sums()

    def tearDown(self):
        self.temp.cleanup()

    def refresh_sums(self):
        files = sorted(p for p in self.mod.rglob('*') if p.is_file() and p.name != 'SHA256SUMS')
        (self.mod/'SHA256SUMS').write_text(''.join(f'{sha(p)}  {p.relative_to(self.mod)}\n' for p in files))

    def run_installer(self):
        return subprocess.run(['sh', str(self.wrapper)], env=self.environment, text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    def assert_old_untouched(self):
        old = self.root/'data/adb/modules'
        for id in ['com.fei_ke.unlockcngms', 'mosey_pme110', 'mosey_stack_pme110']:
            self.assertFalse((old/id/'remove').exists())
            self.assertFalse((old/id/'disable').exists())

    def test_complete_import_and_backup_before_retirement(self):
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stdout)
        state = self.root/'data/adb/opairshare_pme110'
        backup = Path((state/'latest-backup').read_text().strip())
        self.assertEqual((backup/'bridge.apk').read_bytes(), b'existing bridge')
        self.assertTrue((backup/'mosey_stack_pme110/uninstall.sh').is_file())
        self.assertFalse((self.root/'data/adb/modules/mosey_stack_pme110/uninstall.sh').exists())
        self.assertTrue((self.root/'data/adb/modules/mosey_stack_pme110/uninstall.sh.pre-unify').exists())
        for id in ['com.fei_ke.unlockcngms', 'mosey_pme110', 'mosey_stack_pme110']:
            self.assertTrue((backup/id/'module.prop').exists())
            self.assertTrue((self.root/'data/adb/modules'/id/'remove').exists())
        imported = self.mod/'gms'/str(self.root).lstrip('/')/'my_product/etc/permissions/oplus_google_cn_gms_features.xml'
        self.assertIn('keep.me', imported.read_text())
        self.assertNotIn('cn.google.services', imported.read_text())
        self.assertTrue((self.mod/'system/product/priv-app/MoseyApp/base.apk').exists())
        self.assertFalse((self.mod/'system/product/product').is_symlink())

    def test_reinstall_preserves_first_clean_backup(self):
        first = self.run_installer()
        self.assertEqual(first.returncode, 0, first.stdout)
        state = self.root/'data/adb/opairshare_pme110'
        backup = (state/'latest-backup').read_text()
        second = self.run_installer()
        self.assertEqual(second.returncode, 0, second.stdout)
        self.assertEqual((state/'latest-backup').read_text(), backup)
        self.assertTrue((Path(backup.strip())/'mosey_stack_pme110/uninstall.sh').is_file())

    def test_wrong_kernel_never_retires_old_modules(self):
        self.environment['TEST_KERNEL'] = 'different-kernel'
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assert_old_untouched()

    def test_wrong_daemon_never_retires_old_modules(self):
        (self.root/'data/moapp/mosey_server').write_text('unverified replacement')
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assert_old_untouched()

    def test_package_tampering_never_retires_old_modules(self):
        (self.mod/'module.prop').write_text('tampered')
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assert_old_untouched()

    def test_hash_constants_are_complete_sha256(self):
        text = (ROOT/'module/customize.sh').read_text()
        for value in re.findall(r'check_hash "[^"\n]+" ([a-f0-9]+)', text):
            self.assertEqual(len(value), 64)


if __name__ == '__main__':
    unittest.main(verbosity=2)
