#!/usr/bin/env python3
"""Build with the running phone's kheaders and recorded import CRCs.

This is a small module-only build, not a replacement kernel. No force loading,
CRC substitution on existing binaries, device operations, or deployment occurs.
"""
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from elftools.elf.elffile import ELFFile
from inspect_elf import Module


def run(args):
    subprocess.run([str(x) for x in args], check=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--headers", required=True, type=Path)
    p.add_argument("--linker-script", required=True, type=Path)
    p.add_argument("--lld", required=True, type=Path)
    inputs = p.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--donor-dir", type=Path)
    inputs.add_argument("--recorded-crcs", type=Path,
                        help="Previously recorded CRC provenance JSON, verified on this kernel")
    p.add_argument("--extra-donor", action="append", default=[], type=Path)
    a = p.parse_args()
    root = Path(__file__).resolve().parent
    out = root / "build"
    out.mkdir(exist_ok=True)
    clang = shutil.which("clang")
    resource = subprocess.check_output([clang, "-print-resource-dir"], text=True).strip()
    includes = ["arch/arm64/include", "arch/arm64/include/generated", "include",
                "arch/arm64/include/uapi", "arch/arm64/include/generated/uapi",
                "include/uapi", "include/generated/uapi"]
    flags = [clang, "-target", "aarch64-linux-gnu", "-nostdinc", "-isystem", resource + "/include"]
    flags += [x for directory in includes for x in ("-I", str(a.headers / directory))]
    flags += ["-include", str(a.headers / "include/linux/kconfig.h"),
              "-include", str(a.headers / "include/linux/compiler_types.h"),
              "-D__KERNEL__", "-DMODULE", '-DKBUILD_MODNAME="mtk_wonder_bind"',
              '-DKBUILD_BASENAME="mtk_wonder_bind"', "-mgeneral-regs-only", "-ffreestanding",
              "-fno-pic", "-fno-stack-protector", "-fsanitize=kcfi",
              "-fsanitize-cfi-icall-experimental-normalize-integers", "-O2", "-Wall", "-Werror"]
    obj = out / "mtk_wonder_bind.o"
    run(flags + ["-c", root / "mtk_wonder_bind.c", "-o", obj])
    with obj.open("rb") as f:
        sym = ELFFile(f).get_section_by_name(".symtab")
        wanted = {s.name for s in sym.iter_symbols() if s["st_shndx"] == "SHN_UNDEF" and s.name}
    wanted.discard("__this_module")
    wanted.add("module_layout")
    crcs = {}
    if a.recorded_crcs:
        recorded = json.loads(a.recorded_crcs.read_text())
        crcs = {name: recorded[name] for name in wanted if name in recorded}
    donors = (sorted(a.donor_dir.glob("*.ko")) if a.donor_dir else []) + a.extra_donor
    for donor in donors:
        # Read only version sections. Full symbol/relocation parsing is unnecessary.
        import struct
        with donor.open("rb") as f:
            e = ELFFile(f)
            versions = e.get_section_by_name("__versions")
            if versions is None:
                continue
            data = versions.data()
        for offset in range(0, len(data), 64):
            name = data[offset + 8:offset + 64].split(b"\0")[0].decode()
            if name not in wanted:
                continue
            crc = struct.unpack_from("<Q", data, offset)[0]
            entry = crcs.setdefault(name, {"crc": crc, "sources": []})
            if entry["crc"] != crc:
                raise ValueError(f"Conflicting CRCs for {name}, refusing build")
            entry["sources"].append(str(donor.resolve()))
    missing = wanted - crcs.keys()
    if missing:
        raise ValueError(f"No recorded CRC for: {sorted(missing)}")

    names = sorted(wanted)
    mod = '''#define INCLUDE_VERMAGIC
#include <linux/module.h>
#include <linux/vermagic.h>
MODULE_INFO(vermagic, VERMAGIC_STRING);
MODULE_INFO(name, KBUILD_MODNAME);
__visible struct module __this_module
__section(".gnu.linkonce.this_module") = {
    .name = KBUILD_MODNAME,
    .init = init_module,
#ifdef CONFIG_MODULE_UNLOAD
    .exit = cleanup_module,
#endif
    .arch = MODULE_ARCH_INIT,
};
static const struct modversion_info versions[] __used
__section("__versions") = {
'''
    mod += "".join(f'    {{ 0x{crcs[n]["crc"]:08x}UL, "{n}" }},\n' for n in names)
    mod += "};\nstatic const u32 version_ext_crcs[] __used __section(\"__version_ext_crcs\") = {\n"
    mod += "".join(f'    0x{crcs[n]["crc"]:08x},\n' for n in names)
    mod += "};\nstatic const char version_ext_names[] __used __section(\"__version_ext_names\") =\n"
    mod += "\n".join('    "' + n + '\\0"' for n in names) + ";\n"
    mod += 'MODULE_INFO(depends, "");\n'
    modsrc = out / "mtk_wonder_bind.mod.c"
    modsrc.write_text(mod)
    modobj = out / "mtk_wonder_bind.mod.o"
    run(flags + ["-c", modsrc, "-o", modobj])
    script = out / "module.lds"
    run(flags + ["-D__ASSEMBLY__", "-E", "-P", "-x", "assembler-with-cpp", a.linker_script, "-o", script])
    ko = out / "mtk_wonder_bind.ko"
    run([a.lld, "-flavor", "gnu", "-r", "-T", script, "--build-id=sha1", "-o", ko, obj, modobj])
    built = Module(ko)
    actual = built.crcs()
    if actual != {n: crcs[n]["crc"] for n in wanted}:
        raise ValueError("Final version records differ from build inputs")
    record = {
        "sha256": hashlib.sha256(ko.read_bytes()).hexdigest(),
        "headers": str(a.headers.resolve()),
        "compiler": subprocess.check_output([clang, "--version"], text=True),
        "flags": [str(x) for x in flags],
        "imports": crcs,
        "source_sha256": hashlib.sha256((root / "mtk_wonder_bind.c").read_bytes()).hexdigest(),
        "status": "built; not proof of device acceptance or successful radio operation",
    }
    (out / "build-record.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({"module": str(ko), "bytes": ko.stat().st_size,
                      "imports": len(wanted), "sha256": record["sha256"]}, indent=2))


if __name__ == "__main__":
    main()
