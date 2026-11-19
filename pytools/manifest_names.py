import struct, sys

# Dump asset (TypeId, InstanceId, Name) from a KW v5 manifest (little-endian / not big-endian).
GAMEOBJECT_TYPEID = 0x942fff2d

def parse(path, filt=None):
    d = open(path, "rb").read()
    is_be = d[0]; is_linked = d[1]
    version = struct.unpack_from("<H", d, 2)[0]
    (stream_cs, all_types, asset_count, tot_inst, max_inst, max_relo, max_imp,
     asset_ref_sz, ref_man_sz, asset_name_sz, src_name_sz) = struct.unpack_from("<11I", d, 4)
    print(f"version={version} linked={is_linked} assets={asset_count} "
          f"assetNameBufSize={asset_name_sz}")
    entries_off = 48
    ESIZE = 44
    asset_ref_off = entries_off + asset_count * ESIZE
    ref_man_off = asset_ref_off + asset_ref_sz
    name_off = ref_man_off + ref_man_sz          # AssetNameBuffer start
    results = []
    for i in range(asset_count):
        base = entries_off + i * ESIZE
        type_id, inst_id, type_hash, inst_hash = struct.unpack_from("<4I", d, base)
        name_offset = struct.unpack_from("<i", d, base + 24)[0]  # NameOffset (7th field)
        # read null-terminated name from AssetNameBuffer
        p = name_off + name_offset
        end = d.find(b"\x00", p)
        name = d[p:end].decode("latin1", "replace") if end > p else ""
        results.append((type_id, inst_id, name))
    for type_id, inst_id, name in results:
        if filt is None or filt.lower() in name.lower():
            tag = "GameObject" if type_id == GAMEOBJECT_TYPEID else f"{type_id:08x}"
            print(f"  {tag}  inst={inst_id:08x}  {name}")

if __name__ == "__main__":
    parse(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
