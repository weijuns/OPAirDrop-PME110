#!/usr/bin/env python3
"""Check actual DEX class definitions, not string references or a warm host cache."""
import argparse
from pathlib import Path
import struct
import zipfile

REQUIRED = {
    'Lcom/tlsu/oshareairdrop/Entry;',
    'Lorg/luckypray/dexkit/DexKitBridge;',
    'Lcom/google/flatbuffers/FlatBufferBuilder;',
    'Lcom/google/flatbuffers/Table;',
    'Lkotlin/jvm/internal/Intrinsics;',
}


def class_definitions(dex):
    if not dex.startswith(b'dex\n') or len(dex) < 112:
        raise ValueError('Invalid DEX header')
    string_count, strings = struct.unpack_from('<II', dex, 56)
    type_count, types = struct.unpack_from('<II', dex, 64)
    count, classes = struct.unpack_from('<II', dex, 96)
    result = set()
    for index in range(count):
        type_index = struct.unpack_from('<I', dex, classes + index*32)[0]
        if type_index >= type_count:
            raise ValueError('Invalid class type index')
        string_index = struct.unpack_from('<I', dex, types + type_index*4)[0]
        if string_index >= string_count:
            raise ValueError('Invalid descriptor string index')
        offset = struct.unpack_from('<I', dex, strings + string_index*4)[0]
        # Skip the ULEB128 UTF-16 length. Class descriptors use ASCII here.
        while dex[offset] & 0x80:
            offset += 1
        offset += 1
        end = dex.index(b'\0', offset)
        result.add(dex[offset:end].decode('ascii'))
    return result


def verify_runtime_apk(path):
    definitions = set()
    with zipfile.ZipFile(path) as apk:
        dex_files = [name for name in apk.namelist() if name.startswith('classes') and name.endswith('.dex')]
        if not dex_files:
            raise ValueError('No DEX files in bridge APK')
        for name in dex_files:
            classes = class_definitions(apk.read(name))
            duplicate = definitions & classes
            if duplicate:
                raise ValueError(f'Duplicate runtime classes: {sorted(duplicate)}')
            definitions.update(classes)
        missing = REQUIRED - definitions
        if missing:
            raise ValueError(f'Missing runtime class definitions: {sorted(missing)}')
        native = apk.getinfo('lib/arm64-v8a/libdexkit.so')
        if native.compress_type != zipfile.ZIP_STORED:
            raise ValueError('DexKit native library must remain uncompressed')
    return len(definitions)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('apk', type=Path)
    args = parser.parse_args()
    print(f'Runtime definitions verified: {verify_runtime_apk(args.apk)} classes')
