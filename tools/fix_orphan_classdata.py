"""DEX class-data ownership inspection and targeted relocation repair.

Checks the declaring-class relationship for nonempty class-data records and retains
code, ID tables, resources and offsets outside the class-data section.
"""
from pathlib import Path
import struct, json, sys
from dexutil import Dex, uleb

ROOT = Path(__file__).resolve().parents[1]

def scan(data):
    d = Dex(data)
    map_off = struct.unpack_from('<I', data, 52)[0]
    maps = []
    for i in range(struct.unpack_from('<I', data, map_off)[0]):
        entry_off = map_off + 4 + 12*i
        typ, unused, count, off = struct.unpack_from('<HHII', data, entry_off)
        maps.append((typ, count, off, entry_off))
    typ, count, start, map_entry = next(x for x in maps if x[0] == 0x2000)
    records = []
    p = start
    for i in range(count):
        record_start = p
        counts = []
        for j in range(4):
            n, p = uleb(data, p)
            counts.append(n)
        owners = set()
        for j, n in enumerate(counts):
            idx = 0
            for k in range(n):
                delta, p = uleb(data, p)
                flags, p = uleb(data, p)
                idx += delta
                if j >= 2:
                    code, p = uleb(data, p)
                    assert idx < len(d.methods)
                    member = d.methods[idx]
                else:
                    assert idx < len(d.fields)
                    member = d.fields[idx]
                owners.add(member.split('->')[0])
        assert len(owners) <= 1, ('mixed member owners', hex(record_start), owners)
        owner = next(iter(owners), None)
        records.append(dict(start=record_start, end=p, owner=owner, counts=counts,
                            orphan=owner is not None and owner not in d.classes))
    return d, records, (map_entry, start, p)

def describe(data):
    d, records, region = scan(data)
    addresses = {r['start']: r for r in records}
    errors = []
    for c, cl in d.classes.items():
        off = cl['data_off']
        if off:
            if off not in addresses:
                errors.append({'class': c, 'problem': 'class_data_off is not a record start'})
            elif addresses[off]['owner'] not in (None, c):
                errors.append({'class': c, 'problem': 'class_data owner mismatch'})
    orphans = [r for r in records if r['orphan']]
    return {'classes': len(d.classes), 'class_data_items': len(records),
            'orphan_records': orphans, 'class_definition_errors': errors,
            'ownership_check': 'FAIL' if (orphans or errors) else 'PASS'}

def repair(data):
    d, records, (map_entry, start, end) = scan(data)
    orphan = [r for r in records if r['orphan']]
    expected = {'Lcom/suda/yzune/wakeupschedule/SplashActivity;',
                'Lcom/suda/yzune/wakeupschedule/schedule_parser/parser/zf/OooO0O0;'}
    assert {r['owner'] for r in orphan} == expected, orphan
    keep = [r for r in records if not r['orphan']]
    rewritten = bytearray()
    offsets = {}
    for r in keep:
        offsets[r['start']] = start + len(rewritten)
        rewritten.extend(data[r['start']:r['end']])
    d.d[start:end] = rewritten + bytes(end - start - len(rewritten))
    changed_offsets = 0
    for c, cl in d.classes.items():
        old = cl['data_off']
        if old:
            new = offsets[old]
            struct.pack_into('<I', d.d, cl['def_off']+24, new)
            changed_offsets += old != new
    struct.pack_into('<I', d.d, map_entry+4, len(keep))
    fixed = bytes(d.fix())
    fd, fr, (fmap, fs, fe) = scan(fixed)
    assert not any(r['orphan'] for r in fr)
    assert all(x['counts'] == y['counts'] and x['owner'] == y['owner']
               and data[x['start']:x['end']] == fixed[y['start']:y['end']]
               for x,y in zip(keep,fr))
    assert len(fixed) == len(data)
    assert fd.strings == d.strings and fd.types == d.types
    assert fd.fields == d.fields and fd.methods == d.methods
    assert set(fd.classes) == set(d.classes)
    # Every active method still refers to its exact original code_item.
    assert fd.defs == d.defs or all(
        fd.defs[k]['code'] == d.defs[k]['code'] and
        fd.defs[k]['flags'] == d.defs[k]['flags'] for k in d.defs)
    # Allow changes ONLY in checksum/signature, class_data offsets, map count,
    # and the compacted class_data region.
    allowed = [(8,32),(start,end),(map_entry+4,map_entry+8)]
    allowed += [(c['def_off']+24,c['def_off']+28) for c in d.classes.values()]
    mask = bytearray(len(data))
    for a,b in allowed: mask[a:b] = bytes([1])*(b-a)
    for i,(a,b) in enumerate(zip(data,fixed)):
        assert a==b or mask[i], ('unexpected byte change',hex(i))
    assert describe(fixed)['ownership_check']=='PASS'
    # Idempotence: a second scan identifies nothing to remove.
    assert len(fr) == len(keep) and len(fr)==len(records)-2
    return fixed, {'removed_nonempty_orphan_records':orphan,
                   'class_data_items_before':len(records),
                   'class_data_items_after':len(fr),
                   'orphan_bytes_removed':sum(r['end']-r['start'] for r in orphan),
                   'class_data_offsets_updated':changed_offsets,
                   'unchanged_code_and_id_tables':True,
                   'new_zero_padding_bytes':end-fe}

