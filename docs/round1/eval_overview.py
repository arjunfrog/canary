import openpyxl, statistics as st, collections, re
wb = openpyxl.load_workbook('/Users/arjunar/Downloads/Final_Evaluaton_Sheet.xlsx', data_only=True)
def num(x):
    try: return float(x)
    except: return None
ALL=[]
for ws in wb.worksheets:
    hdr=[str(c.value).strip() if c.value else '' for c in ws[1]]
    idx={h:i for i,h in enumerate(hdr)}
    I=[idx[k] for k in ['Impact Score /25','Creativity Score /25','Design Score /25','Execution Score /25','Overall Score /100']]
    rmk=idx.get('Remark')
    for r in ws.iter_rows(min_row=2):
        v=[c.value for c in r]
        if v[0] is None: continue
        s=[num(v[i]) for i in I]
        green = r[0].fill.fill_type is not None and r[0].fill.fgColor.rgb=='FF00B050'
        ALL.append(dict(track=ws.title,team=str(v[0]).strip(),s=s,green=green,remark=(v[rmk] or '').strip() if v[rmk] else ''))
    cm=[(c.coordinate,c.comment.text) for row in ws.iter_rows() for c in row if c.comment]
    hid_c=[k for k,d in ws.column_dimensions.items() if d.hidden]
    hid_r=[k for k,d in ws.row_dimensions.items() if d.hidden]
    print(ws.title,'comments',cm[:3],'hidden cols',hid_c,'hidden rows',len(hid_r),'merged',len(ws.merged_cells.ranges))
print('total teams',len(ALL),'green',sum(a['green'] for a in ALL))
print('\n== SHORTLIST CUTOFFS')
for t in sorted(set(a['track'] for a in ALL)):
    g=[a for a in ALL if a['track']==t and a['green']]
    n=[a for a in ALL if a['track']==t and not a['green']]
    gs=[a['s'][4] for a in g]; ns=[a['s'][4] for a in n if a['s'][4] is not None]
    print(f"{t:24s} shortlisted {len(g):2d}/{len(g)+len(n):2d} cutoff {min(gs):.0f} top {max(gs):.0f} | best-not-shortlisted {max(ns):.0f}")
print('\n== GLOBAL SHORTLIST TOP 25 (all tracks)')
g=sorted([a for a in ALL if a['green']],key=lambda a:-a['s'][4])
for i,a in enumerate(g[:25]):
    print(i+1,a['track'][:12],a['team'],a['s'])
print('rank of RADIOHEAD overall among green:',[i+1 for i,a in enumerate(g) if a['team']=='RADIOHEAD'],'of',len(g))
print('\n== SUBSCORE: shortlisted vs not (all tracks) and stdev')
names=['Impact','Creativity','Design','Execution','Overall']
G=[a for a in ALL if a['green']]; N=[a for a in ALL if not a['green'] and a['s'][4] is not None]
for j,n in enumerate(names):
    gx=[a['s'][j] for a in G]; nx=[a['s'][j] for a in N if a['s'][j] is not None]
    print(f"{n:11s} shortlisted mean {st.mean(gx):5.1f} sd {st.pstdev(gx):4.1f} | others mean {st.mean(nx):5.1f} sd {st.pstdev(nx):4.1f} | gap {st.mean(gx)-st.mean(nx):4.1f}")
print('\n== Cyber shortlisted subscore means + RADIOHEAD delta')
CG=[a for a in G if a['track']=='Cybersecurity']
r=[a for a in CG if a['team']=='RADIOHEAD'][0]
for j,n in enumerate(names):
    xs=[a['s'][j] for a in CG]
    rank=sorted(xs,reverse=True).index(r['s'][j])+1
    print(f"{n:11s} us {r['s'][j]:4.0f} | shortlist mean {st.mean(xs):5.1f} max {max(xs):3.0f} | rank {rank}/{len(xs)}")
print('\n== Global top by each subscore among shortlisted')
for j,n in enumerate(names[:4]):
    t=sorted(G,key=lambda a:-a['s'][j])[:5]
    print(n,[(a['team'],a['s'][j]) for a in t])
print('\n== Correlation of subscores to overall (all scored)')
def corr(x,y):
    mx,my=st.mean(x),st.mean(y)
    a=sum((p-mx)*(q-my) for p,q in zip(x,y)); b=(sum((p-mx)**2 for p in x)*sum((q-my)**2 for q in y))**.5
    return a/b
S=[a for a in ALL if all(v is not None for v in a['s'])]
for j,n in enumerate(names[:4]):
    print(n,round(corr([a['s'][j] for a in S],[a['s'][4] for a in S]),3))
print('\n== Competing ideas: keyword grep across all remarks')
kw=re.compile(r'exam|leak|paper|watermark|fingerprint|canary|steganograph|trace|provenance|document',re.I)
for a in ALL:
    if a['remark'] and kw.search(a['remark']):
        print(a['track'][:10],'|',a['team'],'|',a['s'][4],'|',a['remark'])
print('\n== Theme tallies in remarks (substring count across %d remarks)'%sum(1 for a in ALL if a['remark']))
themes={
 'hourly plan / 24h plan':r'hourly|hour-by-hour|hour-wise|24-hour plan|24-hour build|hour wise',
 'scope too big / trim / narrow':r'heavy|trim|narrow|unrealistic|exceed|far exceed|ambitious|pick one|scope',
 'define dataset / data sources':r'dataset|training data|data source|sample data|synthetic',
 'claims need evidence / test set':r'claim|evidence for|needs evidence|test set|accuracy|validate|figures|target|sub-15|false.positive',
 'honest (praise)':r'honest',
 'differentiator / common idea':r'differentiator|distinctive|common|generic|sets it apart|existing',
 'tidy slides/placeholder/template':r'placeholder|template|overlap|tidy|leftover|sparse|thin|typo|repeated slide',
 'demo slice / demo fallback':r'demo',
 'name the actual model/libs':r'name the|specify|finalise|finalize',
 'newly built vs reused':r'reused|newly built|built during|earlier prototype|clarify what',
 'scope/legal consent':r'consent|authoris|authoriz|privacy|misuse',
 'workflow diagram/UX screens':r'diagram|wireframe|screens|mockup',
}
for k,p in themes.items():
    c=sum(1 for a in ALL if a['remark'] and re.search(p,a['remark'],re.I))
    print(f"  {k:36s} {c}")
print('\n== Execution<=10 reasons')
for a in ALL:
    if a['s'][3] is not None and a['s'][3]<=10 and a['remark']: print('  ',a['track'][:8],a['team'],a['s'][3],a['remark'][:170])
print('\n== Execution>=20 remarks (not shortlisted)')
for a in ALL:
    if a['s'][3] is not None and a['s'][3]>=20 and a['remark']: print('  ',a['track'][:8],a['team'],a['s'][3],a['remark'][:170])
print('\n== Design>=20 remarks')
for a in ALL:
    if a['s'][2] is not None and a['s'][2]>=20 and a['remark']: print('  ',a['track'][:8],a['team'],a['s'][2],a['remark'][:170])
