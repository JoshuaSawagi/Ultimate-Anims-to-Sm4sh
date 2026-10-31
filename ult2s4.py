#!/usr/bin/env python3
"""ult2s4.py - port Smash Ultimate animations back to Smash 4 (the reverse of JoshuaSawagi's S4-Anims-to-Ult).

Input : Ultimate animations exported from StudioSB as Maya .anim (one file per animation, all bones),
        the Smash 4 character's model.vbn, and the character's Smash 4 motion .pac files (main, lhand, rhand, swing pacs).
Output: copies of the .pac files with the chosen animations replaced by converted .omo files (ready to put in the
        workspace), plus the loose .omo files.

What it does per animation:
  * renames Ultimate bones to Smash 4 names (reverse of the S4->Ult tool's table, + Peach/Daisy extras);
  * removes Ultimate's extra ClavicleC / LegC bones by folding their transform into the shoulder / leg bones
    (Smash 4 LShoulderN = ClavicleC * ClavicleL, LLegJ = LegC * LegL);
  * takes key frames 1..N (StudioSB's endTime is N+1), the same frame count Smash 4 uses for the same move;
  * writes each .pac's .omo with exactly the bones that .pac's stock .omo animates (body -> main.pac,
    fingers -> lhand/rhand.pac, swing bones -> the character's swing pacs);
  * bones whose Ultimate rig differs from Smash 4 (e.g. Peach/Daisy skirt) get Ultimate's rotations on Smash 4's
    own bone lengths (approximate); face bones are skipped (Smash 4 body animations don't key them).
Rotations: .anim euler radians, R = Rz*Ry*Rx (checked against stock Smash 4 Peach animations).

usage: python ult2s4.py --vbn model.vbn --pacs <dir with main.pac etc> --out <dir> \
          --prefix FitPeachBody a00wait1.anim[=A00Wait1] a02run.anim ...

Single-file version: needs only Python 3 + numpy (pip install numpy).
"""
import sys, os, re, struct, argparse, numpy as np

# ---------------- Smash 4 formats: VBN skeleton, PAC archive, OMO reader ----------------
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

# ---------------- Maya .anim reader (StudioSB / Smash Forge export) ----------------
def read_anim(path):
    t=open(path).read()
    start=float(re.search(r'startTime ([\d.\-]+);',t).group(1)); end=float(re.search(r'endTime ([\d.\-]+);',t).group(1))
    ang=re.search(r'angularUnit (\w+);',t).group(1)
    out={}; order=[]
    for m in re.finditer(r'anim (\S+) (\S+) (\S+) \d+ \d+ \d+;\s*\n(?:animData \{(.*?)\n\})?',t,re.S):
        attr=m.group(2); bone=m.group(3); body=m.group(4)
        if bone not in out: out[bone]={}; order.append(bone)
        if not body: continue
        km=re.search(r'keys \{(.*?)\}',body,re.S)
        fr=[];va=[]
        for line in km.group(1).strip().split('\n'):
            p=line.split()
            if len(p)>=2: fr.append(float(p[0])); va.append(float(p[1]))
        v=np.array(va)
        if attr.startswith('rotate') and ang=='deg': v=np.radians(v)
        out[bone][attr]=(np.array(fr),v)
    return out,order,start,end
def sample(track, frames, default):
    if track is None: return np.full(len(frames),default)
    fr,va=track
    if len(fr)==1: return np.full(len(frames),va[0])
    return np.interp(frames,fr,va)

# ---------------- OMO writer (Forge layout, 16-bit interpolated channels) ----------------
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

# ---------------- bone table: (Smash 4 name, Ultimate name), from S4-Anims-to-Ult ----------------
S4_TO_ULT=[('TransN', 'Trans'),('RotN', 'Rot'),('RotN', 'Rot'),('HipN', 'Hip'),('HLP_HaraJb', 'H_Waist'),
  ('ThrowN', 'Throw'),('HLP_LLegJc', 'LegL2'),('HLP_RLegJc', 'LegR2'),('LLegJb', 'H_LegL1'),('RLegJb', 'H_LegR1'),
  ('LLegJ', 'LegL'),('LKneeJ', 'KneeL'),('LFootJ', 'FootL'),('LFootJ2', 'FootL2'),('LToeN', 'ToeL'),
  ('LToe1stN', 'ToeL2'),('LToe2ndN', 'ToeL3'),('LToe3rdN', 'ToeL4'),('HLP_LComaneciJb', 'H_LegL'),
  ('HLP_LKneeJb', 'H_KneeL'),('RLegJ', 'LegR'),('RKneeJ', 'KneeR'),('RFootJ', 'FootR'),('RFootJ2', 'FootR2'),
  ('RToeN', 'ToeR'),('RToe1stN', 'ToeR2'),('RToe2ndN', 'ToeR3'),('RToe3rdN', 'ToeR4'),('HLP_RComaneciJb', 'H_LegR'),
  ('HLP_RKneeJb', 'H_KneeR'),('WaistN', 'Waist'),('BustN', 'Bust'),('LShoulderN', 'ClavicleL'),
  ('LShoulderJ', 'ShoulderL'),('LArmJ', 'ArmL'),('LHandN', 'HandL'),('HLP_LElbowJb', 'H_ElbowL'),
  ('HLP_LTekubiJb', 'H_WristL'),('HLP_LArmTwistjb', 'H_ArmtwistL'),('HLP_LSholJb', 'H_SholderL'),
  ('LFingerBaseN', 'FingerL10'),('LThumb1N', 'FingerL51'),('LThumb2N', 'FingerL52'),('LThumb3N', 'FingerL53'),
  ('LThumbNa', 'FingerL51'),('LThumbNb', 'FingerL52'),('LIndex1N', 'FingerL11'),('LIndex2N', 'FingerL12'),
  ('LIndex3N', 'FingerL13'),('L1stNa', 'FingerL11'),('L1stNb', 'FingerL12'),('LMiddleN', 'FingerL20'),
  ('LMiddle1N', 'FingerL21'),('LMiddle2N', 'FingerL22'),('LMiddle3N', 'FingerL23'),('L2ndNa', 'FingerL21'),
  ('L2ndNb', 'FingerL22'),('LRingN', 'FingerL30'),('LRing1N', 'FingerL31'),('LRing2N', 'FingerL32'),
  ('LRing3N', 'FingerL33'),('L3rdNa', 'FingerL31'),('L3rdNb', 'FingerL32'),('LPinkyN', 'FingerL40'),
  ('LPinky1N', 'FingerL41'),('LPinky2N', 'FingerL42'),('LPinky3N', 'FingerL43'),('L4thNa', 'FingerL41'),
  ('L4thNb', 'FingerL42'),('RShoulderN', 'ClavicleR'),('RShoulderJ', 'ShoulderR'),('RArmJ', 'ArmR'),
  ('RHandN', 'HandR'),('HLP_RElbowJb', 'H_ElbowR'),('HLP_RTekubiJb', 'H_WristR'),('HLP_RArmTwistJb', 'H_ArmtwistR'),
  ('HLP_RSholJb', 'H_SholderR'),('RFingerBaseN', 'FingerR10'),('RThumb1N', 'FingerR51'),('RThumb2N', 'FingerR52'),
  ('RThumb3N', 'FingerR53'),('RThumbNa', 'FingerR51'),('RThumbNb', 'FingerR52'),('RIndex1N', 'FingerR11'),
  ('RIndex2N', 'FingerR12'),('RIndex3N', 'FingerR13'),('R1stNa', 'FingerR11'),('R1stNb', 'FingerR12'),
  ('RMiddleN', 'FingerR20'),('RMiddle1N', 'FingerR21'),('RMiddle2N', 'FingerR22'),('RMiddle3N', 'FingerR23'),
  ('R2ndNa', 'FingerR21'),('R2ndNb', 'FingerR22'),('RRingN', 'FingerR30'),('RRing1N', 'FingerR31'),
  ('RRing2N', 'FingerR32'),('RRing3N', 'FingerR33'),('R3rdNa', 'FingerR31'),('R3rdNb', 'FingerR32'),
  ('RPinkyN', 'FingerR40'),('RPinky1N', 'FingerR41'),('RPinky2N', 'FingerR42'),('RPinky3N', 'FingerR43'),
  ('R4thNa', 'FingerR41'),('R4thNb', 'FingerR42'),('FaceN', 'Face'),('FaceLEyebrowInnerN', 'BrowL1_offset'),
  ('FaceLEyebrowMidN', 'BrowL2_offset'),('FaceLEyebrowOuterN', 'BrowL3_offset'),
  ('FaceREyebrowInnerN', 'BrowR1_offset'),('FaceREyebrowMidN', 'BrowR2_offset'),
  ('FaceREyebrowOuterN', 'BrowR3_offset'),('Mouth3N', 'Mouth2'),('Mouth4N', 'Mouth1'),('HairN', 'Hair'),
  ('LHornN', 'HornL'),('RHornN', 'HornR'),('NoseN', 'Snout'),('FaceCLipUpperN', 'UplipC_offset'),
  ('FaceLLipUpperN', 'UplipL1_offset'),('FaceLLipCornerN', 'UplipL2_offset'),('FaceRLipUpperN', 'UplipR1_offset'),
  ('FaceRLipCornerN', 'UplipR2_offset'),('FaceJawN', 'Jaw_offset'),('FaceCLipLowerN', 'DownlipC_offset'),
  ('FaceLLipLowerN', 'DownlipL_offset'),('FaceRLipLowerN', 'DownlipR_offset'),('FaceTongueN', 'Tongue_offset'),
  ('HLP_LSakotsuJb', 'H_ClavicleL'),('HLP_RSakotsuJb', 'H_ClavicleR'),('HLP_LComaneciJb', 'H_LegL'),
  ('HLP_LComaneciJc', 'H_LegL'),('HLP_LComaneciJc1', 'H_LegL2'),('HLP_RComaneciJb', 'H_LegR'),
  ('HLP_RComaneciJc', 'H_LegR'),('SWG_Scarf0__swing', 'S_Scarf1'),('SWG_Scarf1__swing', 'S_Scarf2'),
  ('SWG_Scarf2__swing', 'S_Scarf3'),('SWG_cap1__swing', 'S_Hat1'),('SWG_cap2__swing', 'S_Hat2'),
  ('SWG_sodeLa01__swing', 'S_SleeveFL1'),('SWG_sodeRa01__swing', 'S_SleeveFR1'),('SWG_BHem0__swing', 'S_ShirttailB1'),
  ('SWG_FHem1__swing', 'S_ShirttailF1'),('SWG_LBHem0__swing', 'S_ShirttailBL1'),
  ('SWG_LFHem1__swing', 'S_ShirttailFL1'),('SWG_LSHem1__swing', 'S_ShirttailL1'),
  ('SWG_RBHem0__swing', 'S_ShirttailBR1'),('SWG_RFHem1__swing', 'S_ShirttailFR1'),
  ('SWG_RSHem1__swing', 'S_ShirttailR1'),('SWG_LFinN__swing', 'S_FinL1'),('SWG_RFinN__swing', 'S_FinR1'),
  ('SWG_TailN__swing', 'S_Tail1'),('SWG_LBStingNa__swing', 'StingL1'),('SWG_LBStingNb__swing', 'StingL2'),
  ('SWG_RBStingNa__swing', 'StingR1'),('SWG_RBStingNb__swing', 'StingR2'),('SWG_DStingNa__swing', 'S_StingD1'),
  ('SWG_DStingNb__swing', 'S_StingD2'),('SWG_UStingNa__swing', 'S_StingU1'),('SWG_UStingNb__swing', 'S_StingU2'),
  ('SWG_UStingNc__swing', 'S_StingU3'),('SWG_LAStingNa__swing', 'S_StingBL1'),('SWG_LAStingNb__swing', 'S_StingBL2'),
  ('SWG_RAStingNa__swing', 'S_StingBR1'),('SWG_RAStingNb__swing', 'S_StingBR2'),('SWG_HairA1__swing', 'S_HairF1'),
  ('SWG_HairB1__swing', 'S_HairFR1'),('SWG_HairC1__swing', 'S_HairFL1'),('SWG_HairD1__swing', 'S_HairBR1'),
  ('SWG_HairE1__swing', 'S_HairBL1'),('SWG_hair0__swing', 'S_Hair1'),('SWG_hair1__swing', 'S_Hair2'),
  ('SWG_hair2__swing', 'S_Hair3'),('SWG_LMant1__swing', 'S_MantleL2'),('SWG_LMant2__swing', 'S_MantleL3'),
  ('SWG_LMant3__swing', 'S_MantleL4'),('SWG_RMant1__swing', 'S_MantleR2'),('SWG_RMant2__swing', 'S_MantleR3'),
  ('SWG_RMant3__swing', 'S_MantleR4'),('SWG_CMant0__swing', 'S_MantleC1'),('SWG_CMant1__swing', 'S_MantleC2'),
  ('SWG_CMant2__swing', 'S_MantleC3'),('SWG_CMant3__swing', 'S_MantleC4'),('SWG_LFLeg0__swing', 'S_ShirttailFL1'),
  ('SWG_LFLeg1__swing', 'S_ShirttailFL2'),('SWG_LFLeg2__swing', 'S_ShirttailFL3'),
  ('SWG_RFLeg0__swing', 'S_ShirttailFR1'),('SWG_RFLeg1__swing', 'S_ShirttailFR2'),
  ('SWG_RFLeg2__swing', 'S_ShirttailFR3'),('SWG_RBHip0__swing', 'S_ShirttailBR1'),
  ('SWG_RBHip1__swing', 'S_ShirttailBR2'),('SWG_LBHip0__swing', 'S_ShirttailBL1'),
  ('SWG_LBHip1__swing', 'S_ShirttailBL2'),('SWG_LLeg0__swing', 'S_LegL1'),('SWG_RLeg0__swing', 'S_LegR1'),
  ('SWG_LHand0__swing', 'S_HandL1'),('SWG_RHand0__swing', 'S_HandR1'),('SWG_LFSBust0__swing', 'S_BusthairFL1'),
  ('SWG_LFSBust1__swing', 'S_BusthairFL2'),('SWG_RFSBust0__swing', 'S_BusthairFR1'),
  ('SWG_RFSBust1__swing', 'S_BusthairFR2'),('SayaTateN', 'ShieldB'),('SWG_BagA0__swing', 'queiver'),
  ('TateN', 'Shield'),('SphereN', 'Sphere'),('HatN', 'Hat'),('ShellNb', 'Shell2'),('ShellN', 'Shell1'),
  ('ShellCenterN', 'Shell'),('TailNa', 'Tail1'),('TailNb', 'Tail2'),('TailNc', 'Tail3'),('TailNd', 'Tail4'),
  ('TailN', 'Tail1'),('Tail1N', 'Tail2'),('Tail2N', 'Tail3'),('HLP_NeckJb', 'H_Neck'),('NeckN', 'Neck'),
  ('HeadN', 'Head'),('RHaveN', 'HaveR'),('LHaveN', 'HaveL'),('SpineN', 'Spine'),('HanaN', 'Snout'),
  ('ChinNa', 'Mouth2'),('ChinN', 'Mouth1'),('CheekN', 'Cheek'),('TamagoN', 'Egg'),('HLP_KneeLb', 'H_KneeL'),
  ('HLP_KneeRb', 'H_KneeR'),('HLP_LUpArmTwistjb', 'H_UparmtwistL'),('HLP_RUpArmTwistjb', 'H_UparmtwistR'),
  ('HLP_LTekubiJb', 'H_WristL'),('HLP_RTekubiJb', 'H_WristR'),('SWG_SHair1N__swing', 'S_HairF1'),
  ('SWG_SHair2N__swing', 'S_HairB1'),('HLP_CShellJb', 'H_ShellC'),('HLP_LShellJb', 'H_ShellL'),
  ('HLP_RShellJb', 'H_ShellR'),('JawN', 'Jaw'),('HaveN', 'Have'),('PipeJA', 'Pipe1'),('PipeJB', 'Pipe2'),
  ('PipeJC', 'Pipe3'),('PipeJD', 'Pipe4'),('PipeJE', 'Pipe5'),('SWG_TaiNa__swing', 'S_Tail1'),
  ('SWG_TaiNb__swing', 'S_Tail2'),('SWG_TaiNc__swing', 'S_Tail3'),('SWG_TaiNd__swing', 'S_Tail4'),
  ('SWG_TaiNe__swing', 'S_Tail5'),('SWG_TaiNf__swing', 'S_Tail6'),('SWG_TaiNg__swing', 'S_Tail7'),
  ('LMimiNb', 'EarL2'),('RMimiNb', 'EarR2'),('LMimiN', 'EarL1'),('RMimiN', 'EarR1'),('Sippo1N', 'S_Tail1'),
  ('Sippo2N', 'S_Tail2'),('Sippo3N', 'S_Tail3'),('Sipoo4N', 'S_Tail4'),('Sipoo5N', 'S_Tail5'),('Sippo6N', 'S_Tail6'),
  ('Sippo7N', 'S_Tail7'),('Sipoo8N', 'S_Tail8'),('Sippo9N', 'S_Tail9'),('AgoN', 'Mouth'),('JikuN', 'Shaft'),
  ('LKataSinN', 'ShoulderpadL'),('RKataSinN', 'ShoulderpadR'),('WingbaseN', 'Wingbase'),('LWingJa', 'WingL1'),
  ('LWingJb', 'WingL2'),('LWingJc', 'WingL3'),('LWingJd', 'WingL4'),('RWingJa', 'WingR1'),('RWingJb', 'WingR2'),
  ('RWingJc', 'WingR3'),('RWingJd', 'WingR4'),('KenJ', 'Sword1'),('SwordN', 'Sword1'),('KenModelN', 'Sword2'),
  ('SwordHeadN', 'Sword2'),('SayaN', 'Scabbard'),('Saya01N', 'Scabbard'),('SayaTukaN', 'Hilt'),('TsukaN', 'Hilt'),]

# ---------------- converter ----------------

# Ultimate -> Smash 4 names: reverse of the S4->Ult tool, first Smash 4 name wins (Brawl names come later there)
U2S={}
for s4,ult in S4_TO_ULT:
    U2S.setdefault(ult,s4)
U2S.update({'HaveL':'LHaveN','HaveR':'RHaveN','Throw':'ThrowN','Trans':'TransN','Rot':'RotN','Hip':'HipN'})
# Peach / Daisy swing bones (Ultimate S_* -> Smash 4 SWG_*). Skirt rigs differ -> rotation only.
SKIRT={'F':'F','FR':'RF','R':'RS','BR':'RB','B':'B','BL':'LB','L':'LS','FL':'LF'}
ROT_ONLY=set()
for u,s in SKIRT.items():
    for i in range(1,5):
        U2S['S_Skirt%s%d'%(u,i)]='SWG_%sSkirt%d__swing'%(s,i-1); ROT_ONLY.add('S_Skirt%s%d'%(u,i))
for i in range(1,4): U2S['S_Hair%d'%i]='SWG_Bhair%d__swing'%(i-1)
FOLD={'ClavicleL':'ClavicleC','ClavicleR':'ClavicleC','LegL':'LegC','LegR':'LegC'}   # child -> inserted Ultimate parent

def quat_from_euler(rx,ry,rz):
    cx,sx=np.cos(rx/2),np.sin(rx/2); cy,sy=np.cos(ry/2),np.sin(ry/2); cz,sz=np.cos(rz/2),np.sin(rz/2)
    # q = qz * qy * qx  (xyzw)
    x=sx*cy*cz-cx*sy*sz; y=cx*sy*cz+sx*cy*sz; z=cx*cy*sz-sx*sy*cz; w=cx*cy*cz+sx*sy*sz
    return np.stack([x,y,z,w],-1)
def qmul(a,b):
    ax,ay,az,aw=np.moveaxis(a,-1,0); bx,by,bz,bw=np.moveaxis(b,-1,0)
    return np.stack([aw*bx+ax*bw+ay*bz-az*by, aw*by-ax*bz+ay*bw+az*bx, aw*bz+ax*by-ay*bx+az*bw, aw*bw-ax*bx-ay*by-az*bz],-1)
def qrot(q,v):
    u=q[...,:3]; w=q[...,3:4]
    return v+2*np.cross(u,np.cross(u,v)+w*v)
def tracks(A,bone,frames):
    a=A.get(bone,{})
    T=np.stack([sample(a.get('translate'+c),frames,0.0) for c in 'XYZ'],-1)
    R=quat_from_euler(*[sample(a.get('rotate'+c),frames,0.0) for c in 'XYZ'])
    S=np.stack([sample(a.get('scale'+c),frames,1.0) for c in 'XYZ'],-1)
    return T,R,S

def convert(anim_path, vbn, stock_omos):
    A,order,start,end=read_anim(anim_path)
    last=max([v[0][-1] for b in A.values() for v in b.values() if len(v[0])>1] or [end-1])
    frames=np.arange(1,int(round(last))+1,dtype=float); F=len(frames)
    s2u={}
    for u in A:
        s=U2S.get(u)
        if s and s not in s2u: s2u[s]=u
    out={}
    for b in vbn:
        u=s2u.get(b['name'])
        if u is None: continue
        T,R,S=tracks(A,u,frames)
        if u in FOLD and FOLD[u] in A:            # fold ClavicleC / LegC back in
            Tp,Rp,Sp=tracks(A,FOLD[u],frames)
            T=Tp+qrot(Rp,T*Sp); R=qmul(Rp,R); S=Sp*S
        if u in ROT_ONLY: T=np.tile(b['pos'],(F,1))   # different rig: keep Smash 4 bone lengths
        out[b['id']]=dict(id=b['id'],pos=T,rot=R,sca=S,name=b['name'],rot_only=u in ROT_ONLY)
    return out,F

def qmean(Q):
    Q=np.asarray(Q,float); Q=Q/np.linalg.norm(Q,axis=1,keepdims=True)
    w,v=np.linalg.eigh(Q.T@Q); return v[:,-1]
def qang(a,b):
    a=a/np.linalg.norm(a,axis=-1,keepdims=True); b=b/np.linalg.norm(b,axis=-1,keepdims=True)
    return np.degrees(2*np.arccos(np.clip(np.abs((a*b).sum(-1)),0,1)))
LEG_BONES=('HipN','LLegJ','LKneeJ','LFootJ','RLegJ','RKneeJ','RFootJ')
def legs_match(conv,F,stock_main,sf,vbn,tol=8.0):
    """True when the converted legs move like the stock Smash 4 motion (same length, mean leg-bone difference < tol degrees)"""
    if F!=sf: return False, None
    ids={b['name']:b['id'] for b in vbn}; d=[]
    for n in LEG_BONES:
        h=ids.get(n)
        if h in conv and h in stock_main: d.append(qang(conv[h]['rot'],stock_main[h]['rot']).mean())
    if not d: return False, None
    return float(np.mean(d))<tol, float(np.mean(d))
def swing_fix(node,stock_node,F,mode):
    """Re-base a rebuilt-rig swing bone (e.g. skirt). 'stock' = Smash 4's own motion; 'anchored' = Ultimate's sway
    around Smash 4's average pose for this move instead of Ultimate's; 'ult' = Ultimate's rotations as they are."""
    if mode=='stock':
        return dict(id=node['id'],pos=stock_node['pos'],rot=stock_node['rot'],sca=stock_node['sca'])
    if mode=='anchored':
        base=qmean(stock_node['rot']); m=qmean(node['rot']); minv=m*np.array([-1,-1,-1,1])
        delta=qmul(np.tile(minv,(F,1)),node['rot']); R=qmul(np.tile(base,(F,1)),delta)
        return dict(id=node['id'],pos=node['pos'],rot=R,sca=node['sca'])
    return node

# ---------------- skirt push-out: swing skirt panels out where a knee or foot would poke through ----------------
SK_STRANDS=['F','LF','LS','LB','B','RB','RS','RF']   # around the body, in order
def q2m(q):
    q=q/np.linalg.norm(q,axis=-1,keepdims=True); x,y,z,w=np.moveaxis(q,-1,0)
    return np.stack([np.stack([1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],-1),
                     np.stack([2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],-1),
                     np.stack([2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)],-1)],-2)
def has_skirt(vbn):
    n={b['name'] for b in vbn}
    return all('SWG_%sSkirt%d__swing'%(s,i) in n for s in SK_STRANDS for i in range(4)) and all(x in n for x in ('HipN','LKneeJ','LFootJ','LToeN','RKneeJ','RFootJ','RToeN'))
def _hipspace(vbn,locq,loct,F):
    """forward kinematics relative to HipN; locq/loct: name->(F,4)/(F,3), anything missing uses the rest pose"""
    idx={b['name']:i for i,b in enumerate(vbn)}; memo={}
    def g(n):
        if n in memo: return memo[n]
        b=vbn[idx[n]]
        if n=='HipN': memo[n]=(np.tile(np.eye(3),(F,1,1)),np.zeros((F,3))); return memo[n]
        q=locq.get(n); q=np.tile(quat_from_euler(*b['rot']),(F,1)) if q is None else q
        t=loct.get(n); t=np.tile(b['pos'],(F,1)) if t is None else t
        pR,pp=g(vbn[b['parent']]['name']); memo[n]=(pR@q2m(q), pp+np.einsum('fij,fj->fi',pR,t)); return memo[n]
    return g
def _skirt_excess(vbn,locq,loct,F):
    g=_hipspace(vbn,locq,loct,F); pts=[]
    for sd in 'LR':
        K=g(sd+'KneeJ')[1]; Fo=g(sd+'FootJ')[1]; T=g(sd+'ToeN')[1]
        pts+= [(K,.75),(K*.67+Fo*.33,.65),(K*.33+Fo*.67,.6),(Fo,.6),(T,.55),(T+0.6*(T-Fo),.5)]   # leg surface points + thickness
    poly={}
    for s in SK_STRANDS:
        J=[g('SWG_%sSkirt%d__swing'%(s,i))[1] for i in range(4)]; J.append(J[3]+(J[3]-J[2]))  # + hem segment
        poly[s]=np.stack(J,1)
    az={s:poly[s][:,3,1:]/np.linalg.norm(poly[s][:,3,1:],axis=1,keepdims=True) for s in SK_STRANDS}
    def rad(P,x,u):   # radial reach of a strand at height x (hip-space -X is down), along azimuth u
        out=np.full(F,np.nan)
        for i in range(P.shape[1]-1):
            a,b=P[:,i],P[:,i+1]; den=b[:,0]-a[:,0]; ok=((a[:,0]-x)*(b[:,0]-x)<=0)&(den!=0)&np.isnan(out)
            t=np.where(ok,(x-a[:,0])/np.where(den==0,1,den),0); pt=a+t[:,None]*(b-a)
            out=np.where(ok,(pt[:,1:]*u).sum(1),out)
        return out
    need={s:np.zeros(F) for s in SK_STRANDS}; worst=np.zeros(F)
    for p,r in pts:
        ph=p[:,1:]; pn=np.linalg.norm(ph,axis=1)+1e-9; pu=ph/pn[:,None]
        for i,s in enumerate(SK_STRANDS):
            s2=SK_STRANDS[(i+1)%8]; c12=(az[s]*az[s2]).sum(1)
            between=((az[s]*pu).sum(1)>=c12-1e-6)&((az[s2]*pu).sum(1)>=c12-1e-6)
            if not between.any(): continue
            rr=np.fmin(rad(poly[s],p[:,0],pu),rad(poly[s2],p[:,0],pu))
            e=np.maximum(np.where(between&np.isfinite(rr),pn+r-rr,0.0),0)
            worst=np.maximum(worst,e); need[s]=np.maximum(need[s],e); need[s2]=np.maximum(need[s2],e)
    return need,worst,poly
def skirt_pushout(vbn,locq,loct,F,iters=8,gain=1.3,smooth=2):
    """returns new top-panel rotations {SWG_xSkirt0__swing: (F,4)} and the remaining worst poke-through per frame"""
    locq=dict(locq); down=np.array([-1.,0,0])
    for _ in range(iters):
        need,worst,poly=_skirt_excess(vbn,locq,loct,F)
        if worst.max()<1e-3: break
        for s in SK_STRANDS:
            e=need[s]
            if e.max()<=0: continue
            em=np.array([e[max(0,f-smooth):f+smooth+1].max() for f in range(F)])          # ease in/out
            em=np.convolve(np.pad(em,smooth,mode='edge'),np.ones(2*smooth+1)/(2*smooth+1),'valid')
            P=poly[s]; L=np.linalg.norm(P[:,4]-P[:,0],axis=1)
            d=np.arcsin(np.clip(em*gain/np.maximum(L,1e-3),0,0.9))
            u=np.concatenate([np.zeros((F,1)),P[:,3,1:]],1); u/=np.linalg.norm(u,axis=1,keepdims=True)
            ax=np.cross(down,u); h=np.sin(d/2)[:,None]
            R=np.concatenate([ax*h,np.cos(d/2)[:,None]],1)                                    # hip-space swing outward
            n='SWG_%sSkirt0__swing'%s; locq[n]=qmul(R,locq[n])
    need,worst,_=_skirt_excess(vbn,locq,loct,F)
    return {('SWG_%sSkirt0__swing'%s):locq['SWG_%sSkirt0__swing'%s] for s in SK_STRANDS}, worst

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--vbn',required=True); ap.add_argument('--pacs',required=True)
    ap.add_argument('--out',required=True); ap.add_argument('--prefix',default=None,help='e.g. FitPeachBody (auto from main.pac)')
    ap.add_argument('--skirt',choices=['auto','stock','anchored','ult'],default='auto',
        help="rebuilt-rig swing bones (Peach/Daisy skirt): auto = Smash 4's own skirt when the legs match the stock move; Smash 4's skirt + push-out when only the legs differ; anchored + push-out when the length differs")
    ap.add_argument('--no-pushout',action='store_true',help="don't swing skirt panels out where legs would poke through")
    ap.add_argument('anims',nargs='+',help='file.anim or file.anim=MotionName (default: name from the file, a00wait1 -> A00Wait1)')
    a=ap.parse_args()
    vbn=read_vbn(a.vbn); os.makedirs(a.out,exist_ok=True)
    pacs={}
    for f in sorted(os.listdir(a.pacs)):
        if f.endswith('.pac'): pacs[f[:-4]]=read_pac(os.path.join(a.pacs,f))
    main=pacs['main'][0]; prefix=a.prefix or re.match(r'(Fit\w+?Body)Main',next(iter(main))).group(1)
    report=[]
    for item in a.anims:
        path,_,mname=item.partition('=')
        if not mname:
            b=os.path.splitext(os.path.basename(path))[0]; m=re.match(r'([a-z])(\d+)(.*)',b)
            mname=m.group(1).upper()+m.group(2)+m.group(3)[:1].upper()+m.group(3)[1:]
        conv,F=convert(path,vbn,None)
        mk=[k for k in main if k.lower()==('%sMain%s.omo'%(prefix,mname)).lower()]
        mode=a.skirt; note=''; do_push=mode in ('anchored','stock')
        if mode=='auto':
            sm,sfm=read_omo(main[mk[0]]) if mk else ({},0)
            ok,dev=legs_match(conv,F,sm,sfm,vbn) if mk else (False,None)
            # same move (legs match): Smash 4's skirt as is; same length but new legs: Smash 4's skirt timing + push-out;
            # different length: Ultimate's sway on Smash 4's skirt shape + push-out
            mode='stock' if (ok or (mk and F==sfm)) else 'anchored'; do_push=not ok
            note=' (legs %s stock%s)'%('match' if ok else 'differ from', '' if dev is None else ', %.1f deg'%dev)
        report.append('%s: skirt = %s%s'%(mname,mode,note))
        pushed={}
        if do_push and mode in ('anchored','stock') and has_skirt(vbn) and not a.no_pushout:
            ids={b['name']:b['id'] for b in vbn}; stk={}
            for pk,(files,E) in pacs.items():
                key=[k for k in files if k.lower()==('%s%s%s.omo'%(prefix,pk.capitalize(),mname)).lower()]
                if key: stk.update(read_omo(files[key[0]])[0])
            locq={}; loct={}
            for b in vbn:
                h=b['id']
                if h in conv:
                    node=swing_fix(conv[h],stk[h],F,mode) if conv[h].get('rot_only') and h in stk else conv[h]
                    locq[b['name']]=node['rot']
                    if not conv[h].get('rot_only'): loct[b['name']]=node['pos']
            if all(n in locq for n in ['SWG_%sSkirt0__swing'%x for x in SK_STRANDS]):
                before=_skirt_excess(vbn,locq,loct,F)[1]
                newq,after=skirt_pushout(vbn,locq,loct,F)
                pushed={ids[n]:q for n,q in newq.items()}
                report.append('%s: skirt push-out: legs poked through in %d/%d frames (worst %.2f) -> %d frames (worst %.2f)'%(mname,(before>0.05).sum(),F,before.max(),(after>0.05).sum(),after.max()))
        for pk,(files,E) in pacs.items():
            key=[k for k in files if k.lower()==('%s%s%s.omo'%(prefix,pk.capitalize(),mname)).lower()]
            if not key: report.append('%s: %s.pac has no %s - skipped'%(mname,pk,mname)); continue
            stock,sf=read_omo(files[key[0]])
            nodes=[swing_fix(conv[h],stock[h],F,mode) if conv[h].get('rot_only') else conv[h] for h in stock if h in conv]
            nodes=[dict(n,rot=pushed[n['id']]) if n['id'] in pushed else n for n in nodes]
            if mode=='stock' and F!=sf: raise SystemExit('--skirt stock needs the same frame count as the stock motion (%s: %d vs %d)'%(mname,F,sf))
            missing=[h for h in stock if h not in conv]
            # bones the stock .omo animates but Ultimate doesn't have: keep the stock motion, stretched to the new length
            t=np.linspace(0,sf-1,F)
            def rs(v): return np.stack([np.interp(t,np.arange(len(v)),v[:,c]) for c in range(v.shape[1])],-1)
            for h in missing:
                s=stock[h]; nodes.append(dict(id=h,pos=rs(s['pos']),rot=rs(s['rot']),sca=rs(s['sca'])))
            order={h:i for i,h in enumerate(stock)}; nodes.sort(key=lambda n: order[n['id']])
            tmp=os.path.join(a.out,key[0]); write_omo(nodes,F,tmp); files[key[0]]=open(tmp,'rb').read()
            report.append('%s: %s.pac %s  %d frames (stock %d), %d bones, %d kept from stock'%(mname,pk,key[0],F,sf,len(nodes),len(missing)))
    for pk,(files,E) in pacs.items(): write_pac(files,os.path.join(a.out,pk+'.pac'),E)
    print('\n'.join(report)); open(os.path.join(a.out,'report.txt'),'w').write('\n'.join(report)+'\n')
if __name__=='__main__': main()
