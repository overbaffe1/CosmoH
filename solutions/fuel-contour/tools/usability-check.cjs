// Optional real-browser UX and axe-core accessibility regression. See RUNBOOK.
const {chromium:pw}=require('playwright-core');
const chromium=require('@sparticuz/chromium');
const axe=require('axe-core');const fs=require('fs');const path=require('path');
(async()=>{
 const root=path.resolve(__dirname,'..'),base=process.env.SHOWCASE_URL||'http://127.0.0.1:8000/demo';
 const browser=await pw.launch({executablePath:await chromium.executablePath(),args:chromium.args,headless:true});
 const page=await browser.newPage({viewport:{width:1440,height:1080}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const check=(ok,message)=>{if(!ok)throw Error(message)};
 const audits=[];
 await page.goto(base);await page.waitForFunction(()=>document.querySelector('#appStatus').textContent.startsWith('Рассчитано'));
 check(await page.locator('html').getAttribute('data-theme')==='light','First visit must be light');
 const kpis=await page.locator('#kpis').textContent();
 for(const theme of ['light','dark']){
  if(theme==='dark')await page.locator('#themeToggle').click();
  check(await page.locator('#kpis').textContent()===kpis,'Theme changed model numbers');
  await page.addScriptTag({content:axe.source});
  const result=await page.evaluate(async()=>await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}}));
  audits.push({page:'showcase',theme,violations:result.violations,incomplete:result.incomplete.map(v=>({id:v.id,nodes:v.nodes.length}))});
  fs.writeFileSync(path.join(root,'results/accessibility.json'),JSON.stringify(audits,null,2));
  await page.screenshot({path:path.join(root,`results/showcase-${theme}.png`),fullPage:true});
 }
 await page.reload();check(await page.locator('html').getAttribute('data-theme')==='dark','Theme did not persist');
 await page.goto(new URL('/planner',base).href);check(await page.locator('html').getAttribute('data-theme')==='dark','Planner lost theme');
 await page.locator('#themeToggle').click();await page.goto(base);
 await page.waitForFunction(()=>document.querySelector('#appStatus').textContent.startsWith('Рассчитано'));
 check(await page.locator('html').getAttribute('data-theme')==='light','Shared preference not restored');
 await page.locator('[data-mode="prepared_base"]').click();
 check((await page.locator('#decisionMeaning').textContent()).includes('переполняет'),'Explanation missing');
 await page.reload();await page.waitForFunction(()=>document.querySelector('#appStatus').textContent.startsWith('Рассчитано'));
 check(new URL(page.url()).searchParams.get('mode')==='prepared_base','Mode not preserved in URL');
 check((await page.locator('#decisionMeaning').textContent()).includes('переполняет'),'Reload lost selection');
 await page.locator('#resetView').click();
 check(new URL(page.url()).searchParams.get('mode')==='base','Reset did not restore baseline');
 await page.locator('.chart-values summary').click();check(await page.locator('#chartData tbody tr').count()===6,'Accessible data missing');
 await page.locator('.chart-values summary').click();
 for(const width of [390,768,1440]){
  await page.setViewportSize({width,height:960});
  check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Page overflow at '+width);
 }
 await page.setViewportSize({width:1440,height:1080});await page.evaluate(()=>scrollTo({top:0,behavior:'instant'}));await page.waitForFunction(()=>scrollY===0);
 await page.screenshot({path:path.join(root,'results/showcase-light-viewport.png')});
 await page.goto(new URL('/presentation',base).href);await page.locator('#slidePicker').selectOption('2');
 check(await page.locator('#slideCount').textContent()==='3 / 8','Slide picker broken');
 check(await page.locator('#notesToggle').count()===0&&await page.locator('#speakerPanel').count()===0,'Presenter prompt must not be in audience deck');
 await page.screenshot({path:path.join(root,'results/presentation-process.png')});
 await page.setViewportSize({width:390,height:844});await page.waitForFunction(()=>document.documentElement.scrollWidth<=innerWidth);
 await page.emulateMedia({media:'print'});check(await page.locator('article:visible').count()===8,'Print must contain 8 audience slides');
 // A privacy-restricted browser must still boot, with in-memory theme switching.
 const restricted=await browser.newContext();await restricted.addInitScript(()=>{Storage.prototype.getItem=()=>{throw Error('Storage blocked')};Storage.prototype.setItem=()=>{throw Error('Storage blocked')};});
 const offline=await restricted.newPage();offline.on('pageerror',e=>errors.push(e.message));await offline.goto(base);await offline.locator('#themeToggle').click();
 check(await offline.locator('html').getAttribute('data-theme')==='dark','Blocked storage broke toggle');
 fs.writeFileSync(path.join(root,'results/accessibility.json'),JSON.stringify(audits,null,2));
 const failures=audits.flatMap(a=>a.violations.filter(v=>['serious','critical'].includes(v.impact)).map(v=>`${a.theme}: ${v.id} (${v.nodes.length})`));
 await browser.close();check(!errors.length,errors.join('\n'));check(!failures.length,failures.join('\n'));
 console.log('PASS usability: themes/persistence/privacy, explanations, data tables, responsive, slide picker/no prompts/print; axe serious/critical: 0');
})().catch(e=>{console.error(e);process.exit(1)});
