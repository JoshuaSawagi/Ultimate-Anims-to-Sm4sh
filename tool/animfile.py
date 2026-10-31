"""Maya .anim (as exported by StudioSB / Smash Forge) reader: {bone: {attr: (frames, values)}}, start, end"""
import re, numpy as np
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
