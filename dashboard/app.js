/* Browser reporting over the existing cleaned synthetic data. No live patient data. */
const D=window.CLINIC_DATA, A=D.appointments, P=D.patients;
const $=id=>document.getElementById(id), sum=a=>a.reduce((x,y)=>x+y,0);
const fmt=n=>Math.round(n).toLocaleString('en-CA'), money=n=>(n/100).toLocaleString('en-CA',{style:'currency',currency:'CAD',maximumFractionDigits:0}),pct=n=>Number.isFinite(n)?(n*100).toFixed(1)+'%':'—';
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const months=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
const colors=['#7141bc','#b5a3ed','#d6cbe8','#da8ca4'];
const shortCats=['Routine & preventive','Repair & restoration','Gum care','Root canal care','Surgery & replacement','Alignment & other care'];
const categoryDescriptions=['Check-ups, preventive cleaning and diagnostic services.','Fillings, crowns and other services that restore teeth.','Periodontal maintenance and gum assessments.','Services treating the tooth pulp and root canals.','Extractions, replacement-related care and denture adjustments.','Aligner reviews, night guards and other related care.'];
let page='overview',category=0,latestExport=[];
months.forEach((m,i)=>$('month').add(new Option(m,String(i+1).padStart(2,'0'))));
D.locations.forEach((l,i)=>$('location').add(new Option(l[0]+' · '+l[1],String(i))));
const allDates=[...new Set(D.costs.map(x=>x[0]))].sort();
const netByVisit=Array(A.length).fill(0);D.treatments.forEach(t=>netByVisit[t[0]]+=t[2]);
function dateMatch(d){return ($('year').value==='all'||d.slice(0,4)===$('year').value)&&($('month').value==='all'||d.slice(5,7)===$('month').value);}
function locMatch(l){return $('location').value==='all'||l===Number($('location').value);}
function metric(label,value,note){return `<div class="metric"><div class="label">${label}</div><strong>${value}</strong><small>${note}</small></div>`;}
function panel(title,sub,body,extra=''){return `<section class="panel ${extra}"><h2>${title}</h2><p class="sub">${sub}</p>${body}</section>`;}
function legend(names){return '<div class="legend">'+names.map((n,i)=>`<span><i class="dot" style="background:${colors[i%colors.length]}"></i>${esc(n)}</span>`).join('')+'</div>';}
function chart(rows,names,{currency=false,click=false}={}){
 if(!rows.length)return '<div class="empty">No records in this period.</div>';
 const w=650,h=270,left=65,right=20,top=20,bottom=45,iw=w-left-right,ih=h-top-bottom;
 const all=rows.flatMap(r=>r.values),lo=Math.min(0,...all),hi=Math.max(1,...all),range=hi-lo;
 const x=i=>left+(rows.length===1?iw/2:i*iw/(rows.length-1)),y=v=>top+(hi-v)/range*ih;
 let s=`<svg viewBox="0 0 ${w} ${h}" class="chart" role="img" aria-label="${esc(names.join(', '))} over the selected months">`;
 for(let j=0;j<=4;j++){const v=lo+range*j/4,yy=y(v);s+=`<line x1="${left}" x2="${w-right}" y1="${yy}" y2="${yy}" stroke="#eee9f4"/><text x="${left-9}" y="${yy+4}" text-anchor="end" fill="#80768b" font-size="10">${currency?money(v):fmt(v)}</text>`;}
 names.forEach((name,j)=>{s+=`<polyline points="${rows.map((r,i)=>x(i)+','+y(r.values[j])).join(' ')}" fill="none" stroke="${colors[j]}" stroke-width="2.5"/>`;
 rows.forEach((r,i)=>s+=`<circle cx="${x(i)}" cy="${y(r.values[j])}" r="4" fill="${colors[j]}" ${click?'class="clickable" tabindex="0" role="button" data-month="'+r.key+'" aria-label="Filter '+r.key+'"':''}><title>${esc(r.label)} · ${esc(name)}: ${currency?money(r.values[j]):fmt(r.values[j])}</title></circle>`);});
 const every=Math.max(1,Math.ceil(rows.length/9));rows.forEach((r,i)=>{if(i%every===0||i===rows.length-1)s+=`<text x="${x(i)}" y="${h-15}" text-anchor="middle" fill="#80768b" font-size="10">${esc(r.label)}</text>`;});
 return s+'</svg>'+legend(names);
}
function bars(rows,{currency=false}={}){const max=Math.max(1,...rows.map(r=>r.value));return rows.map(r=>`<div class="bar-row"><span>${esc(r.label)}</span><div class="bar-track"><div class="bar-fill" style="width:${100*r.value/max}%"></div></div><span class="value">${currency?money(r.value):fmt(r.value)}</span></div>`).join('');}
function table(headers,rows){return '<div class="table-scroll"><table><thead><tr>'+headers.map((x,i)=>`<th class="${i?'num':''}">${esc(x)}</th>`).join('')+'</tr></thead><tbody>'+rows.map(row=>'<tr>'+row.map((x,i)=>`<td class="${i?'num':''}">${x}</td>`).join('')+'</tr>').join('')+'</tbody></table></div>';}
function periodLabel(m){return months[Number(m.slice(5,7))-1]+' '+m.slice(2,4);}
function recallSnapshot(cutoff){const latest=new Map();for(const q of D.recalls){const a=A[q[1]];if(a[2]>cutoff)continue;const prev=latest.get(q[0]);if(!prev||A[prev[1]][2]<a[2]||(A[prev[1]][2]===a[2]&&prev[1]<q[1]))latest.set(q[0],q);}return [...latest.values()].filter(q=>locMatch(A[q[1]][1]));}
function isOverdue(q,cutoff){const d=new Date(q[2]+'T00:00:00Z');d.setUTCDate(d.getUTCDate()+q[3]);return d.toISOString().slice(0,10)<cutoff;}
function getState(){
 const dates=allDates.filter(dateMatch),cutoff=dates.at(-1)||'2025-12-31',first=dates[0]||cutoff;
 const selected=[];A.forEach((a,i)=>{if(dateMatch(a[2])&&locMatch(a[1]))selected.push(i);});
 const completed=selected.filter(i=>A[i][4]===0),patients=new Set(completed.map(i=>A[i][0]));
 const monthly=[...new Set(dates.map(d=>d.slice(0,7)))];
 return {dates,cutoff,first,selected,completed,patients,monthly};
}
function overview(s){
 const noShows=s.selected.filter(i=>A[i][4]===2).length;
 const newPatients=[...s.patients].filter(p=>P[p][2]>=s.first&&P[p][2]<=s.cutoff).length;
 const firstVisit=new Map();for(const i of s.completed){const a=A[i];if(!firstVisit.has(a[0])||a[2]<firstVisit.get(a[0]))firstVisit.set(a[0],a[2]);}
 const ages=[...firstVisit].map(([p,d])=>Number(d.slice(0,4))-P[p][0]);
 $('metrics').innerHTML=metric('Unique patients seen',fmt(s.patients.size),'Distinct people with completed visits')+metric('Completed visits',fmt(s.completed.length),'One person may have several visits')+metric('New patients seen',fmt(newPatients),'First-ever visit in selected period')+metric('Returning patients seen',fmt(s.patients.size-newPatients),'First attended before this period')+metric('Attendance rate',pct(s.completed.length/(s.completed.length+noShows)),'Completed ÷ completed + no-show')+metric('Average patient age',ages.length?(sum(ages)/ages.length).toFixed(1):'—','Approximate years · each person once');
 const ageRows=[['0–17',0,17],['18–34',18,34],['35–49',35,49],['50–64',50,64],['65+',65,150]].map(([label,min,max])=>({label,values:[0,0,0],min,max}));
 firstVisit.forEach((d,p)=>{const age=Number(d.slice(0,4))-P[p][0],r=ageRows.find(x=>age>=x.min&&age<=x.max),g=P[p][1]==='Female'?0:P[p][1]==='Male'?1:2;if(r)r.values[g]++;});
 function ageChart(){const max=Math.max(1,...ageRows.flatMap(r=>r.values)),w=620,h=235;let svg=`<svg class="chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="Distinct patients by age group and recorded gender">`;
 ageRows.forEach((r,i)=>{r.values.forEach((v,j)=>{const height=v/max*165;svg+=`<rect x="${50+i*115+j*22}" y="${185-height}" width="19" height="${height}" rx="3" fill="${colors[j]}"><title>${r.label} · ${['Female','Male','Other / not recorded'][j]}: ${fmt(v)}</title></rect>`;});svg+=`<text x="${82+i*115}" y="210" text-anchor="middle" fill="#80768b" font-size="12">${r.label}</text>`;});return svg+'</svg>'+legend(['Female','Male','Other / not recorded']);}
 const completedSet=new Set(s.completed);
 const cats=D.categories.map((label,i)=>({label:shortCats[i],value:new Set(D.treatments.filter(t=>t[1]===i&&completedSet.has(t[0])).map(t=>A[t[0]][0])).size}));
 const byLoc=D.locations.map((l,j)=>{const ids=s.completed.filter(i=>A[i][1]===j);return [esc(l[0]),fmt(new Set(ids.map(i=>A[i][0])).size),fmt(ids.length),fmt(new Set(ids.filter(i=>P[A[i][0]][2]>=s.first).map(i=>A[i][0])).size)];}).filter((_,j)=>locMatch(j));
 $('content').innerHTML='<div class="grid">'+panel('Patient age & recorded gender','Distinct patients · age at first selected completed visit',ageChart())+panel('Explore dental care','Category measures apply to completed services in this period','<div id="care-panel"></div>')+panel('Patients treated by care category','Patients may appear in more than one category.',bars(cats))+panel('Compare locations','Group patient totals are deduplicated; branch counts are not additive.',table(['Location','Patients seen','Completed visits','New patients'],byLoc))+'</div>';
 renderCategory(completedSet);
}
function renderCategory(completedSet){
 const t=D.treatments.filter(t=>t[1]===category&&completedSet.has(t[0])),people=new Set(t.map(t=>A[t[0]][0]));
 $('care-panel').innerHTML=`<div class="care"><img src="images/${D.images[category]}" alt="Illustrative dental model for ${esc(D.categories[category])}"><div class="care-info"><label>Care category<select id="category">${D.categories.map((c,i)=>`<option value="${i}" ${i===category?'selected':''}>${esc(c)}</option>`).join('')}</select></label><p>${categoryDescriptions[category]}</p><div class="care-numbers"><div><strong>${fmt(people.size)}</strong><span>Patients treated</span></div><div><strong>${fmt(t.length)}</strong><span>Services completed</span></div><div><strong>${money(sum(t.map(t=>t[2])))}</strong><span>Net service charges</span></div></div></div></div>`;
 $('category').addEventListener('change',e=>{category=Number(e.target.value);renderCategory(completedSet);});
}
function trends(s){
 const comparison=comparisonText(s);
 const cancelled=s.selected.filter(i=>A[i][4]===1).length,missed=s.selected.filter(i=>A[i][4]===2).length,late=s.selected.filter(i=>A[i][7]).length;
 const available=D.available.filter(x=>dateMatch(x[0])&&locMatch(x[1])),capacity=sum(available.map(x=>x[2]));
 const recall=recallSnapshot(s.cutoff),overdue=recall.filter(q=>isOverdue(q,s.cutoff)).length;
 $('metrics').innerHTML=metric('Scheduled appointments',fmt(s.selected.length),'All booking outcomes')+metric('Completed visits',fmt(s.completed.length),comparison.visits || 'Care delivered')+metric('Missed appointments',fmt(missed),pct(missed/(s.completed.length+missed))+' of completed + missed')+metric('Cancelled appointments',fmt(cancelled),fmt(late)+' with less than 24h notice')+metric('Actual care utilization',pct(sum(s.completed.map(i=>A[i][5]))/capacity),'Treatment minutes ÷ available minutes')+metric('Overdue recall patients',fmt(overdue),'Latest plan · as of '+s.cutoff);
 const activity=s.monthly.map(m=>({key:m,label:periodLabel(m),values:[s.completed.filter(i=>A[i][2].startsWith(m)).length,s.selected.filter(i=>A[i][2].startsWith(m)&&A[i][4]===2).length,s.selected.filter(i=>A[i][2].startsWith(m)&&A[i][4]===1).length]}));
 const ret=s.monthly.map(m=>{const set=new Set(s.completed.filter(i=>A[i][2].startsWith(m)).map(i=>A[i][0]));return {key:m,label:periodLabel(m),values:[[...set].filter(p=>P[p][2].startsWith(m)).length,[...set].filter(p=>P[p][2].slice(0,7)<m).length]};});
 const heat=s.monthly.map(m=>{const cells=[1,2,3,4,5].map(day=>{const dow=d=>new Date(d+'T12:00:00Z').getUTCDay();const cap=sum(available.filter(x=>x[0].startsWith(m)&&dow(x[0])===day).map(x=>x[2]));const booked=sum(s.selected.filter(i=>A[i][2].startsWith(m)&&dow(A[i][2])===day).map(i=>A[i][6]));const ratio=cap?booked/cap:null;return `<td style="background:rgba(113,65,188,${ratio===null?0:Math.min(.65,ratio*.65)})" title="Reserved time includes cancelled bookings and turnover">${ratio===null?'—':pct(ratio)}</td>`;});return '<tr><td>'+periodLabel(m)+'</td>'+cells.join('')+'</tr>';}).join('');
 const heatTable='<div class="table-scroll"><table class="heat"><thead><tr>'+['Month','Mon','Tue','Wed','Thu','Fri'].map(x=>'<th>'+x+'</th>').join('')+'</tr></thead><tbody>'+heat+'</tbody></table></div>';
 const recallRows=s.monthly.map(m=>{const days=s.dates.filter(d=>d.startsWith(m)),cutoff=days.at(-1),rr=recallSnapshot(cutoff);return {label:periodLabel(m),key:m,values:[rr.filter(q=>isOverdue(q,cutoff)).length]};});
 $('content').innerHTML='<div class="grid">'+panel('Appointment activity over time','Counts · select a point to focus on its month',chart(activity,['Completed','No-show','Cancelled'],{click:true}))+panel('New and returning patients','Monthly distinct patients · not additive across months',chart(ret,['New','Returning'],{click:true}))+panel('Booked capacity by weekday','Reserved minutes ÷ available minutes · includes turnover and cancellations',heatTable)+panel('Overdue follow-ups','Monthly snapshot · overdue does not mean the patient has left',chart(recallRows,['Overdue patients'],{click:true}))+'</div>';
}
function weekOf(d){const dt=new Date(d+'T00:00:00Z'),day=(dt.getUTCDay()+6)%7;dt.setUTCDate(dt.getUTCDate()-day);return dt.toISOString().slice(0,10);}
function finance(s){
 const comparison=comparisonText(s);
 const visits=new Set(s.completed),charges=sum(s.completed.map(i=>netByVisit[i]));
 const receipts=D.payments.filter(p=>dateMatch(p[1])&&locMatch(A[p[0]][1])),costs=D.costs.filter(c=>dateMatch(c[0])&&locMatch(c[1]));
 const received=sum(receipts.map(p=>p[2])),cost=sum(costs.map(c=>c[3])),profit=charges-cost;
 const paidForVisits=sum(D.payments.filter(p=>visits.has(p[0])&&p[1]<=s.cutoff).map(p=>p[2]));
 $('metrics').innerHTML=metric('Net service revenue',money(charges),comparison.revenue || 'After discounts; before operating costs')+metric('Money received',money(received),'Receipts dated in selected period')+metric('Operating costs',money(cost),'Recorded costs allocated to this period')+metric('Operating profit',money(profit),(comparison.profit || 'Revenue minus operating costs')+' · before loss estimates')+metric('Operating margin',pct(profit/charges),'Before estimated collection losses')+metric('Unpaid at period end',money(charges-paidForVisits),'Selected visits · gross balance at '+s.cutoff);
 const cashPaid=sum(D.cashExpenses.filter(x=>dateMatch(x[0])&&locMatch(x[1])).map(x=>x[2]));
 const snapshot=D.financialMonths.filter(x=>x.Month===s.cutoff.slice(0,7)&&locMatch(D.locationIds.indexOf(x['Location ID'])));
 const financialSum=key=>Math.round(sum(snapshot.map(x=>Number(x[key])))*100);
 const cashPanel=panel('Cash collected and paid','Payment dates in the selected period · modeled operations only',table(['Money received','Operating payments','Operating cash surplus'],[[money(received),money(cashPaid),money(received-cashPaid)]])+'<p class="notice">Cash surplus is separate from profit. It excludes equipment purchases, loans, income tax and owner withdrawals; it is not the bank balance or owner take-home pay. Depreciation and loss provisions are not cash payments.</p>','full');
 const aging=D.financialPolicy.age_bands.map(b=>[b.label,money(Math.round(sum(D.financialAging.filter(x=>x['As Of']===s.cutoff&&x['Invoice Age']===b.label&&locMatch(D.locationIds.indexOf(x['Location ID']))).map(x=>Number(x['Gross Balance'])))*100)),pct(b.loss_rate)]);
 const riskExpense=sum(D.riskCosts.filter(x=>dateMatch(x[0])&&locMatch(x[1])).map(x=>x[2]));
 const balancePanel='<details class="panel full"><summary><strong>Collection-risk scenario · optional</strong></summary><p class="sub">What if part of the unpaid bills cannot be collected? These are assumptions, not recorded losses.</p>'+table(['Assumed loss expense','Scenario profit','Scenario margin'],[[money(riskExpense),money(profit-riskExpense),pct((profit-riskExpense)/charges)]])+'<p class="sub">All tracked visits up to '+s.cutoff+' · selected locations, including earlier visits</p>'+table(['Total unpaid','Assumed loss allowance','Scenario collectible balance'],[[money(financialSum('Gross Receivables')),money(financialSum('Scenario Loss Allowance')),money(financialSum('Scenario Net Receivables'))]])+table(['Age since treatment','Unpaid balance','Assumed loss rate'],aging)+'<p class="notice">The main profit uses recorded operating costs, before estimated collection losses. This separate scenario deducts the change in an assumed loss allowance. It does not change receipts or cancel bills. Age alone does not prove a bill is overdue. Records end on 2025-12-31.</p></details>';
 const cat=D.categories.map((x,i)=>({label:shortCats[i],value:sum(D.treatments.filter(t=>t[1]===i&&visits.has(t[0])).map(t=>t[2]))}));
 const byCost=D.costNames.map((x,i)=>({label:x,value:sum(costs.filter(c=>c[2]===i).map(c=>c[3]))})).filter(x=>x.value).sort((a,b)=>b.value-a.value);
 const monthly=s.monthly.map(m=>{const rev=sum(s.completed.filter(i=>A[i][2].startsWith(m)).map(i=>netByVisit[i])),cos=sum(costs.filter(c=>c[0].startsWith(m)).map(c=>c[3]));return {key:m,label:periodLabel(m),values:[rev,cos,rev-cos]};});
 const rows=D.locations.map((l,j)=>{const rev=sum(s.completed.filter(i=>A[i][1]===j).map(i=>netByVisit[i])),co=sum(costs.filter(c=>c[1]===j).map(c=>c[3])),cash=sum(receipts.filter(p=>A[p[0]][1]===j).map(p=>p[2]));return [esc(l[0]),money(rev),money(cash),money(co),money(rev-co),pct((rev-co)/rev)];}).filter((_,j)=>locMatch(j));
 const weekly=new Map();s.dates.forEach(d=>{const w=weekOf(d);if(!weekly.has(w))weekly.set(w,{week:w,revenue:0,cost:0,receipts:0,days:0});weekly.get(w).days++;});
 s.completed.forEach(i=>weekly.get(weekOf(A[i][2])).revenue+=netByVisit[i]);costs.forEach(c=>weekly.get(weekOf(c[0])).cost+=c[3]);receipts.forEach(p=>weekly.get(weekOf(p[1])).receipts+=p[2]);
 latestExport=[...weekly.values()].map(x=>({'Week Starting':x.week,'Days Included':x.days,'Service Revenue':(x.revenue/100).toFixed(2),'Money Received':(x.receipts/100).toFixed(2),'Operating Costs':(x.cost/100).toFixed(2),'Operating Profit':((x.revenue-x.cost)/100).toFixed(2)}));
 const weekRows=[...weekly.values()].slice(-12).map(x=>[x.week+(x.days<7?' *':''),money(x.revenue),money(x.receipts),money(x.cost),money(x.revenue-x.cost)]);
 $('content').innerHTML='<div class="grid">'+panel('Revenue by care category','Service mix explains revenue differences; it does not establish profitability.',bars(cat,{currency:true}))+panel('Revenue, costs & operating profit','Monthly values · before estimated collection losses',chart(monthly,['Revenue','Costs','Profit'],{currency:true,click:true}))+panel('Compare branch finances','Before estimated collection losses · shared administration split equally',table(['Location','Revenue','Receipts','Costs','Profit','Margin'],rows),'full')+cashPanel+panel('Operating cost breakdown','Recorded costs recognized in the selected period',bars(byCost,{currency:true}))+panel('Weekly management report','Latest 12 selected weeks · * means partial week',`<div class="panel-head"><p class="notice">CAD · all selected locations combined</p><button id="download">Download all weeks</button></div>`+table(['Week starting','Revenue','Receipts','Costs','Profit'],weekRows)+'<p class="notice">Profit is before estimated collection losses, income tax and financing costs. Unpaid charges are already included in revenue; do not add them to profit again. Profit is not cash flow or owner take-home pay.</p>')+balancePanel+'</div>';
 $('download').addEventListener('click',()=>{const h=Object.keys(latestExport[0]||{}),csv=[h.join(','),...latestExport.map(r=>h.map(k=>r[k]).join(','))].join('\n');const url=URL.createObjectURL(new Blob([csv],{type:'text/csv'}));const a=document.createElement('a');a.href=url;a.download='dental-clinic-weekly-report.csv';a.click();URL.revokeObjectURL(url);});
}
function render(){
 const s=getState();$('period').textContent=s.dates.length?s.first+' → '+s.cutoff:'No dates in this selection';
 const titles={overview:['Patient Overview','Who visits our clinics, and which services do they use?'],trends:['Key Trends','What is changing, and where should we investigate?'],finance:['Treatment & Costs','What did we earn, receive and spend in the selected period?']};
 [$('title').textContent,$('subtitle').textContent]=titles[page];
 if(!s.dates.length){$('metrics').innerHTML='';$('content').innerHTML='<div class="panel empty">No data for this period. Choose another year or month.</div>';return;}
 ({overview,trends,finance})[page](s);
 document.querySelectorAll('[data-month]').forEach(el=>{function go(){const m=el.dataset.month;$('year').value=m.slice(0,4);$('month').value=m.slice(5,7);render();}el.addEventListener('click',go);el.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();go();}});});
}
function comparisonText(s){
 const year=$('year').value,month=$('month').value;
 if(year==='all')return {};
 const prev=String(Number(year)-1),match=d=>d.slice(0,4)===prev&&(month==='all'||d.slice(5,7)===month);
 if(!allDates.some(match))return {visits:'No earlier-year data',revenue:'No earlier-year data',profit:'No earlier-year data'};
 const label=month==='all'?prev:months[Number(month)-1]+' '+prev;
 const ids=[];A.forEach((a,i)=>{if(a[4]===0&&locMatch(a[1])&&match(a[2]))ids.push(i);});
 const revenue=sum(s.completed.map(i=>netByVisit[i])),oldRevenue=sum(ids.map(i=>netByVisit[i]));
 const profit=revenue-sum(D.costs.filter(c=>dateMatch(c[0])&&locMatch(c[1])).map(c=>c[3]));
 const oldProfit=oldRevenue-sum(D.costs.filter(c=>match(c[0])&&locMatch(c[1])).map(c=>c[3]));
 const change=(now,before,down,up)=>before>0?(now===before?'No change from '+label:(Math.abs(now-before)/before*100).toFixed(1)+'% '+(now<before?down:up)+' than '+label):'No comparison available';
 const delta=profit-oldProfit;
 return {visits:change(s.completed.length,ids.length,'fewer','more'),revenue:change(revenue,oldRevenue,'lower','higher'),profit:delta===0?'No change from '+label:money(Math.abs(delta))+' '+(delta<0?'less':'more')+' than '+label};
}
document.querySelectorAll('.tab').forEach(b=>b.addEventListener('click',()=>{page=b.dataset.page;document.querySelectorAll('.tab').forEach(x=>{x.classList.toggle('active',x===b);if(x===b)x.setAttribute('aria-current','page');else x.removeAttribute('aria-current');});render();}));
['year','month','location'].forEach(id=>$(id).addEventListener('change',render));
$('reset').addEventListener('click',()=>{['year','month','location'].forEach(id=>$(id).value='all');category=0;render();});
render();
