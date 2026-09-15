"""Host-side exception-aware DEX assignment and primitive/reference category analysis.

Normal, conditional and exception edges are propagated to a fixed point. This checker
reports register initialization and coarse type consistency for the selected methods.
"""
from collections import deque
from pathlib import Path
import struct,json,zipfile
from dexutil import Dex,uleb,sleb,signed

UNDEF='Undefined'
NULL='Zero/null'
INT='Int'
FLOAT='Float'
LONG='Long'
DOUBLE='Double'
BITS='Const32'
WIDE='Const64'
HIGH='WideHigh'
RESULT='ResultUndefined'

def split_types(signature):
    result=[];p=0
    while p<len(signature):
        a=p
        while signature[p]=='[':p+=1
        if signature[p]=='L':p=signature.index(';',p)+1
        else:p+=1
        result.append(signature[a:p])
    return result

def category(t):
    if t in ('Z','B','C','S','I'):return INT
    return {'J':LONG,'D':DOUBLE,'F':FLOAT,'V':RESULT}.get(t,t)

def reference(t):
    return t==NULL or t.startswith(('L','['))

def throws(op):
    return op in (0x1a,0x1b,0x1c,0x1d,0x1e,0x1f,0x20,0x21,0x22,0x23,0x24,0x25,0x26,0x27) or 0x44<=op<=0x78 or op in (0x93,0x94,0x9e,0x9f,0xb3,0xb4,0xbe,0xbf,0xd3,0xd4,0xdb,0xdc,0xfa,0xfb,0xfc,0xfd)

def handlers_for(d,m):
    regs,ni,no,nt,dbg,n=struct.unpack_from('<HHHHII',d.d,m['code'])
    start=(m['code']+16+2*n+3)&~3;hs=start+8*nt
    ranges=[]
    for i in range(nt):
        pc,num,off=struct.unpack_from('<IHH',d.d,start+8*i)
        count,p=sleb(d.d,hs+off);targets=[]
        for _ in range(abs(count)):
            typ,p=uleb(d.d,p);dest,p=uleb(d.d,p);targets.append((d.types[typ],dest))
        if count<=0:
            dest,p=uleb(d.d,p);targets.append(('Ljava/lang/Throwable;',dest))
        ranges.append((pc,pc+num,targets))
    return ranges

def analyze(d,m):
    regs,ni,no,nt,dbg,n=struct.unpack_from('<HHHHII',d.d,m['code'])
    ins={x['pc']:x for x in d.insns(m)};ranges=handlers_for(d,m)
    initial=[frozenset([UNDEF]) for _ in range(regs)]+[frozenset([RESULT])]
    name=m['name'];args=split_types(name.split('(',1)[1].split(')',1)[0]);p=regs-ni
    if not m['flags']&8:initial[p]=frozenset([name.split('->')[0]]);p+=1
    for t in args:
        initial[p]=frozenset([category(t)]);p+=1
        if t in ('J','D'):initial[p]=frozenset([HIGH]);p+=1
    assert p==regs
    states={0:tuple(initial)};q=deque([0]);queued={0};edges=set();checks={};iterations=0
    handler_types={}
    for _,_,hs in ranges:
        for ty,dest in hs:handler_types.setdefault(dest,set()).add(ty)
    def merge(pc,st):
        assert pc in ins and not ins[pc]['payload'],(m['name'],pc)
        old=states.get(pc)
        new=st if old is None else tuple(a|b for a,b in zip(old,st))
        if new!=old:
            states[pc]=new
            if pc not in queued:q.append(pc);queued.add(pc)
    while q:
        pc=q.popleft();queued.remove(pc);iterations+=1
        assert iterations<1000000
        x=ins[pc];op=x['op'];rs=x['regs'];st=list(states[pc]);before=tuple(st)
        def read(r,kind='any'):
            checks.setdefault((pc,r,kind),set()).update(st[r])
        def write(r,value,wide=False):
            st[r]=value if isinstance(value,frozenset) else frozenset([value])
            if wide:st[r+1]=frozenset([HIGH])
        def refread(r):read(r,'reference')
        def valread(r,t):
            if t.startswith(('L','[')):refread(r)
            else:read(r,category(t))
        result=frozenset([RESULT])
        if op==0x00:pass
        elif 0x01<=op<=0x09:
            read(rs[1],'reference' if op>=0x07 else 'any');write(rs[0],st[rs[1]],0x04<=op<=0x06)
        elif op in (0x0a,0x0b,0x0c):
            checks.setdefault((pc,regs,'reference' if op==0x0c else 'result'),set()).update(before[regs])
            write(rs[0],before[regs],op==0x0b)
        elif op==0x0d:write(rs[0],frozenset(handler_types.get(pc,{'Ljava/lang/Throwable;'})))
        elif op in (0x0f,0x10,0x11):read(rs[0],'reference' if op==0x11 else 'any')
        elif op==0x0e:pass
        elif 0x12<=op<=0x19:
            if op==0x12:v=signed(x['units'][0]>>12,4)
            else:v=any(x['units'][1:])
            write(rs[0],NULL if not v else WIDE if op>=0x16 else BITS,op>=0x16)
        elif op in (0x1a,0x1b):write(rs[0],'Ljava/lang/String;')
        elif op==0x1c:write(rs[0],'Ljava/lang/Class;')
        elif op in (0x1d,0x1e):refread(rs[0])
        elif op==0x1f:refread(rs[0]);write(rs[0],d.types[x['ref']])
        elif op==0x20:refread(rs[1]);write(rs[0],INT)
        elif op==0x21:refread(rs[1]);write(rs[0],INT)
        elif op==0x22:write(rs[0],d.types[x['ref']])
        elif op==0x23:read(rs[1],INT);write(rs[0],d.types[x['ref']])
        elif op in (0x24,0x25):
            t=d.types[x['ref']]
            for r in rs:valread(r,t[1:])
            result=frozenset([t])
        elif op in (0x26,0x27):refread(rs[0])
        elif 0x28<=op<=0x2a:pass
        elif op in (0x2b,0x2c):read(rs[0],INT)
        elif 0x2d<=op<=0x31:
            for r in rs[1:]:read(r)
            write(rs[0],INT)
        elif 0x32<=op<=0x3d:
            for r in rs:read(r)
        elif 0x44<=op<=0x51:
            refread(rs[1]);read(rs[2],INT)
            if op<0x4b:
                types=frozenset(category(t[1:]) for t in st[rs[1]] if t.startswith('['))
                t=types or frozenset(['Ljava/lang/Object;' if op==0x46 else LONG if op==0x45 else INT])
                write(rs[0],t,op==0x45)
            else:read(rs[0],'reference' if op==0x4d else 'any')
        elif 0x52<=op<=0x6d:
            t=d.fields[x['ref']].rsplit(':',1)[1]
            if 0x52<=op<=0x58:refread(rs[1]);write(rs[0],category(t),t in ('J','D'))
            elif 0x59<=op<=0x5f:refread(rs[1]);valread(rs[0],t)
            elif 0x60<=op<=0x66:write(rs[0],category(t),t in ('J','D'))
            else:valread(rs[0],t)
        elif op in (0x6e,0x6f,0x70,0x71,0x72,0x74,0x75,0x76,0x77,0x78):
            target=d.methods[x['ref']];params=split_types(target.split('(',1)[1].split(')',1)[0]);arg=0
            if op not in (0x71,0x77):refread(rs[0]);arg+=1
            for t in params:
                valread(rs[arg],t);arg+=2 if t in ('J','D') else 1
            assert arg==len(rs),(pc,target,rs)
            result=frozenset([category(target.split(')',1)[1])])
        elif 0x7b<=op<=0x8f:
            read(rs[1]);t=[INT,INT,LONG,LONG,FLOAT,DOUBLE,LONG,FLOAT,DOUBLE,INT,FLOAT,DOUBLE,INT,LONG,DOUBLE,INT,LONG,FLOAT,INT,INT,INT][op-0x7b]
            write(rs[0],t,t in (LONG,DOUBLE))
        elif 0x90<=op<=0xaf:
            for r in rs[1:]:read(r)
            t=INT if op<=0x9a else LONG if op<=0xa5 else FLOAT if op<=0xaa else DOUBLE
            write(rs[0],t,t in (LONG,DOUBLE))
        elif 0xb0<=op<=0xcf:
            for r in rs:read(r)
            t=INT if op<=0xba else LONG if op<=0xc5 else FLOAT if op<=0xca else DOUBLE
            write(rs[0],t,t in (LONG,DOUBLE))
        elif 0xd0<=op<=0xe2:read(rs[1],INT);write(rs[0],INT)
        else:raise NotImplementedError((m['name'],pc,x))
        st[regs]=result
        if throws(op):
            for a,b,hs in ranges:
                if a<=pc<b:
                    for ty,dest in hs:
                        # Exception edges use PRE-instruction registers, not the success result.
                        es=list(before);es[regs]=frozenset([RESULT]);merge(dest,tuple(es));edges.add((pc,dest,'catch'))
                    break
        if op in (0x0e,0x0f,0x10,0x11,0x27):continue
        if op in (0x28,0x29,0x2a):targets=[x['target']]
        elif 0x32<=op<=0x3d:targets=[pc+x['length'],x['target']]
        elif op in (0x2b,0x2c):
            u=ins[x['target']]['units'];cnt=u[1];b=4 if op==0x2b else 2+2*cnt
            targets=[pc+x['length']]+[pc+signed(u[b+2*i]|u[b+2*i+1]<<16,32) for i in range(cnt)]
        else:targets=[pc+x['length']]
        for dest in targets:merge(dest,tuple(st));edges.add((pc,dest,'normal'))
    errors=[]
    # Only final fixed-point states should be diagnosed; every observed state
    # is accumulated monotonically, so accumulated use categories are equivalent.
    for (pc,r,kind),ts in sorted(checks.items()):
        bad=None
        if UNDEF in ts:bad='read before definite assignment'
        elif RESULT in ts:bad='undefined invoke result'
        elif kind=='reference' and any(not reference(t) for t in ts):bad='non-reference used as reference'
        elif kind==INT and any(t not in (INT,BITS,NULL) for t in ts):bad='non-int used as int'
        elif kind==FLOAT and any(t not in (FLOAT,BITS,NULL) for t in ts):bad='non-float used as float'
        elif kind==LONG and any(t not in (LONG,WIDE,NULL) for t in ts):bad='non-long used as long'
        elif kind==DOUBLE and any(t not in (DOUBLE,WIDE,NULL) for t in ts):bad='non-double used as double'
        if bad:errors.append({'pc':hex(pc),'register':f'v{r}' if r<regs else 'result','expected':kind,'types':sorted(ts),'error':bad,'instruction':ins[pc]['name']+' '+ins[pc]['text']})
    return {'method':m['name'],'reachable_instructions':len(states),'normal_edges':sum(e[2]=='normal' for e in edges),
            'exception_edges':sum(e[2]=='catch' for e in edges),'iterations':iterations,'errors':errors,
            'status':'PASS' if not errors else 'FAIL'},states

