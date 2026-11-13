import openpyxl, re, statistics as st
wb=openpyxl.load_workbook('/Users/arjunar/Downloads/Final_Evaluaton_Sheet.xlsx',data_only=True)
A=[]
for ws in wb.worksheets:
    h=[str(c.value).strip() if c.value else '' for c in ws[1]]
    i=[h.index(x) for x in ['Impact Score /25','Creativity Score /25','Design Score /25','Execution Score /25','Overall Score /100']]
    k=h.index('Remark')
    for r in ws.iter_rows(min_row=2):
        v=[c.value for c in r]
        if v[0] is None: continue
        try: s=[float(v[j]) for j in i]
        except: continue
        A.append((ws.title,str(v[0]).strip(),s,r[0].fill.fill_type is not None and r[0].fill.fgColor.rgb=='FF00B050',str(v[k]).strip() if v[k] else ''))
print('== Shortlist rate by Design/Execution band (excluding Open Innovation, whose cutoff was 63)')
B=[a for a in A if a[0]!='Open Innovation']
bands={'Design>=19 and Execution>=18':lambda s:s[2]>=19 and s[3]>=18,'Design>=19, Execution<18':lambda s:s[2]>=19 and s[3]<18,'Design<19, Execution>=18':lambda s:s[2]<19 and s[3]>=18,'Design<19, Execution<18':lambda s:s[2]<19 and s[3]<18}
for n,f in bands.items():
    x=[a for a in B if f(a[2])]; g=sum(1 for a in x if a[3])
    print(f'  {n:32s} teams {len(x):3d} shortlisted {g:3d} rate {100*g/len(x):5.1f}% mean overall {st.mean(a[2][4] for a in x):.1f}')
print('== Strong idea (I+C>=36) by Execution band, all tracks')
for lo,hi in [(0,13),(14,16),(17,25)]:
    x=[a for a in A if a[2][0]+a[2][1]>=36 and lo<=a[2][3]<=hi]; g=sum(1 for a in x if a[3])
    print(f'  Execution {lo}-{hi}: teams {len(x)} shortlisted {g} rate {100*g/max(1,len(x)):.0f}%')
print('== Remark rates per track (%)')
R=[a for a in A if a[4]]
P={'hourly plan asked':r'add (an?|the)? ?(hourly|hour-wise|hour-by-hour|24-hour|clear 24|realistic 24)|needs? (an? )?(hourly|24-hour)|24-hour (plan|build|timeline|roadmap)|hourly (build )?(plan|timeline)|hour-wise|phase timings','dataset':r'dataset|training data|data sources?|sample data|synthetic','name tools/model':r'tech(nology)? stack (and|is|are)? ?(missing|vague)|name the|specify the|finalise|concrete (tech )?stack|add .*stack|stack.*missing|missing.*stack','evidence of problem':r'evidence of|real(-world)? (data|evidence|statistics)|add (data|evidence|statistics|numbers)|problem data|usage data|baseline|field evidence|add figures|target numbers','differentiator':r'differentiator|distinctive|the idea is common|sets it apart|similar tools|existing (tools|scanners|apps)|repeats the existing','slide mess':r'template|placeholder|leftover|overlap|repeated|repeats|typo|tidy|slide layout|slides are|missing slide|slide is missing|unfilled|fill in','consent/safety':r'consent|authoris|authoriz|misuse|privacy harm|safety','number needs support':r'claim|needs? evidence|support the|figures|target figures|test set|accuracy|100%|0%|zero false|sub-15'}
T=sorted(set(a[0] for a in R))
print(f"{'':24s}"+''.join(f'{t[:8]:>10s}' for t in T))
print(f"{'remarks':24s}"+''.join(f'{sum(1 for a in R if a[0]==t):10d}' for t in T))
for k,p in P.items():
    print(f'{k:24s}'+''.join(f"{100*sum(1 for a in R if a[0]==t and re.search(p,a[4],re.I))/sum(1 for a in R if a[0]==t):10.0f}" for t in T))
print('== Specific remarks for our risks')
for label,p in {'OCR':r'\bocr\b','simulation path':r'simulation to|path from|deployment','data access':r'restricted|partner data|registry|kept trustworthy|populated','hedged':r'hedged|if implemented','user value':r'user value|relevance to|practical deployment','false alarms':r'false alarm|false positive|false-positive','typos/team details':r'typo|unfilled|team details|fill in the','blockchain':r'blockchain','plan too long':r'exceeds|36-hour|six-day|four-week|12 weeks|eight weeks','too many parts':r'\b(four|five|six|eight|13|many) (modules|roles|agents|engines|robots|input|layers)|large stack|heavy stack'}.items():
    print('--',label)
    for a in R:
        if re.search(p,a[4],re.I): print('  ',a[0][:8],int(a[2][4]),a[1],'|',a[4][:165])
