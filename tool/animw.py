import struct, numpy as np
def write_vbn(bones, path):
    """bones: list of dict(name, parent(-1 root), id, pos(3), rot(3 euler rad), sca(3))"""
    o=bytearray(b'VBN '+struct.pack('>hh',1,2)+struct.pack('>IIIII',len(bones),len(bones),0,0,0))
    for b in bones:
        nm=b['name'].encode()[:63]; o+=nm+b'\0'*(64-len(nm))
        o+=struct.pack('>IiI',0,0x0FFFFFFF if b['parent']<0 else b['parent'],b['id'])
    for b in bones: o+=struct.pack('>9f',*b['pos'],*b['rot'],*b.get('sca',(1,1,1)))
    open(path,'wb').write(o); return len(o)
def write_omo(nodes, nframes, path):
    """nodes: list of dict(id, pos=(F,3) array, rot=(F,4) quat xyzw, sca=(F,3)) per frame"""
    head=bytearray(b'OMO '+struct.pack('>HHI',1,3,0x091E100C)+struct.pack('>HHHH',0,len(nodes),nframes,0)+struct.pack('>III',0,0,0))
    node_tab=bytearray(); t1=bytearray(); keyoff=0; plans=[]
    for n in nodes:
        q=np.array(n['rot'],float); q=np.where(q[:,3:4]<0,-q,q)   # w >= 0 (w is rebuilt as +sqrt)
        chans=[('pos',np.asarray(n['pos'],float)),('rot',q[:,:3]),('sca',np.asarray(n.get('sca',np.ones((nframes,3))),float))]
        flag=0x07000001; plan=[]; my_t1=len(t1); my_key=keyoff
        for kind,v in chans:
            mn=v.min(0); mx=v.max(0); rng=mx-mn; const=(rng<1e-7).all()
            t1.extend(struct.pack('>3f',*mn))
            if kind=='pos': flag|=0x00200000 if const else 0x00080000
            if kind=='rot': flag|=0x00007000 if const else 0x00005000
            if kind=='sca': flag|=0x00000200 if const else 0x00000080
            if not const:
                t1.extend(struct.pack('>3f',*rng)); keyoff+=6
                rr=np.where(rng<1e-12,1,rng)
                plan.append(np.clip(np.round((v-mn)/rr*65535),0,65535).astype('>u2'))
        node_tab.extend(struct.pack('>IIII',flag,n['id'],my_t1,my_key)); plans.append(plan)
    frame_size=keyoff
    keys=bytearray()
    for f in range(nframes):
        for plan in plans:
            for arr in plan: keys.extend(arr[f].tobytes())
    node_off=len(head); inter_off=node_off+len(node_tab); key_off=inter_off+len(t1)
    struct.pack_into('>HHH',head,0x0E,len(nodes),nframes,frame_size)
    struct.pack_into('>III',head,0x14,node_off,inter_off,key_off)
    data=head+node_tab+t1+keys
    open(path,'wb').write(data); return len(data)
def write_mta(entries, nframes, path):
    """entries: list of dict(name, hash, props=[dict(name, frames=(F,4) array)])"""
    o=bytearray(b'MTA4'+struct.pack('>IIIIIIIII',9,nframes,0,nframes-1,60,len(entries),0x38,0,0))
    o+=b'\0'*(0x38-len(o))
    table=len(o); o+=b'\0'*(4*len(entries)); o+=b'\0'*((-len(o))%16)
    for i,e in enumerate(entries):
        pos=len(o); struct.pack_into('>I',o,table+4*i,pos)
        nm=e['name'].encode()+b'\0'
        name_off=pos+0x20; ptab=name_off+len(nm); ptab+=(-ptab)%4
        ent=bytearray(struct.pack('>IiII',name_off,e['hash']-(1<<32) if e['hash']>=1<<31 else e['hash'],len(e['props']),ptab))
        ent+=b'\0'*4+struct.pack('>I',0)+b'\0'*8   # hasPat=0, patOffset (patched), secondName/hash2 = 0
        ent+=nm; ent+=b'\0'*((pos+len(ent))%4 and (4-(pos+len(ent))%4))
        assert pos+len(ent)==ptab
        ent+=b'\0'*(4*len(e['props']))
        while (pos+len(ent))%16: ent+=b'\0'
        for j,p in enumerate(e['props']):
            ppos=pos+len(ent); struct.pack_into('>I',ent,ptab-pos+4*j,ppos)
            fr=np.asarray(p['frames'],'>f4'); pn=p['name'].encode()+b'\0'
            pname_off=ppos+0x20; data_off=pname_off+len(pn); data_off+=(-data_off)%16
            const=len(fr)==1
            pr=bytearray(struct.pack('>IiIIHHI',pname_off,1,fr.shape[1],len(fr),1,2 if const else 1,data_off))+b'\0'*8
            pr+=pn; pr+=b'\0'*(data_off-ppos-len(pr)); pr+=fr.tobytes(); pr+=b'\0'*16
            ent+=pr
            while (pos+len(ent))%16: ent+=b'\0'
        struct.pack_into('>I',ent,0x14,pos+len(ent))
        o+=ent
    open(path,'wb').write(o); return len(o)
