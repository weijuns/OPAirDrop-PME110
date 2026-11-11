#!/usr/bin/env python3
"""Reject missing runtime definitions even when DEX references name the class."""
import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('check_runtime', ROOT/'tools/pme110/check_runtime.py')
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)


def dex_fixture(defined, referenced=()):
    names = sorted(set(defined) | set(referenced))
    strings, types, classes = 112, 112 + len(names)*4, 112 + len(names)*8
    data = classes + len(defined)*32
    result = bytearray(data)
    result[:8] = b'dex\n035\0'
    struct.pack_into('<II', result, 56, len(names), strings)
    struct.pack_into('<II', result, 64, len(names), types)
    struct.pack_into('<II', result, 96, len(defined), classes)
    for index, name in enumerate(names):
        struct.pack_into('<I', result, strings + index*4, len(result))
        struct.pack_into('<I', result, types + index*4, index)
        encoded = name.encode('ascii')
        assert len(encoded) < 128
        result.extend(bytes([len(encoded)]) + encoded + b'\0')
    for index, name in enumerate(sorted(defined)):
        struct.pack_into('<I', result, classes + index*32, names.index(name))
    return bytes(result)


class RuntimeApkTests(unittest.TestCase):
    def apk(self, dex, second=None):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = Path(folder.name)/'bridge.apk'
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('classes.dex', dex)
            if second is not None:
                archive.writestr('classes2.dex', second)
            archive.writestr('lib/arm64-v8a/libdexkit.so', b'fixture', compress_type=zipfile.ZIP_STORED)
        return path

    def test_complete_runtime_passes(self):
        path = self.apk(dex_fixture(runtime.REQUIRED))
        self.assertEqual(runtime.verify_runtime_apk(path), len(runtime.REQUIRED))

    def test_references_cannot_replace_missing_definitions(self):
        flat = {name for name in runtime.REQUIRED if 'flatbuffers' in name}
        path = self.apk(dex_fixture(runtime.REQUIRED - flat, referenced=flat))
        with self.assertRaisesRegex(ValueError, 'Missing runtime class definitions.*FlatBufferBuilder'):
            runtime.verify_runtime_apk(path)

    def test_duplicate_dex_definitions_fail(self):
        dex = dex_fixture(runtime.REQUIRED)
        with self.assertRaisesRegex(ValueError, 'Duplicate runtime classes'):
            runtime.verify_runtime_apk(self.apk(dex, dex))


if __name__ == '__main__':
    unittest.main(verbosity=2)
