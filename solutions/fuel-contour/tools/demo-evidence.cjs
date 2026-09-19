// Real screenshots and measured warm browser timings. No screenshot data are edited.
const {chromium:pw}=require('playwright-core');const chromium=require('@sparticuz/chromium');
const fs=require('fs'),path=require('path'),os=require('os'),crypto=require('crypto');
const {execFileSync}=require('child_process');
const root=path.resolve(__dirname,'..'),dest=path.join(root,'docs/evidence');
const hash=b=>crypto.createHash('sha256').update(b).digest('hex');
function statistics(values){const sorted=[...values].sort((a,b)=>a-b),q=p=>sorted[Math.ceil(p*sorted.length)-1];return {samples_ms:values,min_ms:sorted[0],median_ms:q(.5),p95_ms:q(.95),max_ms:sorted.at(-1)};}
(async()=>{
 fs.mkdirSync(dest,{recursive:true});const browser=await pw.launch({executablePath:await chromium.executablePath(),args:chromium.args,headless:true});
 const page=await browser.newPage({viewport:{width:1440,height:1080}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const url=process.env.SHOWCASE_URL||'http://127.0.0.1:8000';await page.goto(url);
 await page.emulateMedia({reducedMotion:'reduce'});
 await page.waitForFunction(()=>document.querySelector('#appStatus').textContent.startsWith('Рассчитано'));
 const expectedResponse=JSON.parse(fs.readFileSync(path.join(root,'results/recourse/delay-90.json'))).after.summary;
 const data=await page.evaluate(async()=>await(await fetch('/api/showcase')).json());
 const examples=[];
 for(const mode of ['base','stress','prepared','prepared_base']){
  await page.locator(`[data-mode="${mode}"]`).click();
  const expected=data.architectures.lunar.runs[mode].summary;
  const text=await page.locator('#kpis').textContent();
  const rendered=Number(expected.shortage_t).toLocaleString('ru-RU',{maximumFractionDigits:2});
  if(!text.includes(rendered))throw Error('Rendered shortage differs from API');
  const name=`ui-${mode}.png`;await page.locator('#kpis').screenshot({path:path.join(dest,name)});
  examples.push({mode,image:name,summary:expected,sha256:hash(fs.readFileSync(path.join(dest,name)))});
 }
 await page.locator('[data-mode="base"]').click();await page.evaluate(()=>scrollTo({top:0,behavior:'instant'}));
 await page.screenshot({path:path.join(dest,'website.png')});
 const switches=[],requests=[];let received=null;
 for(let i=0;i<18;i++){
  const mode=i%2?'base':'stress';
  const elapsed=await page.evaluate(async mode=>{const t=performance.now();document.querySelector(`[data-mode="${mode}"]`).click();await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));return performance.now()-t;},mode);
  if(i>=3)switches.push(elapsed);
 }
 for(let i=0;i<18;i++){
  const result=await page.evaluate(async plan=>{const t=performance.now();const response=await fetch('/api/recourse',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({plan,event_year:2038,delivery_share:0,observed_after_days:90,max_emergency_t:80})});if(!response.ok)throw Error('HTTP '+response.status);const data=await response.json();return {elapsed:performance.now()-t,summary:data.after.summary,unchanged:data.original_commitments_unchanged&&data.prefix_unchanged_until_arrival};},data.architectures.lunar.plan);
  if(!result.unchanged||Math.abs(result.summary.shortage_t-expectedResponse.shortage_t)>1e-6)throw Error('Response benchmark produced unexpected result');
  if(i>=3)requests.push(result.elapsed);received=result.summary;
 }
 await page.locator('#observation').fill('90');await page.locator('#runResponse').click();await page.waitForFunction(()=>!document.querySelector('#downloadResponse').disabled);
 await page.locator('.response-output').screenshot({path:path.join(dest,'ui-response-90.png')});
 const report={status:'TEAM_MEASUREMENT',source_revision:execFileSync('git',['rev-parse','HEAD'],{cwd:root,encoding:'utf8'}).trim(),environment:{platform:os.platform(),arch:os.arch(),cpu:os.cpus()[0].model,node:process.version,browser:browser.version(),viewport:{width:1440,height:1080}},method:{warmup:3,repeats:15,percentile:'nearest rank; ceil(p*n)-1 in sorted samples',ui:'Warm cached BASE/STRESS switch, programmatic DOM click through two animation frames. No network/model run.',api:'Browser fetch POST /api/recourse through JSON decode; 2038 Lunar full outage, delay 90. Warm server, sequential requests, no concurrent test workloads.',scope:'Local browser and local server. Not end-user Internet latency, cold start, throughput, load test or SLA.'},timings:{switch:statistics(switches),recourse:statistics(requests)},response_summary:received,examples,source_hashes:{}};
 for(const folder of ['web','fuel'])for(const file of fs.readdirSync(path.join(root,folder)).sort()){const rel=folder+'/'+file;if(fs.statSync(path.join(root,rel)).isFile())report.source_hashes[rel]=hash(fs.readFileSync(path.join(root,rel)));}
 fs.writeFileSync(path.join(dest,'browser-measurements.json'),JSON.stringify(report,null,2)+'\n');
 if(errors.length)throw Error(errors.join('\n'));await browser.close();console.log(JSON.stringify(report.timings,null,2));
})().catch(e=>{console.error(e);process.exit(1)});
