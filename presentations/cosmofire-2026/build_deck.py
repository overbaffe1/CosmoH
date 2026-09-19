"""Editable PPTX + offline HTML from one scene graph. No competition code is changed."""
from pathlib import Path
import base64, html, json, shutil
from PIL import ImageFont
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR

ROOT = Path(__file__).resolve().parent
W, H = 1280, 720
PAPER, INK, MUTED = '#F3F5EF', '#172E27', '#64796D'
DARK, GREEN, MINT, LINE = '#101F1C', '#237A56', '#B6F0C9', '#CFDAD0'
ORANGE, GOLD = '#D85F3F', '#D9B65B'
FONT = 'DejaVu Sans'
FONT_DIR = ROOT / 'assets/fonts'
FONT_DIR.mkdir(parents=True, exist_ok=True)
for name in ('DejaVuSans.ttf', 'DejaVuSans-Bold.ttf'):
    target = FONT_DIR / name
    if not target.exists():
        shutil.copy('/usr/share/fonts/truetype/dejavu/' + name, target)

slides = []

def wrap(text, size, width, bold=False):
    font = ImageFont.truetype(str(FONT_DIR / ('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf')), round(size))
    lines=[]
    for para in text.split('\n'):
        line=''
        for word in para.split(' '):
            trial=(line+' '+word).strip()
            if line and font.getlength(trial)>width-8:
                lines.append(line);line=word
            else:line=trial
        lines.append(line)
    return '\n'.join(lines)

class Slide:
    def __init__(self, section, title, dark=False, source=''):
        self.items=[];self.dark=dark;self.title=title;self.source=source
        self.ink=MINT if dark else INK;self.muted='#98B4A5' if dark else MUTED
        self.rect(0,0,W,H,DARK if dark else PAPER)
        self.text(60,34,1120,section.upper(),13,self.ink,bold=True)
        self.text(60,80,1160,title,44,self.ink,bold=True)
        self.rect(60,672,1160,1,'#345043' if dark else LINE)
        self.text(60,686,980,'КОСМОФАЙР-2  /  КОСМОХАКАТОН 2026  ·  КРАСНОЯРСК',11,self.muted)
        self.text(1144,682,95,f'{len(slides)+1:02} / 12',14,self.muted)
        slides.append(self)
    def rect(self,x,y,w,h,fill,radius=0,stroke=None):
        self.items.append(dict(type='rect',x=x,y=y,w=w,h=h,fill=fill,radius=radius,stroke=stroke))
    def text(self,x,y,w,text,size=24,color=None,bold=False):
        content=wrap(text,size,w,bold)
        self.items.append(dict(type='text',x=x,y=y,w=w,h=(content.count('\n')+1)*size*1.22+8,text=content,size=size,color=color or self.ink,bold=bold))
    def image(self,x,y,w,h,name):
        self.items.append(dict(type='image',x=x,y=y,w=w,h=h,path='assets/'+name))
    def note(self,text):self.text(60,634,1155,text,13,self.muted)
    def card(self,x,y,w,h,label,body,accent=None):
        self.rect(x,y,w,h,'#1A3028' if self.dark else '#E8EEE5',10)
        self.rect(x+20,y+23,4,27,accent or GREEN)
        self.text(x+38,y+22,w-60,label,24,self.ink,True)
        self.text(x+24,y+75,w-48,body,21,self.muted)

# 01 — a real training scene, not decorative AI imagery.
s=Slide('Двухэтапный мониторинг природных пожаров','',True,'Постановка; PROBES_UPLOAD.md; сообщение команды')
s.image(793,95,427,427,'train-swir.png')
s.rect(793,493,427,71,'#1A3028')
s.text(813,507,388,'SWIR · обучающий чип BS_tr_000117',14,MINT)
s.text(813,532,388,'Архивный снимок. Не финальный тест.',13,'#98B4A5')
s.text(60,91,705,'КосмоФАЙР-2',26,MINT)
s.text(55,151,728,'Огонь найти.\nПоследствия\nизмерить.',66,'#F1F5EA',True)
s.text(60,422,660,'От тепловой аномалии — к контуру гари\nи степени повреждения растительности.',23,'#B0C6B8')
s.text(58,514,420,'0.7455',83,MINT,True)
s.text(447,540,300,'Лучший скор платформы\nпо данным команды · probe 35',18,'#B0C6B8')
s.note('Score — составная метрика, не процент точности и не баллы жюри. Приватный результат не подтверждён.')

# 02 — data contract.
s=Slide('01 / Задача и данные','Один пожар. Два масштаба наблюдения.',source='Постановка, разделы «Цель», «Данные», «Формат ответа»')
for x,idx,title,res,detail in [(60,'AF','Где горит сейчас','375 м','VIIRS I1–I5 + вспомогательные слои\nБинарная маска природного горения'),(650,'BS','Что осталось после','20 м','Sentinel-2 до/после + Sentinel-1\nГарь и степень поражения: 0–3')]:
 s.rect(x,187,570,300,'#E5ECE2',12);s.text(x+26,209,95,idx,16,GREEN,True);s.text(x+26,249,520,title,30,INK,True);s.text(x+26,300,510,res,66,GREEN,True);s.text(x+26,399,520,detail,21,MUTED)
s.text(62,522,550,'TRAIN  420 AF + 224 BS',26,INK,True)
s.text(652,522,550,'TEST  180 AF + 89 BS',26,INK,True)
s.text(62,563,550,'AF: 256 × 256 px  ·  BS: 512 × 512 px',21,MUTED)
s.text(652,563,550,'Один CSV: 180 + 3 × 89 = 447 строк',21,MUTED)
s.note('Три результата: активное горение → площадь гари → степень поражения. Степени 1 / 2 / 3: слабая / средняя / сильная.')

# 03 — actual implementation, not a neural-network claim.
s=Slide('02 / Решение','Физические правила + обучаемая модель',source='fires/af.py; fires/bs.py; fires/severity.py; weights/weights_probe_35.json')
for y,label,steps,color in [(190,'AF',[('Тепловой сигнал','I4, I5, день / ночь'),('Контекст','Отклонение от фона'),('Маска','Природное горение')],GREEN),(377,'BS',[('До / после','NBR, dNBR, покров'),('Бустинг','23 признака пикселя'),('Постобработка','Контуры + классы')],ORANGE)]:
 s.text(60,y+47,72,label,28,color,True)
 for j,(name,sub) in enumerate(steps):
  x=158+j*354;s.rect(x,y,328,151,'#E6ECE3',10);s.text(x+20,y+25,292,name,25,INK,True);s.text(x+20,y+75,292,sub,20,MUTED)
  if j<2:s.text(x+330,y+47,35,'→',24,color)
s.text(60,559,1160,'Python  ·  NumPy / SciPy  ·  scikit-learn  ·  FastAPI  ·  Three.js',22,GREEN)
s.note('BS: HistGradientBoostingClassifier на CPU. В probe 35 восстановление под облаками по SAR выключено; нейросеть не заявляется.')

# 04 — historical, explicitly train-only diagnosis.
s=Slide('03 / EDA → инженерное решение','Маска облачности скрывала сигнал',source='JUMP_REPORT.md; fires/bs.py; исторические замеры train, не повторены')
s.text(58,175,492,'17.8%',96,GREEN,True)
s.text(64,299,488,'эталонной гари в train\nпопало под маску SCL',27,INK)
s.text(64,382,480,'1 051 349 пикселей\nПо диагностике обучающей выборки',20,MUTED)
s.rect(612,184,608,338,'#E6ECE3',12)
s.text(640,208,550,'Исключили SCL = 10 из жёсткой маски',23,INK,True)
s.text(640,253,550,'Тени, плотные облака и снег\nSCL 3 / 8 / 9 / 11 остаются закрыты.',21,MUTED)
for y,label,a,b,col in [(337,'Пропущенная гарь (FN)','1.46 млн','0.78 млн',GREEN),(420,'Ложная гарь (FP)','1.97 млн','2.44 млн',ORANGE)]:
 s.text(640,y,530,label,16,MUTED);s.text(640,y+28,530,f'{a}  →  {b}',32,col,True)
s.rect(60,553,1160,57,'#DAE6D7',8);s.text(82,566,1114,'Меньше пропусков — ценой роста ложных срабатываний. Это компромисс, не универсальное правило.',20,INK)
s.note('Все числа здесь — исторические замеры train. Доля 17.8% относится ко всей маске SCL, а не только к классу 10.')

# 05 — central pixel illustration, not invented satellite evidence.
s=Slide('04 / Финальная конфигурация','Окно 3 × 3 убирает «соль и перец»',source='PROBES_UPLOAD.md; weights/weights_probe_35.json; severity_model_p35.pkl (static inspection)')
colors={1:'#A6C99D',2:GOLD,3:ORANGE}
for k,x in enumerate([65,363]):
 grid=[[2,2,1],[2,3 if k==0 else 2,2],[2,2,2]]
 for i,row in enumerate(grid):
  for j,v in enumerate(row):
   s.rect(x+j*69,220+i*69,61,61,colors[v],4,INK if i==j==1 else None)
   s.text(x+j*69+20,233+i*69,38,str(v),25,INK,True)
 s.text(x,446,244,'ДО' if k==0 else 'ПОСЛЕ',16,MUTED,True)
s.text(287,288,64,'→',42,GREEN)
s.text(65,493,498,'Схема голосования\nза центральный пиксель',21,MUTED)
s.text(650,196,568,'probe 24 → probe 35',22,MUTED)
s.text(646,239,574,'0.7393 → 0.7455',45,GREEN,True)
s.text(650,312,555,'+0.0062 к скору платформы',24,GREEN)
s.text(650,371,550,'Один проход majority 3 × 3\nМинимальный контур: 96 px\nAF: k_sigma = 2.5',25,INK)
s.text(650,490,550,'5 × 5 и повторный проход\nдали худший результат.',22,ORANGE)
s.note('Здесь показана алгоритмическая постобработка. Ручная разметка тестовых чипов запрещена условиями кейса.')

# 06 — point scale with explicit domain; no misleading truncated bars.
s=Slide('05 / Эксперименты','Улучшение — это ещё и вовремя откатиться',True,'Сообщение команды; PROBES_UPLOAD.md; JUMP_REPORT.md')
lo,hi=.68,.75;x0,x1=302,865
for tick in [.68,.70,.72,.74,.75]:
 x=x0+(tick-lo)/(hi-lo)*(x1-x0);s.rect(x,217,1,312,'#2E463B');s.text(x-22,546,80,f'{tick:.2f}',15,'#98B4A5')
for j,(name,val) in enumerate([('Ранний ответ',.6979),('v1',.7391),('probe 24',.7393),('probe 35',.7455)]):
 y=235+j*83;x=x0+(val-lo)/(hi-lo)*(x1-x0)
 s.text(62,y-9,230,name,23,'#D4E4D8',j==3);s.rect(x-7,y,14,14,MINT if j==3 else '#648F75',7);s.text(x-57,y-38,145,f'{val:.4f}',23,MINT,j==3)
s.rect(946,204,273,340,'#1B3229',12)
s.text(968,226,233,'НЕ ВЫБРАЛИ',14,'#C5AD77',True)
s.text(968,273,229,'0.7357',39,'#E49A7F',True);s.text(968,326,229,'Бэггинг +\nбинарная голова',19,'#B0C6B8')
s.text(968,405,229,'0.7313',39,'#E49A7F',True);s.text(968,458,229,'Majority 5 × 5',19,'#B0C6B8')
s.text(61,588,1150,'+0.0476 к раннему ответу  ·  все значения — скор платформы по данным команды',20,MINT)
s.note('Шкала графика: 0.68–0.75. Train / validation не смешаны с платформой; причин различий по приватной части не утверждаем.')

# 07 — metric and honest component availability.
s=Slide('06 / Что означает результат','Три компонента качества, а не «точность»',source='Официальная постановка, «Метрика»; JUMP_REPORT.md, компоненты train')
for j,(coef,name,desc) in enumerate([('0.35','F1_AF','Активное горение'),('0.35','IoU_burn','Контур гари'),('0.30','mIoU_sev','Степени 1 / 2 / 3')]):
 x=60+j*395;s.rect(x,185,370,198,'#E5ECE2',12);s.text(x+23,202,330,coef,55,GREEN,True);s.text(x+24,271,330,'× '+name,28,INK,True);s.text(x+24,328,330,desc,19,MUTED)
s.text(60,411,1160,'Сначала TP / FP / FN суммируются по всем чипам. Затем считается метрика.',21,INK)
s.rect(60,462,1160,128,'#E6ECE3',8)
s.text(80,476,530,'Контроль после SCL · исторический train',18,MUTED)
s.text(80,514,1100,'F1_AF  0.90934     IoU_burn  0.61496     mIoU_sev  0.59772',24,INK,True)
s.text(80,552,1110,'Взвешенная сумма: 0.71282. Это НЕ разложение финального 0.7455.',18,ORANGE)
s.note('Компоненты результата 0.7455 не предоставлены. mIoU — среднее IoU классов 1–3; пустой и в истине, и в ответе класс даёт 1.')

# 08 — actual browser capture, training-only screenshot, API independently tested.
s=Slide('07 / Продукт','Рассмотреть. Проверить. Выгрузить.',True,'map.html (train screenshot); service/app.py; service/catalog.json; 82 tests')
s.image(60,185,760,475,'viewer-train.png')
s.rect(60,609,760,51,DARK)
s.text(72,619,733,'Реальный интерфейс на train · высота — dNBR, не рельеф',15,'#AFC6B6')
s.text(860,193,356,'REST API',29,MINT,True)
for y,k,v in [(249,'Запрос','bbox / polygon + даты'),(344,'Карта и векторы','Термоточки · GeoJSON / SHP'),(439,'Справка','Гектары + степени · JSON / CSV')]:
 s.text(860,y,350,k,21,'#E3ECE2',True);s.text(860,y+38,350,v,18,'#AFC6B6');s.rect(860,y+79,350,1,'#345043')
s.text(861,555,350,'Подготовленный каталог train.\nНе оперативный мониторинг\nвсей территории России.',18,'#C5AD77')
# Custom note is intentionally absent: the screenshot has its own explicit caption.

# 09 — current verification and release blocker.
s=Slide('08 / Проверяемость','Проверили формат. Разделили версии.',source='Аудит 20.09.2026: pytest; независимая структурная проверка CSV; сравнение weights')
for j,(n,label) in enumerate([('82','теста прошли в этой проверке'),('447','строк в submission_probe_35.csv'),('269','чипов: 180 AF + 89 BS')]):
 x=60+j*395;s.text(x,183,370,n,83,GREEN,True);s.text(x+3,293,366,label,19,MUTED)
s.rect(60,351,1160,178,'#E6ECE3',12)
s.text(82,373,1105,'Конфигурация чемпиона в архиве',23,INK,True)
s.text(82,418,1105,'weights_probe_35.json  →  severity_model_p35.pkl',27,GREEN,True)
s.text(82,471,1105,'RLE: допустимые границы, непересекающиеся классы, уникальные ключи.',21,INK)
s.rect(60,551,1160,60,'#F0E4D6',8)
s.text(82,566,1111,'Важно: веса по умолчанию и TOPsubmission.csv не совпадают с probe 35.',22,'#8A492D',True)
s.note('Полный инференс не повторён: исходных TIFF и шаблона теста в архиве нет. 82 теста ≠ подтверждение метрики или времени на стенде жюри.')

# 10 — exact rubric, not invented self-awarded score.
s=Slide('09 / Критерии жюри · часть 1','60 баллов: качество и инженерный отчёт',source='Официальные критерии, разделы 2 и 3.2')
s.rect(60,183,390,419,INK,12);s.text(86,207,336,'40',99,MINT,True)
s.text(88,337,330,'Качество модели',27,'#E5EEE4',True)
s.text(88,399,322,'По приватному Score,\nнормированному среди\nвалидных решений.',21,'#ACC5B5')
s.text(88,513,323,'0.7455 не переводится\nнапрямую в 40 баллов.',20,'#DFBB86')
s.text(488,192,710,'20  /  ОТЧЁТ: ПЯТЬ КРИТЕРИЕВ ПО 4',22,GREEN,True)
for i,(title,proof) in enumerate([('EDA','Диагностика маски SCL и типов ошибок'),('Бейзлайн','Правила AF, пороги BS, точка сравнения'),('Эксперименты','Сопоставимые пробы, в том числе неудачные'),('Предметная область','День / ночь, покров, оптика и SAR'),('Выводы','Компромисс FN / FP и ограничения переноса')]):
 y=250+i*70;s.text(490,y,224,title,21,INK,True);s.text(708,y,490,proof,18,MUTED);s.rect(490,y+54,710,1,LINE)
s.note('Это карта требований и доказательств, а не присвоенные командой баллы. Формула качества: 40 × (Score − worst) / (best − worst).')

# 11 — remaining four categories total 40.
s=Slide('10 / Критерии жюри · часть 2','Ещё 40: код, сервис, защита и скорость',source='Официальные критерии, 3.1, 3.3, 4, 5; аудит исходников сервиса')
cards=[(60,182,'12  /  Код','5 воспроизводимость · 4 структура\n3 корректный инференс\n82 теста; финальный default не сверен.'),(650,182,'12  /  Сервис','4 запрос + API · 4 карта + векторы\n4 справка по площадям\nAPI есть; AOI-фильтр требует проверки.'),(60,401,'8  /  Презентация','3 ясность · 5 выступление\n12 слайдов, отдельная речь.\nРегламент времени уточнить у площадки.'),(650,401,'8  /  Скорость','<30 с: 8 · ≤5 мин: 6 · ≤12 мин: 4\n≤30 мин: 2 · >1 ч / сбой: 0\nСвежего замера на стенде жюри нет.')]
for x,y,title,body in cards:
 s.rect(x,y,570,197,'#E6ECE3',10);s.text(x+23,y+20,525,title,28,GREEN,True);s.text(x+23,y+70,525,body,20,INK)
s.note('AOI: сейчас отбор контура по первой вершине, не пересечению. Интервал 30–60 минут в шкале скорости не определён: нужен ответ организатора.')

# 12 — scope and takeaway.
s=Slide('11 / Итог','От снимка — к проверяемому решению',True,'Итог по архиву; скор по данным команды; регламент 8.5')
s.text(55,170,720,'0.7455',142,MINT,True)
s.text(67,347,681,'Лучший скор платформы по данным команды\nАвтоматическая конфигурация probe 35',24,'#B0C6B8')
s.rect(846,180,374,260,'#1B3229',12)
s.text(872,206,326,'Что объединяет решение',23,'#E8F0E5',True)
s.text(872,273,315,'Физика сигнала\nОбучаемая модель\nИзмеримые эксперименты',24,MINT)
s.text(62,477,1150,'Следующий шаг — воспроизвести и зафиксировать финальную версию.',25,'#E5EEE4',True)
s.text(63,537,1145,'Границы: ручная разметка test запрещена; демонстрационные слои не доказывают работу модели в регионе.',22,'#D3B77F')
s.note('После стоп-кода оцениваемые материалы меняются только с разрешения организатора. Этот комплект не загружен в конкурсную систему.')

# Export the scene graph for tests, review and future text edits.
(ROOT/'slides.json').write_text(json.dumps([{'title':s.title,'source':s.source,'items':s.items} for s in slides],ensure_ascii=False,indent=2),encoding='utf-8')

def rgb(s):return RGBColor.from_string(s.lstrip('#'))
prs=Presentation();prs.slide_width=Inches(W/96);prs.slide_height=Inches(H/96)
prs.core_properties.title='КосмоФАЙР-2 — двухэтапный мониторинг природных пожаров'
prs.core_properties.subject='Защита по архиву проекта, 20 сентября 2026'
prs.core_properties.author='Команда проекта'
prs.core_properties.comments='Исходные TXT/MD недоступны; версия восстановлена по архиву и сообщению команды. Скор не проверен на платформе.'
articles=[]
for num,s in enumerate(slides,1):
    page=prs.slides.add_slide(prs.slide_layouts[6]);parts=[]
    for o in s.items:
        x,y,w,h=[o[k] for k in ('x','y','w','h')]
        style=f'left:{x}px;top:{y}px;width:{w}px;height:{h}px;'
        if o['type']=='rect':
            shape=page.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE if o['radius'] else MSO_SHAPE.RECTANGLE,Inches(x/96),Inches(y/96),Inches(w/96),Inches(h/96))
            if o['radius']:
                try:shape.adjustments[0]=min(.16,o['radius']/min(w,h))
                except (IndexError,ZeroDivisionError):pass
            shape.fill.solid();shape.fill.fore_color.rgb=rgb(o['fill'])
            if o['stroke']:shape.line.color.rgb=rgb(o['stroke']);shape.line.width=Pt(1.5)
            else:shape.line.fill.background()
            parts.append(f'<div class="shape" style="{style}background:{o["fill"]};border-radius:{o["radius"]}px;'+(f'border:2px solid {o["stroke"]};' if o['stroke'] else '')+'"></div>')
        elif o['type']=='text':
            shape=page.shapes.add_textbox(Inches(x/96),Inches(y/96),Inches(w/96),Inches(h/96))
            tf=shape.text_frame;tf.clear();tf.word_wrap=False;tf.margin_left=tf.margin_right=tf.margin_top=tf.margin_bottom=0;tf.vertical_anchor=MSO_ANCHOR.TOP
            for i,line in enumerate(o['text'].split('\n')):
                p=tf.paragraphs[0] if i==0 else tf.add_paragraph();p.text=line;p.font.name=FONT;p.font.size=Pt(o['size']*.75);p.font.bold=o['bold'];p.font.color.rgb=rgb(o['color']);p.space_before=Pt(0);p.space_after=Pt(0);p.line_spacing=1.22
            parts.append(f'<div class="txt" style="{style}font-size:{o["size"]}px;color:{o["color"]};font-weight:{700 if o["bold"] else 400}">{html.escape(o["text"])}</div>')
        else:
            path=ROOT/o['path'];page.shapes.add_picture(str(path),Inches(x/96),Inches(y/96),Inches(w/96),Inches(h/96))
            data=base64.b64encode(path.read_bytes()).decode();parts.append(f'<img alt="{html.escape(o["path"])}" style="{style}" src="data:image/png;base64,{data}">')
    articles.append(f'<article id="slide-{num}" aria-label="Слайд {num}: {html.escape(s.title)}">'+''.join(parts)+'</article>')
prs.save(ROOT/'КосмоФАЙР-2_защита.pptx')
fontcss=''.join('@font-face{font-family:"DejaVu Sans";font-weight:'+str(weight)+';src:url(data:font/ttf;base64,'+base64.b64encode((FONT_DIR/name).read_bytes()).decode()+') format("truetype");}' for weight,name in [(400,'DejaVuSans.ttf'),(700,'DejaVuSans-Bold.ttf')])
css='''*{box-sizing:border-box}html,body{margin:0;background:#0b1512;font-family:"DejaVu Sans",Arial,sans-serif}article{width:1280px;height:720px;position:relative;overflow:hidden;break-after:page}article:last-child{break-after:auto}.shape,.txt,img{position:absolute}.txt{white-space:pre;line-height:1.22}.shell{margin:24px auto 90px}.stage{transform-origin:top left}body.ready article{display:none}body.ready article.active{display:block}nav{position:fixed;bottom:14px;left:50%;transform:translateX(-50%);display:flex;gap:12px;align-items:center;background:#152d23;border:1px solid #42644f;padding:10px;border-radius:10px;color:#c3e6cc;font-size:13px;z-index:20}button,a{background:none;color:inherit;border:1px solid #527760;border-radius:6px;padding:8px 12px;cursor:pointer;text-decoration:none;font:inherit}button:focus-visible,a:focus-visible{outline:3px solid #b6f0c9}button:disabled{opacity:.35}@page{size:1280px 720px;margin:0}@media print{.shell{margin:0!important;width:1280px!important;height:auto!important}.stage{transform:none!important}body.ready article{display:block}nav{display:none}}'''
js='''(()=>{const ss=[...document.querySelectorAll('article')],n=ss.length;let i=0;const prev=document.querySelector('#prev'),next=document.querySelector('#next'),counter=document.querySelector('#counter');function fit(){let z=Math.min((innerWidth-24)/1280,(innerHeight-110)/720);z=Math.max(.1,z);document.querySelector('.stage').style.transform=`scale(${z})`;let sh=document.querySelector('.shell');sh.style.width=1280*z+'px';sh.style.height=720*z+'px'}function show(k){i=Math.max(0,Math.min(n-1,k));ss.forEach((s,j)=>{s.classList.toggle('active',j===i);s.setAttribute('aria-hidden',String(j!==i))});counter.textContent=`${i+1} / ${n}`;prev.disabled=i===0;next.disabled=i===n-1;history.replaceState(null,'',`#slide-${i+1}`)}document.body.classList.add('ready');prev.onclick=()=>show(i-1);next.onclick=()=>show(i+1);onhashchange=()=>show((parseInt(location.hash.replace('#slide-',''))||1)-1);onresize=fit;onkeydown=e=>{if(e.key==='ArrowRight'||e.key==='PageDown'||e.key===' '){e.preventDefault();show(i+1)}if(e.key==='ArrowLeft'||e.key==='PageUp'){e.preventDefault();show(i-1)}if(e.key==='Home')show(0);if(e.key==='End')show(n-1)};onbeforeprint=()=>ss.forEach(s=>s.removeAttribute('aria-hidden'));onafterprint=()=>show(i);show((parseInt(location.hash.replace('#slide-',''))||1)-1);fit()})();'''
(ROOT/'index.html').write_text('<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>КосмоФАЙР-2 — защита</title><style>'+fontcss+css+'</style></head><body><main class="shell"><div class="stage">'+''.join(articles)+'</div></main><nav aria-label="Управление презентацией"><button id="prev" aria-label="Предыдущий слайд">←</button><span id="counter" aria-live="polite"></span><button id="next" aria-label="Следующий слайд">→</button><a href="КосмоФАЙР-2_защита.pptx" download>PPTX</a><a href="КосмоФАЙР-2_защита.pdf" download>PDF</a></nav><script>'+js+'</script></body></html>',encoding='utf-8')
text=['КОСМОФАЙР-2 — НОВАЯ СТРУКТУРА ПО АРХИВУ','Это не конвертация недоступного исходного TXT. Редакция 20.09.2026.','']
for i,s in enumerate(slides,1):
    text.extend([f'СЛАЙД {i:02}. {s.title or "КосмоФАЙР-2. Огонь найти. Последствия измерить."}'])
    text.extend(o['text'] for o in s.items if o['type']=='text' and o['y']>70 and o['y']<673)
    text.extend(['Источник: '+s.source,''])
(ROOT/'КосмоФАЙР-2_структура.txt').write_text('\n'.join(text),encoding='utf-8-sig')
print('Built',len(slides),'slides; editable PPTX + offline HTML + reconstructed TXT')
