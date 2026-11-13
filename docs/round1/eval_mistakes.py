import openpyxl, statistics as st, re, collections
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
        if any(x is None for x in s): continue
        green = r[0].fill.fill_type is not None and r[0].fill.fgColor.rgb=='FF00B050'
        ALL.append(dict(track=ws.title,team=str(v[0]).strip(),s=s,green=green,remark=str(v[rmk]).strip() if v[rmk] else ''))
R=[a for a in ALL if a['remark']]
base=[st.mean(a['s'][j] for a in R) for j in range(5)]
print('teams with remarks',len(R),'baseline I/C/D/E/O',[round(b,1) for b in base])
P={
 'no 24h/hourly plan asked':r'add (an?|the)? ?(hourly|hour-wise|hour-by-hour|24-hour|clear 24|realistic 24)|needs? (an? )?(hourly|24-hour)|24-hour (plan|build|timeline|roadmap)|hourly (build )?(plan|timeline)|hour-wise|phase timings',
 'roadmap in months/weeks':r'roadmap (spans|is in)|months|four-week|eight weeks|weeks',
 'scope unrealistic/too broad':r'unrealistic|too broad|too much|far exceed|very broad|overly|all-in-one|super-app|pick one|one core|prioritise one|many input modes|exceed',
 'stack/hardware too heavy':r'heavy|trim|fine-tun|kubernetes|blockchain|ebpf|drones?\b|gpu|multispectral|ros 2',
 'vague/generic/thin content':r'too general|generic|thin|brief|vague|sparse|hedged|if implemented',
 'common idea/no differentiator':r'differentiator|distinctive|the idea is common|sets it apart|similar tools|existing (tools|scanners|apps)|repeats the existing',
 'missing tech stack/model/libs':r'tech(nology)? stack (and|is|are)? ?(missing|vague)|name the|specify the|finalise|concrete (tech )?stack|add .*stack|stack.*missing|missing.*stack',
 'missing dataset/data source':r'dataset|training data|data sources?|sample data|synthetic',
 'unsupported number/claim':r'claim|needs? evidence|support the|figures|target figures|test set|accuracy|100%|0%|zero false|sub-15',
 'no evidence of the problem':r'evidence of|real(-world)? (data|evidence|statistics)|add (data|evidence|statistics|numbers)|problem data|usage data|baseline|field evidence|add figures|target numbers',
 'template/placeholder/slide mess':r'template|placeholder|leftover|overlap|repeated|repeats|typo|tidy|slide layout|slides are|missing slide|slide is missing|unfilled|fill in',
 'wrong track/fit':r'not agritech|hardware idea|closer to|listed under|fit\b|healthtech idea|open innovation idea|wrong track|not fintech|not healthtech|weak .* fit',
 'workflow/architecture missing':r'workflow (and|is|are)? ?.*missing|add a (clear )?workflow|architecture diagram|implementation roadmap is missing|add .*architecture|roadmap (is )?missing|workflow diagram',
 'infeasible/fantasy demo':r"isn.t feasible|not feasible|unrealistic for|isn't feasible|fantasy|holograms?|flying|living-sensor|robots",
 'misuse/consent/authorisation':r'consent|authoris|authoriz|misuse|privacy harm|safety',
 'reused/prebuilt unclear':r'reused|newly built|built during|earlier prototype|what will be built',
 'mismatch between parts':r'conflict|mismatch|while the|but the training|mix(es)? |two separate problems|combined loosely',
}
print(f"\n{'ANTI-PATTERN':34s}{'n':>4s}{'Imp':>6s}{'Cre':>6s}{'Des':>6s}{'Exe':>6s}{'Ovr':>6s}   delta vs baseline (I C D E O)")
rows=[]
for k,p in P.items():
    hit=[a for a in R if re.search(p,a['remark'],re.I)]
    if not hit: continue
    m=[st.mean(a['s'][j] for a in hit) for j in range(5)]
    rows.append((m[4]-base[4],k,len(hit),m))
for d,k,n,m in sorted(rows):
    print(f"{k:34s}{n:4d}"+''.join(f"{x:6.1f}" for x in m)+"   "+' '.join(f"{m[j]-base[j]:+.1f}" for j in range(5)))
print('\n== Count per track')
tracks=sorted(set(a['track'] for a in R))
print(f"{'':34s}"+''.join(f"{t[:7]:>9s}" for t in tracks))
for k,p in P.items():
    print(f"{k:34s}"+''.join(f"{sum(1 for a in R if a['track']==t and re.search(p,a['remark'],re.I)):9d}" for t in tracks))
print('\n== Positive phrases: mean overall when remark uses them')
Q={'hourly plan praised':r'(clear|with|and|well-scoped).{0,30}hourly plan|hourly plan;','honest':r'honest','well-scoped/feasible':r'well-scoped|feasible|buildable','measured/benchmark/backtest':r'benchmark|backtest|measured|held-out|validation|tests\b','working/prototype/live demo':r'working|prototype|live |demo plan','rigorous':r'rigorous|thoughtful','original/novel':r'original|novel|distinctive'}
for k,p in Q.items():
    hit=[a for a in R if re.search(p,a['remark'],re.I)]
    m=[st.mean(a['s'][j] for a in hit) for j in range(5)]
    print(f"{k:34s}{len(hit):4d}"+''.join(f"{x:6.1f}" for x in m))
print('\n== NEAR MISSES: best 6 not shortlisted per track (what stopped them)')
for t in tracks:
    n=sorted([a for a in R if a['track']==t and not a['green']],key=lambda a:-a['s'][4])[:6]
    print('--',t)
    for a in n: print('  ',int(a['s'][4]),[int(x) for x in a['s'][:4]],a['team'],'|',a['remark'][:190])
print('\n== BOTTOM 5 per track')
for t in tracks:
    n=sorted([a for a in R if a['track']==t],key=lambda a:a['s'][4])[:5]
    print('--',t)
    for a in n: print('  ',int(a['s'][4]),[int(x) for x in a['s'][:4]],a['team'],'|',a['remark'][:190])
print('\n== High idea, weak build: Impact+Creativity >=36 but Execution <=13')
for a in sorted(R,key=lambda a:a['s'][3]):
    if a['s'][0]+a['s'][1]>=36 and a['s'][3]<=13: print('  ',a['track'][:8],int(a['s'][4]),[int(x) for x in a['s'][:4]],a['team'],'|',a['remark'][:170])
print('\n== Weakest criterion across shortlisted teams per track (mean I C D E)')
for t in tracks:
    g=[a for a in ALL if a['track']==t and a['green']]
    print(f"  {t:24s}",[round(st.mean(a['s'][j] for a in g),1) for j in range(4)],'n',len(g))
print('\n== Shortlisted teams with Execution <=15 (idea carried them, final-round build risk)')
for a in sorted([a for a in ALL if a['green'] and a['s'][3]<=15],key=lambda a:a['s'][3]):
    print('  ',a['track'][:10],a['team'],[int(x) for x in a['s']])
