"""Offline presentation design: semantic HTML/SVG and editable PowerPoint shapes."""
import base64
import html
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def fmt(v):
    return f'{v:,.2f}'.replace(',', ' ').replace('.', ',')


ORBIT='''<svg viewBox="0 0 480 470" xmlns="http://www.w3.org/2000/svg" aria-label="Условный орбитальный топливный узел"><defs><radialGradient id="planet"><stop stop-color="#527c7a"/><stop offset=".6" stop-color="#253f4d"/><stop offset="1" stop-color="#12242d"/></radialGradient><radialGradient id="glow"><stop stop-color="#a3ecc4" stop-opacity=".2"/><stop offset="1" stop-color="#a3ecc4" stop-opacity="0"/></radialGradient></defs><circle cx="250" cy="225" r="200" fill="url(#glow)"/><g fill="none" stroke="#59796e"><ellipse cx="250" cy="225" rx="205" ry="125" transform="rotate(-32 250 225)" stroke-dasharray="2 7"/><circle cx="250" cy="225" r="183" opacity=".3"/><circle cx="250" cy="225" r="150" opacity=".2"/></g><circle cx="154" cy="301" r="78" fill="url(#planet)" stroke="#47706d"/><path d="M103 261Q177 239 153 308T204 349" stroke="#77a294" stroke-width="18" opacity=".13" fill="none"/><circle cx="376" cy="95" r="25" fill="#63756c"/><circle cx="382" cy="89" r="6" fill="#30443f"/><path d="M200 263Q246 239 279 206M354 115L312 165" stroke="#a3ecc4" stroke-dasharray="5 8" fill="none"/><circle cx="294" cy="188" r="40" fill="#19342c" stroke="#8abea3"/><g fill="none" stroke="#c0efd0" stroke-width="2"><rect x="282" y="175" width="24" height="26"/><path d="M267 179h12v18h-12zM309 179h12v18h-12zM294 167v42M275 188h38"/></g><text x="288" y="254" fill="#b4cebf" font-family="Arial" font-size="12" letter-spacing="2" text-anchor="middle">ОРБИТАЛЬНЫЙ УЗЕЛ</text><text x="86" y="421" fill="#729b8a" font-family="Arial" font-size="12" letter-spacing="3">5 КАНАЛОВ / 1 КОНТУР</text></svg>'''


def cards(items):
    return '<div class="metric-pair">'+''.join('<div class="metric-card"><span class="card-label">'+html.escape(x['label'])+'</span><strong>'+fmt(x['value'])+'</strong><span class="card-unit">'+html.escape(x['unit'])+'</span><div class="card-detail">'+html.escape(x.get('detail','Сопоставимые исходные данные и ставка'))+'</div></div>' for x in items)+'</div>'


def bars(visual):
    items=visual['items'];maximum=max(1,*(x['value'] for x in items));step=64 if len(items)>3 else 80
    parts=[f'<svg class="bar-chart" viewBox="0 0 1100 310" role="img" aria-label="{html.escape(visual["unit"])}"><text x="205" y="22" class="svg-caption">{html.escape(visual["unit"])}</text>']
    for i,item in enumerate(items):
        y=55+i*step;w=max(0,item['value'])/maximum*680
        parts.append(f'<text x="0" y="{y+18}" class="svg-label">{html.escape(item["label"])}</text><rect x="205" y="{y}" width="680" height="22" rx="4" fill="#e3ebe5"/><rect x="205" y="{y}" width="{w}" height="22" rx="4" fill="{"#ca915f" if item["value"] else "#28785d"}"/><text x="916" y="{y+19}" class="svg-value">{fmt(item["value"])}</text>')
        if item.get('detail'):parts.append(f'<text x="1030" y="{y+18}" class="svg-small">{html.escape(item["detail"])}</text>')
    return ''.join(parts)+'</svg>'


def rate_chart(v):
    points=list(v['points'])
    if v.get('root') is not None:points.append({'rate':v['root'],'difference':0})
    points.sort(key=lambda p:p['rate'])
    low=min(p['difference'] for p in points)-25;high=max(p['difference'] for p in points)+35
    x=lambda r:70+r/.1*935;y=lambda d:252-(d-low)/(high-low)*210
    zero=y(0)
    path=' '.join(f'{x(p["rate"])},{y(p["difference"])}' for p in points)
    ticks=''.join(f'<text x="{x(r)}" y="290" text-anchor="middle" class="svg-caption">{int(r*100)}%</text>' for r in (0,.05,.1))
    root=''
    if v.get('root') is not None:root=f'<line x1="{x(v["root"])}" x2="{x(v["root"])}" y1="30" y2="260" stroke="#789d89" stroke-dasharray="3 6"/><circle cx="{x(v["root"])}" cy="{zero}" r="6" fill="#285f4b"/><text x="{x(v["root"])-8}" y="28" text-anchor="end" class="svg-value">{fmt(v["root"]*100)}%</text>'
    return f'<svg viewBox="0 0 1100 310" class="rate-chart" role="img" aria-label="Разность приведённых расходов Lunar минус Earth"><rect x="70" y="{zero}" width="935" height="{260-zero}" fill="#e1eee5"/><line x1="70" x2="1005" y1="{zero}" y2="{zero}" stroke="#a6b8ad"/><text x="1060" y="{zero+5}" class="svg-caption">0</text><text x="85" y="245" class="svg-caption">Lunar дешевле · PV Lunar − PV Earth, млн</text><polyline points="{path}" stroke="#2a7459" stroke-width="3" fill="none"/>{root}{ticks}<text x="73" y="{y(points[0]["difference"])-14}" class="svg-value">{fmt(points[0]["difference"])}</text><text x="1005" y="{y(points[-1]["difference"])-14}" text-anchor="end" class="svg-value">+{fmt(points[-1]["difference"])}</text></svg>'


CSS='''@page{size:1280px 720px;margin:0}*{box-sizing:border-box}html,body{margin:0;font-family:Arial,sans-serif;color:#142e29;background:#111b20}article{width:1280px;height:720px;background:#f5f7f1;padding:49px 64px 90px;position:relative;overflow:hidden;break-after:page}article:last-child{break-after:auto}.kicker{font-size:12px;font-weight:bold;letter-spacing:2.4px;color:#447b62}.page-index{position:absolute;right:55px;top:28px;font-size:95px;line-height:1;font-weight:bold;letter-spacing:-7px;opacity:.035;pointer-events:none}h1{font-size:43px;line-height:1.09;letter-spacing:-1.7px;font-weight:500;margin:19px 0 22px;max-width:1110px}p{font-size:21px;line-height:1.42;margin:8px 0;color:#536e62}.content{position:relative}.content>p{max-width:1100px}.takeaway{position:absolute;left:64px;right:64px;bottom:67px;font-size:18px;line-height:1.4;border-top:1px solid #c5d6ca;padding-top:15px;color:#275e47;max-height:80px}footer{position:absolute;bottom:23px;left:64px;right:64px;font-size:11px;letter-spacing:.6px;color:#6b8377;display:flex;justify-content:space-between}.metric-pair{display:grid;grid-template-columns:1fr 1fr;gap:23px;margin-top:27px}.metric-card{border:1px solid #cbdbcf;border-radius:12px;padding:24px 27px;background:#edf2ea}.metric-card:nth-child(2){background:#ddeadf;border-color:#acc6b2}.card-label{font-size:17px;color:#456854;display:block}.metric-card strong{font-weight:400;font-size:65px;letter-spacing:-2px;display:block;margin:10px 0 4px;font-variant-numeric:tabular-nums}.card-unit{font-size:16px;display:block}.card-detail{font-size:13px;color:#628271;margin-top:20px}.bar-chart,.rate-chart{width:100%;height:293px;display:block;margin-top:18px}.svg-label{fill:#3a5a48;font:20px Arial}.svg-caption{fill:#64816f;font:15px Arial}.svg-value{fill:#173f2d;font:25px Arial}.svg-small{fill:#7c644f;font:14px Arial}table{border-collapse:collapse;width:100%;margin-top:22px;font-size:19px}th{text-align:left;background:#163b2d;color:#e2f0e5;padding:13px 18px;font-size:15px;font-weight:400}td{padding:15px 18px;border-bottom:1px solid #d1ded2}tr:nth-child(even){background:#e8eee4}.network-svg{margin-top:23px;width:100%;height:285px}.theme-cover,.theme-closing{color:#e7eee6;background:radial-gradient(ellipse at 85% 40%,#294b3b55,transparent 60%),#0c1a20}.theme-cover .kicker,.theme-closing .kicker{color:#a3ecc4}.theme-cover h1{font-size:72px;letter-spacing:-3px;max-width:725px;line-height:1.02;margin-top:35px}.theme-cover .content>p{max-width:650px;color:#a5bbb2;font-size:22px;line-height:1.5}.theme-cover .orbit-art{position:absolute;width:450px;height:430px;right:-15px;top:-200px}.theme-cover .takeaway,.theme-closing .takeaway{color:#9ec5b1;border-color:#36534a}.theme-cover footer,.theme-closing footer{color:#6c9683}.theme-cover .page-index,.theme-closing .page-index{color:#a3ecc4}.theme-closing h1{font-size:62px;max-width:1050px;line-height:1.05;margin-top:36px}.theme-closing .content>p{color:#b1c7bb;font-size:23px;max-width:1030px;line-height:1.55;margin:15px 0}.closing-strip{display:flex;gap:18px;margin-top:24px}.closing-strip span{border:1px solid #3d6451;border-radius:7px;padding:15px 23px;color:#a3ecc4;font:12px Arial;letter-spacing:2px}.demo-layout{display:grid;grid-template-columns:310px 1fr;gap:28px;margin-top:20px;align-items:center}.demo-layout img{width:100%;height:300px;object-fit:contain;border:1px solid #bdd2c1;background:#10191e;border-radius:10px}.demo-step{border-bottom:1px solid #cbd8ca;padding:12px 0;font-size:19px;line-height:1.4}.demo-step b{font-size:12px;color:#628773;display:block;margin-bottom:6px}.deck-stage{margin:0 auto}.deck-nav{position:fixed;bottom:15px;left:50%;transform:translateX(-50%);display:flex;align-items:center;gap:10px;background:#14221d;border:1px solid #385245;border-radius:12px;padding:8px 12px;color:#b6d3c1;z-index:10;font:12px Arial}.deck-nav button,.deck-nav a{color:inherit;background:none;border:1px solid #446150;border-radius:6px;padding:9px 13px;cursor:pointer;text-decoration:none;font:12px Arial}.deck-nav button:focus-visible,.deck-nav a:focus-visible{outline:2px solid #a3ecc4}.deck-nav button:disabled{opacity:.3}.deck-ready article{display:none}.deck-ready article.active{display:block}.deck-ready .deck-stage{transform-origin:top left}.deck-ready .deck-shell{position:relative;margin:18px auto 80px}@media print{body{background:white}.deck-shell,.deck-ready .deck-shell{margin:0!important;width:1280px!important;height:auto!important}.deck-stage,.deck-ready .deck-stage{transform:none!important;width:1280px!important}.deck-ready article,article{display:block!important;margin:0!important}.deck-nav{display:none!important}}'''

CSS += '''
.heatmap{margin-top:14px}.heatmap svg{width:100%;height:310px}.proof-layout{display:grid;grid-template-columns:3fr 1fr;gap:26px;margin-top:32px;align-items:start}.proof-layout img{width:100%;display:block;border:1px solid #c9dccd;border-radius:8px}.proof-caption{font-size:11px;letter-spacing:1.5px;color:#536e62;margin:12px 0}.proof-times{padding:15px 0 0 20px;border-left:1px solid #c9dccd}.proof-times>b{font-size:10px;letter-spacing:1px;color:#536e62}.proof-times>div{margin-top:28px}.proof-times span{display:block;font-size:15px}.proof-times strong{display:block;font-weight:400;font-size:32px;letter-spacing:-1px;margin:8px 0}.proof-times small{font-size:12px;color:#536e62}
.decision-matrix{display:grid;grid-template-columns:165px 1fr 1fr;gap:12px;margin-top:22px}.matrix-axis{font-size:12px;letter-spacing:1.5px;color:#536e62;padding-bottom:2px}.matrix-side{font-size:19px;color:#456854;align-self:center;line-height:1.4}.matrix-cell{border:1px solid #abc8b2;background:#dfebe0;border-radius:10px;padding:15px 20px}.matrix-cell.unfit{background:#f3e7db;border-color:#d1b99f}.matrix-cell strong{display:block;font-size:33px;font-weight:400;letter-spacing:-1px}.matrix-cell small{font-size:15px;letter-spacing:0}.matrix-cell span{display:block;font-size:15px;margin:6px 0}.matrix-cell b{font-size:12px;color:#2b6746;font-weight:400}.matrix-cell.unfit b{color:#895427}
.chapter{position:absolute;right:64px;top:28px;font-size:10px;letter-spacing:1.7px;color:#64816f}.process-cards{display:grid;grid-template-columns:repeat(3,1fr);gap:22px;margin-top:38px}.process-cards>div{border:1px solid #bed1c2;background:#e6eee4;border-radius:14px;padding:25px;height:248px}.process-cards span{font-size:42px;color:#447b62;letter-spacing:-2px}.process-cards h2{font-size:26px;line-height:1.2;font-weight:500;margin:20px 0 12px}.process-cards p{font-size:18px}.deck-nav{max-width:calc(100vw - 20px);width:max-content;flex-wrap:wrap;justify-content:center;box-shadow:0 8px 35px #0006}.deck-nav select{max-width:270px;min-width:0;padding:9px;border:1px solid #446150;border-radius:6px;background:#14221d;color:inherit;font:12px Arial}.deck-nav:before{content:"";position:absolute;bottom:-1px;height:2px;background:#a3ecc4;width:var(--progress,8.33%);left:0;border-radius:2px}.speaker-panel{position:fixed;right:20px;top:20px;bottom:100px;width:min(510px,calc(100vw - 40px));background:#fffdf7;border:1px solid #bbcfc0;border-radius:16px;padding:25px;z-index:12;overflow:auto;box-shadow:0 12px 65px #0007;color:#193c31;font:16px/1.65 Arial}.speaker-panel[hidden]{display:none}.speaker-head{display:flex;justify-content:space-between;align-items:center;gap:15px}.speaker-head button{background:transparent;border:1px solid #bfd0c3;border-radius:6px;padding:4px 12px;cursor:pointer;font-size:22px}.speaker-panel h3{font-size:22px;line-height:1.35;margin:20px 0 12px}.speaker-panel section>div{white-space:pre-line;font-size:16px}.speaker-panel .note-time,.speaker-panel .note-warning{font-size:12px;line-height:1.5;color:#5b7365}.speaker-panel .note-warning{background:#f3eddb;padding:12px;border-radius:6px}.theme-cover .chapter,.theme-closing .chapter{color:#7cac94}@media(max-width:640px){.deck-nav{gap:6px;padding:7px;width:calc(100vw - 24px)}.deck-nav select{order:2;max-width:100%;width:100%}.deck-nav button,.deck-nav a{padding:8px;font-size:11px}.speaker-panel{bottom:125px;padding:20px}}@media print{.speaker-panel{display:none!important}}'''

JS='''(()=>{
const slides=[...document.querySelectorAll('article')],shell=document.querySelector('.deck-shell'),stage=document.querySelector('.deck-stage'),picker=document.querySelector('#slidePicker'),panel=document.querySelector('#speakerPanel'),toggle=document.querySelector('#notesToggle');
let index=0;document.body.classList.add('deck-ready');
function fit(){const nav=document.querySelector('.deck-nav');const scale=Math.max(.1,Math.min((innerWidth-24)/1280,(innerHeight-nav.offsetHeight-45)/720));stage.style.transform='scale('+scale+')';shell.style.width=1280*scale+'px';shell.style.height=720*scale+'px';}
function show(i){index=Math.max(0,Math.min(slides.length-1,i));slides.forEach((s,n)=>{s.classList.toggle('active',n===index);s.setAttribute('aria-hidden',n!==index)});document.querySelector('#slideCount').textContent=(index+1)+' / '+slides.length;document.querySelector('#prevSlide').disabled=index===0;document.querySelector('#nextSlide').disabled=index===slides.length-1;picker.value=index;document.querySelectorAll('[data-note]').forEach((n,i)=>n.hidden=i!==index);document.documentElement.style.setProperty('--progress',((index+1)/slides.length*100)+'%');history.replaceState(null,'','#slide-'+(index+1));}
function notes(open){panel.hidden=!open;toggle.setAttribute('aria-expanded',open);if(!open)toggle.focus();}
picker.onchange=()=>show(Number(picker.value));toggle.onclick=()=>notes(panel.hidden);document.querySelector('#closeNotes').onclick=()=>notes(false);
document.querySelector('#prevSlide').onclick=()=>show(index-1);document.querySelector('#nextSlide').onclick=()=>show(index+1);
document.querySelector('#fullscreen').onclick=()=>{if(document.fullscreenElement)document.exitFullscreen().catch(()=>{});else document.documentElement.requestFullscreen().catch(()=>{document.querySelector('#slideCount').textContent='Полный экран недоступен';});};
addEventListener('keydown',e=>{if(e.key==='Escape'&&!panel.hidden){notes(false);return;}if(e.ctrlKey||e.metaKey||e.altKey||['INPUT','TEXTAREA','SELECT'].includes(e.target.tagName))return;if(e.key===' '&&e.target.closest('button,a,summary'))return;if(['ArrowRight','PageDown',' '].includes(e.key)){e.preventDefault();show(index+1)}if(['ArrowLeft','PageUp'].includes(e.key)){e.preventDefault();show(index-1)}if(e.key==='Home'){e.preventDefault();show(0)}if(e.key==='End'){e.preventDefault();show(slides.length-1)}});
addEventListener('beforeprint',()=>slides.forEach(s=>s.removeAttribute('aria-hidden')));addEventListener('afterprint',()=>show(index));
addEventListener('resize',fit);show((parseInt(location.hash.replace('#slide-',''))||1)-1);fit();
})();'''



def render_deck(slides):
    from tools.defense import CHAIN_SVG
    image=ROOT/'docs/assets/showcase.png'
    screenshot='data:image/png;base64,'+base64.b64encode(image.read_bytes()).decode() if image.exists() else None
    articles=[]
    for i,slide in enumerate(slides,1):
        v=slide.get('visual',{});kind=v.get('type','table')
        body=''.join('<p>'+html.escape(line)+'</p>' for line in slide['lines'])
        if kind=='cover':body+='<div class="orbit-art">'+ORBIT+'</div>'
        elif kind=='network':body+=CHAIN_SVG.replace('<svg ', '<svg class="network-svg" ',1)
        elif kind=='process':body+='<div class="process-cards">'+''.join(f'<div><span>0{j}</span><h2>{html.escape(item["label"])}</h2><p>{html.escape(item["detail"])}</p></div>' for j,item in enumerate(v['items'],1))+'</div>'
        elif kind=='cards':body+=cards(v['items'])
        elif kind=='matrix':
            cells=['<div></div><div class="matrix-axis">ОБЫЧНЫЕ УСЛОВИЯ</div><div class="matrix-axis">ОБЯЗАТЕЛЬНЫЙ СТРЕСС</div>']
            for j,item in enumerate(v['items']):
                if j%2==0:cells.append('<div class="matrix-side">'+('Исходный<br>план' if j==0 else 'Подготовка<br>заранее')+'</div>')
                cells.append(f'<div class="matrix-cell {"unfit" if item["violations"] else "fit"}"><strong>{fmt(item["cost"])} <small>млн</small></strong><span>Дефицит {fmt(item["shortage"])} т · {item["violations"]} наруш.</span><b>{"! Не проходит" if item["violations"] else "✓ Проходит проверки"}</b></div>')
            body+='<div class="decision-matrix">'+''.join(cells)+'</div>'
        elif kind=='heatmap':
            from tools.evidence import heatmap
            body+='<div class="heatmap">'+heatmap(v['study'])+'</div>'
        elif kind=='demo_proof':
            from tools.evidence_publish import image
            m=v['measurement'];t=m['timings']
            body+='<div class="proof-layout"><div>'+''.join(f'<div class="proof-caption">{label}</div><img src="{image(name)}" alt="{label}">' for name,label in [('ui-base.png','01 / ОБЫЧНЫЕ УСЛОВИЯ'),('ui-stress.png','02 / ТОТ ЖЕ ПЛАН В СТРЕССЕ')])+'</div><div class="proof-times"><b>ТЁПЛЫЙ ЛОКАЛЬНЫЙ СТЕНД</b>'+''.join(f'<div><span>{label}</span><strong>{fmt(t[key]["median_ms"])} мс</strong><small>медиана · p95 {fmt(t[key]["p95_ms"])} мс</small></div>' for key,label in [('switch','Кешированный вид'),('recourse','Новый расчёт + JSON')])+'</div></div>'
        elif kind=='bars':body+=bars(v)
        elif kind=='rates':body+=rate_chart(v)
        elif kind=='demo':
            body+='<div class="demo-layout"><div>'+''.join(f'<div class="demo-step"><b>0{j} / ПОКАЖИТЕ</b>{text}</div>' for j,text in enumerate(['Тот же план в двух средах','Цену и пределы подготовки','Реакцию после наблюдения'],1))+'</div>'+(f'<img src="{screenshot}" alt="Работающий сценарный центр, контрольный Lunar BASE">' if screenshot else '<p>Откройте сайт и запустите расчёт.</p>')+'</div>'
        elif kind=='closing':body+='<div class="closing-strip"><span>ВХОДЫ</span><span>РЕШЕНИЯ</span><span>ПРОВЕРКИ</span><span>ЭКСПОРТ</span></div>'
        elif slide.get('rows'):
            body+='<table><thead><tr>'+''.join('<th>'+html.escape(x)+'</th>' for x in slide['headers'])+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+html.escape(str(x))+'</td>' for x in row)+'</tr>' for row in slide['rows'])+'</tbody></table>'
        articles.append(f'<article class="theme-{kind}" aria-label="Слайд {i}"><div class="page-index" aria-hidden="true">{i:02}</div><div class="chapter">{html.escape(slide.get("chapter",""))}</div><div class="kicker">{html.escape(slide["kicker"])}</div><h1>{html.escape(slide["title"])}</h1><div class="content">{body}</div><div class="takeaway">{html.escape(slide["takeaway"])}</div><footer><span>КОСМОКОНТУР / TEAM_ANALYSIS · млн постоянных у.е. 2035 / тонны</span><span>Страница {i} / {len(slides)}</span></footer></article>')
    picker=''.join(f'<option value="{j}">{j+1:02} · {html.escape(slide["title"])}</option>' for j,slide in enumerate(slides))
    notes=''.join(f'<section data-note="{j}" hidden><h3>{j+1}. {html.escape(slide["title"])}</h3><p class="note-time">Ориентир: {slide["seconds"]} секунд · репетиционный план</p><div>{html.escape(slide["notes"])}</div></section>' for j,slide in enumerate(slides))
    return '<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Космоконтур — проверяемые решения</title><style>'+CSS+'</style><body><div class="deck-shell"><div class="deck-stage">'+''.join(articles)+'</div></div><nav class="deck-nav" aria-label="Управление презентацией"><button id="prevSlide" aria-label="Предыдущий слайд">←</button><span id="slideCount" aria-live="polite">1 / 12</span><button id="nextSlide" aria-label="Следующий слайд">→</button><select id="slidePicker" aria-label="Перейти к слайду">'+picker+'</select><button id="notesToggle" aria-expanded="false" aria-controls="speakerPanel">Что говорить</button><button id="fullscreen">Полный экран</button><a href="/" aria-label="Вернуться к сайту">Сайт ↗</a></nav><aside id="speakerPanel" class="speaker-panel" aria-label="Заметки докладчика" hidden><div class="speaker-head"><strong>Ваши слова к слайду</strong><button id="closeNotes" aria-label="Закрыть заметки">×</button></div><p class="note-warning">Заметки видны на этом экране, в том числе при его трансляции.</p>'+notes+'</aside><script>'+JS+'</script></body></html>'


def render_pptx(slides, destination):
    from pptx import Presentation
    from pptx.util import Inches,Pt
    from pptx.dml.color import RGBColor
    from pptx.enum.shapes import MSO_SHAPE,MSO_CONNECTOR
    prs=Presentation();prs.slide_width=Inches(13.333333);prs.slide_height=Inches(7.5)
    def rect(s,x,y,w,h,fill,line=None,ellipse=False):
        sh=s.shapes.add_shape(MSO_SHAPE.OVAL if ellipse else MSO_SHAPE.ROUNDED_RECTANGLE,Inches(x), Inches(y), Inches(w), Inches(h))
        if fill:sh.fill.solid();sh.fill.fore_color.rgb=RGBColor.from_string(fill)
        else:sh.fill.background()
        if line:sh.line.color.rgb=RGBColor.from_string(line)
        else:sh.line.fill.background()
        return sh
    def text(s,x,y,w,h,value,size=19,color='163F2D',bold=False):
        sh=s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h));f=sh.text_frame;f.word_wrap=True;f.margin_top=0;f.margin_bottom=0;f.margin_left=0;f.margin_right=0
        for i,line in enumerate(str(value).split('\n')):
            p=f.paragraphs[0] if i==0 else f.add_paragraph();p.text=line;p.font.name='Arial';p.font.size=Pt(size);p.font.color.rgb=RGBColor.from_string(color);p.font.bold=bold
        return sh
    def line(s,x1,y1,x2,y2,color='2A7459',width=2):
        c=s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT,Inches(x1),Inches(y1),Inches(x2),Inches(y2));c.line.color.rgb=RGBColor.from_string(color);c.line.width=Pt(width)
    for i,d in enumerate(slides,1):
        s=prs.slides.add_slide(prs.slide_layouts[6]);v=d.get('visual',{});kind=v.get('type','table');dark=kind in ('cover','closing')
        bg='0C1A20' if dark else 'F5F7F1';fg='E7EEE6' if dark else '142E29'
        s.background.fill.solid();s.background.fill.fore_color.rgb=RGBColor.from_string(bg)
        text(s,10.1,.43,2.55,.25,d.get('chapter',''),9,'729B8A')
        text(s,.66,.43,9.2,.25,d['kicker'],10,'A3ECC4' if dark else '447B62',True)
        if kind=='cover':
            for size in (3.6,4.2):rect(s,10-size/2,3.1-size/2,size,size,None,'38574A',True)
            rect(s,8.1,3.6,1.65,1.65,'253F4D','476D6A',True);rect(s,11.25,1.8,.6,.6,'63756C',None,True)
            line(s,9.4,3.95,10.2,3,'A3ECC4',1);line(s,10.55,2.85,11.25,2.1,'A3ECC4',1)
            rect(s,9.85,2.35,.85,.85,'19342C','8ABEA3',True);rect(s,10.1,2.6,.34,.34,None,'C0EFD0')
            text(s,8.5,5.6,4,.3,'5 КАНАЛОВ / 1 КОНТУР',11,'729B8A')
        title_size=43 if kind=='cover' else 35 if kind=='closing' else 28
        text(s,.66,.97,7.5 if kind=='cover' else 12,1.8 if dark else 1.1,d['title'],title_size,fg)
        text(s,.66,3.45 if kind=='cover' else 2.45 if kind=='closing' else 2.04,6.6 if kind=='cover' else 12,1.7 if dark else 1.05,'\n'.join(d['lines']),18 if dark else 16,'A5BBB2' if dark else '536E62')
        if kind=='network':
            for x,w,label in [(.7,4.25,'ИСТОЧНИКИ\nCore: 12 мес. / Flex: 4 мес.\nNew: 18–24 мес.; нужен ввод\nLunar: 1–2 мес. после ввода\nEmergency: 6 недель'),(5.2,3.2,'ОРБИТАЛЬНЫЙ УЗЕЛ\nХранение и потери\nФизический резерв\nДоступная ёмкость'),(8.7,3.9,'ПОТРЕБИТЕЛИ\nКритические — первыми\nКоммерческие — остаток')]:
                rect(s,x,3.3,w,2.45,'E5EEE4','B6CBB8');text(s,x+.16,3.5,w-.32,2.1,label,16)
            text(s,4.9,4.1,.4,.4,'→',22);text(s,8.35,4.1,.4,.4,'→',22)
        elif kind=='process':
            for j,item in enumerate(v['items']):
                x=.7+j*4.05;rect(s,x,3.27,3.8,2.45,'E5EEE4','B6CBB8')
                text(s,x+.22,3.5,3.35,.6,f'0{j+1}',30,'447B62')
                text(s,x+.22,4.22,3.35,.65,item['label'],21)
                text(s,x+.22,5.02,3.35,.6,item['detail'],14,'536E62')
        elif kind=='cards':
            for j,item in enumerate(v['items']):
                x=.66+6.1*j;rect(s,x,3.26,5.87,2.55,'DDEADF' if j else 'EDF2EA','B6CBB8')
                text(s,x+.28,3.51,5.3,.4,item['label'],16,'456854')
                text(s,x+.28,4.00,5.3,.85,fmt(item['value']),40)
                text(s,x+.28,4.91,5.3,.48,item['unit'],14)
                text(s,x+.28,5.43,5.3,.3,item.get('detail','Сопоставимые данные и ставка'),11,'628271')
        elif kind=='matrix':
            text(s,2.72,3.03,4.8,.3,'ОБЫЧНЫЕ УСЛОВИЯ',11,'536E62')
            text(s,7.7,3.03,4.8,.3,'ОБЯЗАТЕЛЬНЫЙ СТРЕСС',11,'536E62')
            for j,item in enumerate(v['items']):
                x=2.65+(j%2)*5;y=3.45+(j//2)*1.28;bad=item['violations']>0
                if j%2==0:text(s,.7,y+.27,1.75,.75,'Исходный\nплан' if j==0 else 'Подготовка\nзаранее',16)
                rect(s,x,y,4.8,1.12,'F3E7DB' if bad else 'DFEBE0','D1B99F' if bad else 'ABC8B2')
                text(s,x+.2,y+.12,4.4,.4,fmt(item['cost'])+' млн',24)
                text(s,x+.2,y+.59,4.4,.27,f"Дефицит {fmt(item['shortage'])} т · {item['violations']} наруш.",12)
                text(s,x+.2,y+.88,4.4,.22,'! Не проходит' if bad else 'Проходит проверки',10,'895427' if bad else '2B6746')
        elif kind=='heatmap':
            study=v['study'];rows={(r['delivery_share'],r['observed_after_days']):r for r in study['rows']}
            for j,delay in enumerate(study['observation_delays']):text(s,2.1+j*1.48,3.10,1.38,.25,str(delay)+' дней',12)
            for k,share in enumerate(study['delivery_shares']):
                y=3.51+k*.46;text(s,.7,y+.08,1.3,.3,f'{share*100:g}%'+(' · контроль' if share==1 else ''),12)
                for j,delay in enumerate(study['observation_delays']):
                    a=rows[share,delay]['after'];x=2.1+j*1.48
                    fill='E9EDEF' if share==1 else 'DCEBDC' if a['violations']==0 else 'F3E4CE' if a['shortage_t']<1e-8 else 'EDC9B8'
                    rect(s,x,y,1.38,.42,fill);text(s,x+.06,y+.025,1.26,.24,fmt(a['shortage_t'])+' т',14)
                    text(s,x+.06,y+.25,1.26,.15,str(a['violations'])+' наруш.',8)
            text(s,.7,5.99,12,.27,'Строки: исполнено Lunar · столбцы: задержка наблюдения · 100% = нет сбоя',11,'536E62')
        elif kind=='demo_proof':
            for j,(name,label) in enumerate([('ui-base.png','01 / ОБЫЧНЫЕ УСЛОВИЯ'),('ui-stress.png','02 / ТОТ ЖЕ ПЛАН В СТРЕССЕ')]):
                text(s,.7,3.1+j*1.45,8.2,.25,label,10,'536E62')
                s.shapes.add_picture(str(ROOT/'docs/evidence'/name),Inches(.7),Inches(3.44+j*1.45),width=Inches(8.2))
            text(s,9.2,3.13,3.4,.5,'ТЁПЛЫЙ ЛОКАЛЬНЫЙ СТЕНД',11,'536E62')
            for j,(key,label) in enumerate([('switch','Кешированный вид'),('recourse','Новый расчёт + JSON')]):
                t=v['measurement']['timings'][key];y=3.75+j*1.2
                text(s,9.2,y,3.4,.3,label,13)
                text(s,9.2,y+.34,3.4,.48,fmt(t['median_ms'])+' мс',27)
                text(s,9.2,y+.84,3.4,.3,'медиана · p95 '+fmt(t['p95_ms'])+' мс',11,'536E62')
        elif kind=='bars':
            items=v['items'];maximum=max(1,*(x['value'] for x in items));text(s,3.0,3.03,9,.3,v['unit'],11,'64816F')
            step=.60 if len(items)>3 else .75
            for j,item in enumerate(items):
                y=3.50+j*step;text(s,.7,y-.04,2.2,.45,item['label'],16)
                rect(s,3,y,7.1,.23,'E3EBE5')
                if item['value']>0:rect(s,3,y,7.1*item['value']/maximum,.23,'CA915F')
                text(s,10.4,y-.05,1.2,.4,fmt(item['value']),18)
                if item.get('detail'):text(s,11.6,y-.02,1.1,.5,item['detail'],10,'7C644F')
        elif kind=='rates':
            points=list(v['points']);root=v.get('root')
            if root is not None:points.append({'rate':root,'difference':0})
            points.sort(key=lambda p:p['rate']);low=min(p['difference'] for p in points)-25;high=max(p['difference'] for p in points)+35
            xx=lambda r:1+r/.1*10.6;yy=lambda value:5.66-(value-low)/(high-low)*2.15
            line(s,1,yy(0),11.6,yy(0),'A6B8AD',1)
            for a,b in zip(points,points[1:]):line(s,xx(a['rate']),yy(a['difference']),xx(b['rate']),yy(b['difference']))
            for r in (0,.05,.1):text(s,xx(r)-.2,5.91,.8,.3,str(int(r*100))+'%',12,'64816F')
            if root is not None:
                line(s,xx(root),3.2,xx(root),5.75,'A6B8AD',.7);rect(s,xx(root)-.055,yy(0)-.055,.11,.11,'285F4B',None,True)
                text(s,xx(root)-1.3,3.15,1.3,.4,fmt(root*100)+'%',20)
            text(s,1,yy(points[0]['difference'])-.35,1.5,.4,fmt(points[0]['difference']),18)
            text(s,10.4,yy(points[-1]['difference'])-.35,1.5,.4,'+'+fmt(points[-1]['difference']),18)
            text(s,2,5.48,7,.3,'PV Lunar − PV Earth, млн · ниже нуля Lunar дешевле',11,'64816F')
        elif kind=='demo':
            for j,phrase in enumerate(('Тот же план в двух средах','Цена и пределы подготовки','Действие после наблюдения')):
                text(s,.7,3.3+j*.77,3.5,.6,f'0{j+1} / {phrase}',17)
            image=ROOT/'docs/assets/showcase.png'
            if image.exists():s.shapes.add_picture(str(image),Inches(7.3),Inches(3.02),height=Inches(3.1))
        elif kind=='closing':
            for j,word in enumerate(('ВХОДЫ','РЕШЕНИЯ','ПРОВЕРКИ','ЭКСПОРТ')):
                rect(s,.7+2.4*j,5.2,2.2,.55,None,'3D6451');text(s,.86+2.4*j,5.38,2,.3,word,11,'A3ECC4')
        elif d.get('rows'):
            rows=[d['headers']]+d['rows'];table=s.shapes.add_table(len(rows),len(rows[0]), Inches(.7), Inches(3.25), Inches(11.95), Inches(.5*len(rows))).table
            for ri,row in enumerate(rows):
                for ci,value in enumerate(row):
                    cell=table.cell(ri,ci);cell.text=str(value);cell.fill.solid();cell.fill.fore_color.rgb=RGBColor.from_string('163B2D' if ri==0 else 'E8EEE4' if ri%2==0 else 'F5F7F1')
                    for p in cell.text_frame.paragraphs:p.font.name='Arial';p.font.size=Pt(15);p.font.color.rgb=RGBColor.from_string('E2F0E5' if ri==0 else '163F2D')
        line(s,.66,6.38,12.65,6.38,'36534A' if dark else 'C5D6CA',.7)
        text(s,.66,6.51,12,.65,d['takeaway'],14,'9EC5B1' if dark else '275E47')
        text(s,.66,7.21,11,.22,'КОСМОКОНТУР / TEAM_ANALYSIS · млн постоянных у.е. 2035 / тонны',9,'6B8377')
        text(s,11.65,7.21,1,.22,f'{i:02} / {len(slides)}',9,'6B8377')
        s.notes_slide.notes_text_frame.text=d['notes']
    prs.save(str(destination))
