'use strict';
let plan=null, result=null, caseData=null, busy=false;
let lastScenario='BASE', lastResearch=null, lastCasePatch=null, lastAlternative=null, controlBackup=null;
const $=id=>document.getElementById(id);
const clone=value=>JSON.parse(JSON.stringify(value));
const fmt=(value,n=2)=>typeof value==='number'?value.toLocaleString('ru-RU',{maximumFractionDigits:n}):String(value??'—');
const esc=value=>String(value??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const request=()=>({plan,scenario_id:lastScenario,research_scenario:lastResearch,research_case_patch:lastCasePatch});
async function api(path,body){
  const response=await fetch(path,body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{});
  if(!response.ok){const error=await response.json();throw Error(typeof error.detail==='string'?error.detail:JSON.stringify(error.detail));}
  return response.json();
}
async function action(fn){
  if(busy)return;
  busy=true;document.querySelectorAll('button').forEach(b=>b.disabled=true);$('status').textContent='Расчёт…';
  try{await fn();$('status').textContent='Готово · результаты рассчитаны ядром';}
  catch(error){$('status').textContent='Ошибка: '+error.message;}
  finally{busy=false;document.querySelectorAll('button').forEach(b=>b.disabled=false);}
}
function table(id,rows,columns){
  $(id).innerHTML='<table><thead><tr>'+columns.map(([k,n])=>'<th>'+esc(n)+'</th>').join('')+'</tr></thead><tbody>'+rows.map(r=>'<tr>'+columns.map(([k])=>'<td>'+esc(k==='year'?r[k]:fmt(r[k]))+'</td>').join('')+'</tr>').join('')+'</tbody></table>';
}
function chart(id,rows,series){
  const w=600,h=220,l=42,r=14,t=15,b=28,max=Math.max(1,...rows.flatMap(d=>series.map(s=>Number(d[s[0]])||0)))*1.1;
  const x=i=>l+i*(w-l-r)/Math.max(1,rows.length-1),y=v=>h-b-v/max*(h-t-b);
  let svg='';
  for(let i=0;i<4;i++){const v=max*i/3;svg+=`<line x1="${l}" x2="${w-r}" y1="${y(v)}" y2="${y(v)}" stroke="#263747"/><text x="0" y="${y(v)+4}" fill="#92a7b8" font-size="11">${Math.round(v)}</text>`;}
  for(const [key,color,dash] of series)svg+=`<polyline points="${rows.map((v,i)=>x(i)+','+y(v[key])).join(' ')}" fill="none" stroke="${color}" stroke-width="2" ${dash?'stroke-dasharray="5 5"':''}/>`;
  const years=[...new Set(rows.map(row=>row.year))];
  years.forEach(year=>{const index=rows.findIndex(row=>row.year===year);svg+=`<text x="${x(index)}" y="217" fill="#92a7b8" font-size="11" text-anchor="middle">${year}</text>`;});
  $(id).innerHTML=svg;
}
function setDataOptions(data){
  const year=$('year').value,source=$('source').value;
  $('year').innerHTML=data.demand.map(r=>`<option>${r.year}</option>`).join('');
  $('source').innerHTML=data.supply_sources.map(r=>`<option value="${esc(r.source_id)}">${esc(r.name)}</option>`).join('');
  if(data.demand.some(r=>String(r.year)===year))$('year').value=year;
  if(data.supply_sources.some(r=>r.source_id===source))$('source').value=source;
}
function render(r){
  result=r;lastScenario=r.scenario_id;
  lastResearch=r.provenance.scenario_definition.status==='TEAM_ASSUMPTION'?r.provenance.scenario_definition:null;
  $('scenarioBadge').textContent=r.scenario_id+' / '+r.plan_id;
  const m=r.summary;
  const metrics=[['Полная стоимость',fmt(m.total_cost_mln),'млн у.е. · включая начальный запас'],['Дефицит за горизонт',fmt(m.shortage_t),'тонн необслуженного спроса'],['Критический service level',fmt(m.min_critical_service*100)+'%','минимум по годам'],['Нарушения',m.violations,m.violations?'План требует проверки':'В принятой модели не обнаружены']];
  $('metrics').innerHTML=metrics.map(([label,num,unit],i)=>`<div class="card metric"><div class="label">${label}</div><div class="number ${i===3&&m.violations?'bad':''}">${num}</div><div class="muted small">${unit}</div></div>`).join('');
  $('economicSummary').textContent=`Приведённые расходы: ${fmt(m.discounted_cost_mln)} млн у.е. · реальная ставка ${fmt(m.discount_rate*100)}% · стоимость обслуженной тонны: ${fmt(m.cost_per_served_t_mln,3)} млн у.е./т · мин. коммерческий SL: ${fmt(m.min_commercial_service*100)}%. Денежные потоки — конец года, база — начало 2035.`;
  const design=plan.assumptions.design;
  $('designNote').classList.toggle('hidden',!design);
  $('designNote').textContent=design?'Отдельный план, подготовленный под известный стресс заранее. Не является мгновенной реакцией: объёмы фиксируются в указанные даты заказов. В BASE этот план также проверяется, но может оказаться избыточным.':'';
  table('balance',r.yearly_balance.map(x=>({...x,sl:100*x.total_service_level,criticalSL:100*x.critical_service_level,commercialSL:100*x.commercial_service_level})),[['year','Год'],['demand_t','Спрос, т'],['critical_demand_t','Критический спрос'],['opening_inventory_t','Начальный запас'],['reserve_required_t','Резерв 45 дней'],['delivered_t','Поставлено'],['losses_t','Потери'],['served_t','Обслужено'],['closing_inventory_t','Конечный запас'],['shortage_t','Дефицит'],['sl','Общий SL, %'],['criticalSL','Критический SL, %'],['commercialSL','Коммерческий SL, %']]);
  const bad=r.constraint_checks.filter(c=>!c.passed);
  if(bad.length)table('violations',bad,[['rule_id','Правило'],['period','Период'],['source','Источник'],['actual','Факт'],['operator','Оператор'],['limit','Порог'],['unit','Единица']]);
  else $('violations').innerHTML='<p class="ok">✓ Все проверки плана пройдены</p><p class="muted small">Это не заменяет независимый референсный gate.</p>';
  table('costs',r.financial_breakdown,[['year','Год'],['procurement_mln','Закупки'],['reservation_mln','Контракты'],['holding_mln','Хранение'],['fixed_opex_mln','OPEX'],['capex_mln','CAPEX'],['total_mln','Всего'],['discounted_total_mln','Приведённые']]);
  $('preCost').textContent='Подготовительный период: '+fmt(r.pre_horizon.total_mln)+' млн у.е. Уже включён в строку '+r.pre_horizon.cashflow_recognition_year+' и в полную сумму; не прибавлять повторно.';
  table('contracts',r.source_schedule.filter(row=>row.ordered_volume_t||row.reserved_capacity_t),[['year','Год'],['counterparty','Контрагент'],['source_capacity_t_per_year','Мощность, т/год'],['reserved_capacity_t','Резерв мощности'],['ordered_volume_t','Отбор, т'],['offered_volume_t','Предложено'],['delivered_volume_t','Принято'],['order_day','День заказа'],['lead_time_days','Lead time, дни'],['start_day','С начала суток'],['end_day','До суток'],['take_or_pay_share','Доля TOP'],['payable_volume_t','Оплачиваемые т'],['procurement_mln','Закупка, млн'],['reservation_mln','Резерв, млн']]);
  table('roadmap',r.roadmap.map(row=>({...row,funded:row.funded.join(', '),commissioned:row.commissioned.join(', '),orders:row.orders_to_commit.length})),[['year','Год'],['funded','Финансирование'],['commissioned','Ввод'],['capex_mln','CAPEX, млн'],['operating_budget_mln','Прочие расходы, млн'],['cumulative_capex_mln','Накопленный CAPEX'],['orders','Заказы к фиксации']]);
  chart('supplyChart',r.yearly_balance,[['delivered_t','#92e5bb'],['demand_t','#9bb7ff'],['served_t','#ffc078']]);
  chart('inventoryChart',r.inventory_trace.filter((_,i)=>i%5===0),[['inventory_t','#92e5bb'],['reserve_threshold_t','#ffc078',true],['capacity_t','#657887',true]]);
  setDataOptions(r.input_case);fillForm();
  $('provenance').textContent=JSON.stringify({CASE_INPUT:caseData.case,ACTIVE_CASE:r.input_case,TEAM_ASSUMPTION:plan.assumptions,SCENARIO:r.provenance.scenario_definition},null,2);
}
function sync(){
  $('editor').value=JSON.stringify(plan,null,2);fillForm();
  $('investmentEditor').innerHTML=caseData.case.investment_options.map(option=>{
    const id=option.investment_id,decision=plan.decisions.investments.find(x=>x.investment_id===id);
    return `<div class="card"><label><input id="invest-${id}" type="checkbox" ${decision?'checked':''}> ${esc(id)}</label><label for="decision-${id}">День полной оплаты</label><input id="decision-${id}" type="number" min="0" value="${decision?.decision_day??0}"><label for="commission-${id}">День ввода</label><input id="commission-${id}" type="number" min="0" value="${decision?.commission_day??0}"></div>`;
  }).join('');
}
function fillForm(){
  if(!plan)return;
  const source=$('source').value,year=Number($('year').value),d=plan.decisions;
  const order=d.supply_orders.find(x=>x.source_id===source&&x.year===year),reservation=d.capacity_reservations.find(x=>x.source_id===source&&x.year===year);
  $('ordered').value=order?.ordered_volume_t??0;$('reserved').value=reservation?.reserved_capacity_t??0;
  $('start').value=order?.start_day??1;$('end').value=order?.end_day??365;
  $('resStart').value=reservation?.start_day??1;$('resEnd').value=reservation?.end_day??365;
  $('orderday').value=order?.order_day??((year-2035)*365-730);
  $('stock').value=d.inventory_policy.opening_stock_t;$('rate').value=plan.assumptions.discount_rate.value;
}
function dirty(){
  result=null;lastAlternative=null;$('scenarioBadge').textContent='ПЛАН ИЗМЕНЁН · пересчёт нужен';
  $('status').textContent='План изменён. Видимые показатели относятся к предыдущему расчёту.';
  $('analysisCard').classList.add('hidden');
}
async function runControl(s){
  const r=await api('/api/run',{plan,scenario_id:s});
  lastCasePatch=null;render(r);
}
$('base').onclick=()=>action(()=>runControl('BASE'));
$('stress').onclick=()=>action(()=>runControl('MANDATORY_STRESS'));
$('loadDefault').onclick=()=>action(async()=>{
  plan=await api('/api/plans/'+$('strategy').value);lastCasePatch=null;lastAlternative=null;controlBackup=null;sync();await runControl(plan.scenario_id);
});
$('apply').onclick=()=>{
  const source_id=$('source').value,year=+$('year').value,d=plan.decisions;
  d.supply_orders=d.supply_orders.filter(x=>!(x.source_id===source_id&&x.year===year));
  d.capacity_reservations=d.capacity_reservations.filter(x=>!(x.source_id===source_id&&x.year===year));
  d.supply_orders.push({source_id,year,ordered_volume_t:+$('ordered').value,start_day:+$('start').value,end_day:+$('end').value,order_day:+$('orderday').value});
  d.capacity_reservations.push({source_id,year,reserved_capacity_t:+$('reserved').value,start_day:+$('resStart').value,end_day:+$('resEnd').value});
  d.inventory_policy.opening_stock_t=+$('stock').value;plan.assumptions.discount_rate.value=+$('rate').value;
  sync();dirty();
};
$('applyInvestments').onclick=()=>{
  plan.decisions.investments=caseData.case.investment_options.filter(option=>$('invest-'+option.investment_id).checked).map(option=>({investment_id:option.investment_id,decision_day:+$('decision-'+option.investment_id).value,commission_day:+$('commission-'+option.investment_id).value}));
  sync();dirty();
};
$('applyJSON').onclick=()=>action(async()=>{
  const p=JSON.parse($('editor').value),r=await api('/api/run',{...request(),plan:p});
  plan=p;lastAlternative=null;sync();render(r);
});
$('year').onchange=$('source').onchange=fillForm;
$('researchRun').onclick=()=>action(async()=>{
  const research=JSON.parse($('researchEditor').value);
  render(await api('/api/run',{plan,research_scenario:research,research_case_patch:lastCasePatch}));
});
$('runCaseCopy').onclick=()=>action(async()=>{
  const patch=JSON.parse($('caseEditor').value);
  const r=await api('/api/run',{plan,research_scenario:{scenario_id:'TEAM_INPUT_COPY',status:'TEAM_ASSUMPTION'},research_case_patch:patch});
  if(!controlBackup)controlBackup=clone(plan);
  lastCasePatch=patch;lastAlternative=null;render(r);
});
$('restoreControl').onclick=()=>action(async()=>{
  if(controlBackup)plan=clone(controlBackup);
  lastCasePatch=null;lastAlternative=null;controlBackup=null;sync();await runControl('BASE');
});
function download(blob,name){
  const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);
}
function downloadJSON(value,name){download(new Blob([JSON.stringify(value,null,2)],{type:'application/json'}),name);}
$('save').onclick=()=>downloadJSON(plan,'fuel-plan.json');
$('saveProject').onclick=()=>downloadJSON({format:'fuel-project-v1',...request()},'fuel-project.json');
$('open').onclick=()=>$('file').click();
$('file').onchange=()=>action(async()=>{
  const data=JSON.parse(await $('file').files[0].text());
  let body;
  if(data.format==='fuel-project-v1')body=data;
  else if(data.input_plan){
    body={plan:data.input_plan,scenario_id:data.scenario_id};
    if(data.provenance.scenario_definition.status==='TEAM_ASSUMPTION')body.research_scenario=data.provenance.scenario_definition;
    if(data.input_case.status==='TEAM_ASSUMPTION')body.research_case_patch={basis:data.input_case.research_provenance?.basis||'Restored research copy',demand:data.input_case.demand,supply_sources:data.input_case.supply_sources};
  }else body={plan:data,scenario_id:['BASE','MANDATORY_STRESS'].includes(data.scenario_id)?data.scenario_id:'BASE'};
  const r=await api('/api/run',body);plan=body.plan;lastCasePatch=body.research_case_patch??null;lastAlternative=null;controlBackup=null;
  sync();render(r);$('file').value='';
});
$('export').onclick=()=>action(async()=>{
  if(!result)throw Error('Сначала пересчитайте изменённый план, чтобы UI совпадал с экспортом');
  const r=await fetch('/api/export',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...request(),alternative_plan:lastAlternative})});
  if(!r.ok)throw Error(await r.text());download(await r.blob(),'fuel-'+lastScenario+'.zip');
});
function showAnalysis(title,data){
  $('analysisCard').classList.remove('hidden');$('analysisTitle').textContent=title;
  $('analysisResult').textContent=JSON.stringify(data,null,2);$('analysisTable').innerHTML='';$('analysisCard').scrollIntoView({behavior:'smooth',block:'start'});
}
document.querySelectorAll('[data-analysis]').forEach(button=>button.onclick=()=>action(async()=>{
  const kind=button.dataset.analysis,data=await api('/api/analysis/'+kind,{...request(),count:100,seed:2035,dependence:button.dataset.dependence||'independent'});
  showAnalysis(button.textContent,data);
  if(kind==='sensitivity')table('analysisTable',data.points,[['factor','Множитель спроса'],['total_cost_mln','Стоимость'],['min_inventory_t','Мин. запас'],['shortage_t','Дефицит, т'],['violations','Нарушения']]);
  if(kind==='risks')table('analysisTable',data,[['risk_id','Риск'],['physical_consequence_t','Δ дефицит, т'],['financial_consequence_mln','Δ стоимость'],['mitigation_baseline_cost_mln','Цена меры в BASE, Δ млн'],['mitigation_incremental_cost_mln','Эффект в риске, Δ млн'],['owner','Владелец']]);
  if(kind==='parameters')table('analysisTable',data.points,[['parameter','Параметр'],['value','Значение'],['total_cost_mln','Стоимость'],['discounted_cost_mln','Приведённые'],['min_inventory_t','Мин. запас'],['shortage_t','Дефицит'],['violations','Нарушения']]);
  if(kind==='attribution')table('analysisTable',data.steps,[['step','Добавленный фактор'],['delta_cost_mln','Δ стоимость'],['delta_shortage_t','Δ дефицит'],['violations','Нарушения']]);
}));
$('compare').onclick=()=>action(async()=>{
  if(lastCasePatch)throw Error('Контрольное BASE/STRESS сравнение: сначала восстановите исходный проект. Сравнение копии будет в её экспорте.');
  const b=await api('/api/run',{plan,scenario_id:'BASE'}),s=await api('/api/run',{plan,scenario_id:'MANDATORY_STRESS'});
  showAnalysis('Один план. Два сценария.',{BASE:b.summary,MANDATORY_STRESS:s.summary});
  table('analysisTable',[{scenario:'BASE',...b.summary},{scenario:'STRESS',...s.summary}],[['scenario','Сценарий'],['total_cost_mln','Стоимость'],['shortage_t','Дефицит, т'],['min_total_service','Мин. общий SL'],['violations','Нарушения']]);
});
$('compareDecisions').onclick=()=>action(async()=>{
  const alternative=await api('/api/plans/'+$('alternativeStrategy').value);
  alternative.assumptions.discount_rate=clone(plan.assumptions.discount_rate); // one disclosed comparison basis

  const data=await api('/api/analysis/adaptation',{...request(),alternative_plan:alternative});lastAlternative=alternative;
  showAnalysis('Цена перепланирования: отдельные решения, не мгновенная реакция',data);
  table('analysisTable',data.matrix,[['plan_role','Роль плана'],['scenario_id','Среда'],['total_cost_mln','Стоимость'],['shortage_t','Дефицит'],['min_commercial_service','Мин. коммерческий SL'],['violations','Нарушения']]);
});
action(async()=>{
  caseData=await api('/api/case');setDataOptions(caseData.case);
  $('caseEditor').value=JSON.stringify({basis:'TEAM_ASSUMPTION: исследовательская копия, укажите основание изменений',demand:caseData.case.demand,supply_sources:caseData.case.supply_sources},null,2);
  plan=await api('/api/plans/earth');sync();await runControl('BASE');
});
