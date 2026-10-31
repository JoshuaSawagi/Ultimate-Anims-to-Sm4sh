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
"""
import sys, os, json, re, argparse, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from s4lib import read_vbn, read_pac, write_pac, read_omo
from animfile import read_anim, sample
from animw import write_omo

HERE=os.path.dirname(os.path.abspath(__file__))
# Ultimate -> Smash 4 names: reverse of the S4->Ult tool, first Smash 4 name wins (Brawl names come later there)
U2S={}
for s4,ult in json.load(open(os.path.join(HERE,'s4_to_ult_pairs.json'))):
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
        out[b['id']]=dict(id=b['id'],pos=T,rot=R,sca=S,name=b['name'])
    return out,F

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--vbn',required=True); ap.add_argument('--pacs',required=True)
    ap.add_argument('--out',required=True); ap.add_argument('--prefix',default=None,help='e.g. FitPeachBody (auto from main.pac)')
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
        for pk,(files,E) in pacs.items():
            key=[k for k in files if k.lower()==('%s%s%s.omo'%(prefix,pk.capitalize(),mname)).lower()]
            if not key: report.append('%s: %s.pac has no %s - skipped'%(mname,pk,mname)); continue
            stock,sf=read_omo(files[key[0]])
            nodes=[conv[h] for h in stock if h in conv]
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
