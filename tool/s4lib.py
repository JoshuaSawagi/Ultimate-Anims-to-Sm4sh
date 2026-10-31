"""Smash 4 (Wii U) helpers: VBN skeleton, PAC archive, OMO animation (read + write)."""
import struct, numpy as np
def read_vbn(path):
    d=open(path,'rb').read()
    E='>' if d[:4]==b'VBN ' else '<'
    assert d[:4] in (b'VBN ',b' NBV')
    tot=struct.unpack_from(E+'I',d,8)[0]; o=0x1C; bones=[]
    for i in range(tot):
        name=d[o:o+64].split(b'\0')[0].decode(); bt,pi,bid=struct.unpack_from(E+'IiI',d,o+64); o+=76
        bones.append(dict(name=name,type=bt,parent=pi if pi!=0x0FFFFFFF else -1,id=bid))
    for b in bones:
        v=struct.unpack_from(E+'9f',d,o); o+=36; b['pos']=np.array(v[:3]); b['rot']=np.array(v[3:6]); b['sca']=np.array(v[6:])
    for b in bones:
        if b['parent']==0x0FFFFFFF: b['parent']=-1
    return bones
def read_pac(path):
    d=open(path,'rb').read(); E='<' if d[:4]==b'PACK' else '>'
    n=struct.unpack_from(E+'I',d,8)[0]; out={}
    for i in range(n):
        so=struct.unpack_from(E+'I',d,0x10+4*i)[0]; do=struct.unpack_from(E+'I',d,0x10+4*n+4*i)[0]; sz=struct.unpack_from(E+'I',d,0x10+8*n+4*i)[0]
        name=d[so:d.index(b'\0',so)].decode(); out[name]=d[do:do+sz]
    return out,E
def write_pac(files, path, E='>'):
    names=list(files); n=len(names); hdr=bytearray((b'KCAP' if E=='>' else b'PACK')+b'\0'*4+struct.pack(E+'I',n)+b'\0'*4)
    hdr+=b'\0'*(12*n); strs=[]
    for k in names: strs.append(len(hdr)); hdr+=k.encode()+b'\0'
    data=[]
    for k in names:
        while len(hdr)%16: hdr+=b'\0'
        data.append(len(hdr)); hdr+=files[k]
    for i,k in enumerate(names):
        struct.pack_into(E+'I',hdr,0x10+4*i,strs[i]); struct.pack_into(E+'I',hdr,0x10+4*n+4*i,data[i]); struct.pack_into(E+'I',hdr,0x10+8*n+4*i,len(files[k]))
    open(path,'wb').write(hdr)
S1=1/np.sqrt(2); S2=S1*2/1048575.0
def read_omo(d):
    """returns {hash: dict(pos=(F,3), rot=(F,4 xyzw), sca=(F,3), has=(t,r,s))}, frames"""
    bc,fc,fs,no,io,ko=struct.unpack_from('>HHHIII',d,0x0E)
    out={}
    for i in range(bc):
        flags,tf,rf,sf=d[no+16*i:no+16*i+4]; h,off1,fk=struct.unpack_from('>III',d,no+16*i+4); o=io+off1
        T=np.zeros((fc,3)); R=np.tile([0,0,0,1.],(fc,1)); S=np.ones((fc,3)); ttype=rtype=stype=None
        t=t2=rv=rv2=s=s2=None; rex=0
        if flags&1:
            if tf==0x8: t=np.array(struct.unpack_from('>3f',d,o)); t2=np.array(struct.unpack_from('>3f',d,o+12)); o+=24; ttype='i'
            elif tf==0x20: t=np.array(struct.unpack_from('>3f',d,o)); o+=12; ttype='c'
            elif tf==0x4: ttype='k'
        if flags&2:
            hi=rf&0xF0
            if hi==0xA0: rtype='z'
            elif hi==0x50: rv=np.array(struct.unpack_from('>3f',d,o)); rv2=np.array(struct.unpack_from('>3f',d,o+12)); o+=24; rtype='i'
            elif hi==0x60: rv=np.array(struct.unpack_from('>3f',d,o)); rex=struct.unpack_from('>f',d,o+12)[0]/65535; o+=16; rtype='k'
            elif hi==0x70: rv=np.array(struct.unpack_from('>3f',d,o)); o+=12; rtype='c'
        if flags&4:
            if (sf&0xF0)==0x80: s=np.array(struct.unpack_from('>3f',d,o)); s2=np.array(struct.unpack_from('>3f',d,o+12)); o+=24; stype='i'
            if (rf&0x0F) in (2,3): s=np.array(struct.unpack_from('>3f',d,o)); o+=12; stype='c'
        for f in range(fc):
            p=ko+fs*f+fk
            if ttype=='i': v=np.array(struct.unpack_from('>3H',d,p))/65535.0; p+=6; T[f]=t+t2*v
            elif ttype=='c': T[f]=t
            elif ttype=='k': T[f]=struct.unpack_from('>3f',d,p); p+=12
            if rtype=='z':
                b=d[p:p+8]; p+=8
                f1=(b[0]<<12)|(b[1]<<4)|(b[2]>>4); f2=((b[2]&0xF)<<16)|(b[3]<<8)|b[4]; f3=(b[5]<<12)|(b[6]<<4)|(b[7]>>4); fl=b[7]&0xF
                a,bq,c=[x*S2-S1 for x in (f1,f2,f3)]
                if fl==0: q=[0,a,bq,c]; q[0]=np.sqrt(abs(1-(a*a+bq*bq+c*c)))
                elif fl==1: q=[a,0,bq,c]; q[1]=np.sqrt(abs(1-(a*a+bq*bq+c*c)))
                elif fl==2: q=[a,bq,0,c]; q[2]=np.sqrt(abs(1-(a*a+bq*bq+c*c)))
                else: q=[a,bq,c,np.sqrt(abs(1-(a*a+bq*bq+c*c)))]
                R[f]=q
            elif rtype=='i':
                v=np.array(struct.unpack_from('>3H',d,p))/65535.0; p+=6; x=rv+rv2*v; w=np.sqrt(abs(1-(x*x).sum())); q=np.r_[x,w]; R[f]=q/np.linalg.norm(q)
            elif rtype=='k':
                sc=struct.unpack_from('>H',d,p)[0]*rex; p+=2; x=np.array([rv[0],rv[1],rv[2]+sc]); w=np.sqrt(max(0,1-(x*x).sum())); R[f]=np.r_[x,w]
            elif rtype=='c':
                x=rv; w=np.sqrt(abs(1-(x*x).sum())); q=np.r_[x,w]; R[f]=q/np.linalg.norm(q)
            if stype=='i': v=np.array(struct.unpack_from('>3H',d,p))/65535.0; p+=6; S[f]=s+s2*v
            elif stype=='c': S[f]=s
        out[h]=dict(pos=T,rot=R,sca=S,has=(ttype,rtype,stype))
    return out,fc
