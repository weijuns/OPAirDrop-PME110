#!/usr/bin/env python3
"""Read-only AArch64 module inspection; requires pyelftools and capstone."""
import argparse
import hashlib
import json
import struct
from pathlib import Path

from capstone import CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN, Cs
from elftools.elf.elffile import ELFFile


class Module:
    def __init__(self, path):
        self.path = Path(path)
        self.file = self.path.open("rb")
        self.elf = ELFFile(self.file)
        self.symtab = self.elf.get_section_by_name(".symtab")
        self.symbols = list(self.symtab.iter_symbols())
        self.named = {s.name: s for s in self.symbols if s.name}
        self.relocs = {}
        for section in self.elf.iter_sections():
            if section["sh_type"] != "SHT_RELA":
                continue
            for r in section.iter_relocations():
                symbol = self.symtab.get_symbol(r["r_info_sym"])
                self.relocs[(section["sh_info"], r["r_offset"])] = (
                    symbol, r["r_addend"]
                )

    def resolve(self, symbol, addend):
        index = symbol["st_shndx"]
        if not isinstance(index, int):
            return symbol.name
        offset = symbol["st_value"] + addend
        section = self.elf.get_section(index)
        exact = [s.name for s in self.symbols
                 if s["st_shndx"] == index and s["st_value"] == offset
                 and s.name and not s.name.startswith("$")]
        name = "/".join(exact) or f"{section.name}+{offset:#x}"
        if section.name.startswith(".rodata"):
            raw = section.data()[offset:offset + 160].split(b"\0")[0]
            if raw and all(32 <= c < 127 or c in (9, 10, 13) for c in raw):
                name += " " + repr(raw.decode())
        return name

    def body(self, name):
        s = self.named[name]
        section = self.elf.get_section(s["st_shndx"])
        return s, section.data()[s["st_value"]:s["st_value"] + s["st_size"]]

    def disassemble(self, name):
        s, body = self.body(name)
        lines = [f"{name}: section_offset={s['st_value']:#x} size={len(body)}"]
        for ins in Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN).disasm(body, s["st_value"]):
            annotation = self.relocs.get((s["st_shndx"], ins.address))
            comment = " ; " + self.resolve(*annotation) if annotation else ""
            lines.append(f"{ins.address - s['st_value']:04x}  {ins.mnemonic:8} {ins.op_str}{comment}")
        return "\n".join(lines) + "\n"

    def calls(self, name):
        s, body = self.body(name)
        return [self.resolve(*self.relocs[(s["st_shndx"], ins.address)])
                for ins in Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN).disasm(body, s["st_value"])
                if ins.mnemonic in ("bl", "b") and (s["st_shndx"], ins.address) in self.relocs]

    def crcs(self):
        section = self.elf.get_section_by_name("__versions")
        if section is None:
            return {}
        data = section.data()
        if len(data) % 64:
            raise ValueError("Unexpected basic modversion record size")
        return {data[p+8:p+64].split(b"\0")[0].decode(): struct.unpack_from("<Q", data, p)[0]
                for p in range(0, len(data), 64)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("module", type=Path)
    p.add_argument("functions", nargs="*")
    p.add_argument("--out", type=Path)
    p.add_argument("--calls", action="store_true")
    p.add_argument("--crcs", action="store_true")
    a = p.parse_args()
    m = Module(a.module)
    if a.out:
        a.out.mkdir(parents=True, exist_ok=True)
        manifest = {"source": str(a.module.resolve()), "sha256": hashlib.sha256(a.module.read_bytes()).hexdigest()}
        (a.out / "input.json").write_text(json.dumps(manifest, indent=2) + "\n")
    if a.crcs:
        result = "\n".join(f"0x{v:08x}\t{k}" for k, v in sorted(m.crcs().items())) + "\n"
        if a.out:
            (a.out / "imported-symbol-crcs.tsv").write_text(result)
        else:
            print(result, end="")
    for name in a.functions:
        if a.calls:
            print(name + ": " + ", ".join(m.calls(name)))
        else:
            result = m.disassemble(name)
            if a.out:
                (a.out / (name + ".asm")).write_text(result)
            else:
                print(result)


if __name__ == "__main__":
    main()
