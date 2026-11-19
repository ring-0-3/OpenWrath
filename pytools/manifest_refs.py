import struct, sys

# For a named asset in a KW v5 manifest, dump the NAMES of the assets it references
# (optionally filtered). Lets us see e.g. what ConYard a deploy-beacon creates.
def load(path):
    d = open(path, "rb").read()
    (stream_cs, all_types, asset_count, tot_inst, max_inst, max_relo, max_imp,
     asset_ref_sz, ref_man_sz, asset_name_sz, src_name_sz) = struct.unpack_from("<11I", d, 4)
    ESIZE = 44; entries_off = 48
    asset_ref_off = entries_off + asset_count * ESIZE
    ref_man_off = asset_ref_off + asset_ref_sz
    name_off = ref_man_off + ref_man_sz
    assets = []          # (type_id, inst_id, name, refOffset, refCount)
    by_inst = {}
    for i in range(asset_count):
        b = entries_off + i * ESIZE
        type_id, inst_id, type_hash, inst_hash = struct.unpack_from("<4I", d, b)
        ref_o, ref_c = struct.unpack_from("<2i", d, b + 16)
        name_o = struct.unpack_from("<i", d, b + 24)[0]
        p = name_off + name_o; e = d.find(b"\x00", p)
        name = d[p:e].decode("latin1", "replace")
        assets.append((type_id, inst_id, name, ref_o, ref_c))
        by_inst[inst_id] = name
    return d, asset_ref_off, assets, by_inst

def dump_refs(path, needle, filt=None):
    d, asset_ref_off, assets, by_inst = load(path)
    for type_id, inst_id, name, ref_o, ref_c in assets:
        if needle.lower() in name.lower():
            print(f"=== {name} (refs {ref_c}) ===")
            for k in range(ref_c):
                rp = asset_ref_off + ref_o + k * 8
                rtype, rinst = struct.unpack_from("<2I", d, rp)
                rname = by_inst.get(rinst, f"<{rinst:08x}>")
                if filt is None or filt.lower() in rname.lower():
                    print(f"    -> {rname}")

if __name__ == "__main__":
    dump_refs(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
