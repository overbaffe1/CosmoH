"""Checks the deliverable, not the competition model or its platform score."""
from pathlib import Path
import json
import re
import zipfile
from decimal import Decimal
import pymupdf
from PIL import ImageFont
from pptx import Presentation

ROOT = Path(__file__).resolve().parent

def main():
    data = json.loads((ROOT/'slides.json').read_text(encoding='utf-8'))
    prs = Presentation(ROOT/'КосмоФАЙР-2_защита.pptx')
    pdf = pymupdf.open(ROOT/'КосмоФАЙР-2_защита.pdf')
    assert len(data) == len(prs.slides) == len(pdf) == 12
    assert abs(prs.slide_width/prs.slide_height - 16/9) < .00001
    texts=[]
    for i,(scene,page) in enumerate(zip(data,prs.slides),1):
        native=[shape.text for shape in page.shapes if shape.has_text_frame]
        assert len(native) >= 10, f'Slide {i} is not editable text'
        texts.extend(native)
        for obj in scene['items']:
            assert obj['x'] >= 0 and obj['y'] >= 0
            assert obj['x']+obj['w'] <= 1281
            assert obj['y']+obj['h'] <= 721, f'Object outside slide {i}'
            if obj['type']=='text':
                if obj['y']==80:
                    assert '\n' not in obj['text'], f'Wrapped title {i}'
                font=ImageFont.truetype(str(ROOT/'assets/fonts'/('DejaVuSans-Bold.ttf' if obj['bold'] else 'DejaVuSans.ttf')),round(obj['size']))
                assert all(font.getlength(line)<=obj['w'] for line in obj['text'].split('\n')), f'Text overflows {i}'
        assert len(pdf[i-1].get_text())>250
        assert abs(pdf[i-1].rect.width/pdf[i-1].rect.height-16/9)<.00001
    all_text='\n'.join(texts)
    assert all(term in all_text for term in ['0.7455','447','269','82','0.35','0.30','0.71282'])
    assert 'что говорить' not in all_text.lower()
    with zipfile.ZipFile(ROOT/'КосмоФАЙР-2_защита.pptx') as archive:
        for name in archive.namelist():
            if re.fullmatch(r'ppt/notesSlides/notesSlide\d+\.xml',name):
                assert not re.search(rb'<a:t>[^<]+</a:t>',archive.read(name)), 'Speaker notes must stay separate'
    assert sum([40,8,20,12,12,8])==100
    assert Decimal('.7455')-Decimal('.6979')==Decimal('.0476')
    assert Decimal('.35')*Decimal('.90934')+Decimal('.35')*Decimal('.61496')+Decimal('.30')*Decimal('.59772')==Decimal('.712821')
    audit=json.loads((ROOT/'audit-data.json').read_text())
    assert audit['rows']==447 and audit['chips']==269
    assert audit['sha256']=='3d233c7df09661b39028b3e73c0af01936f7bafca87414ca12ca75f8376146a7'
    assert audit['structural_RLE_check']=='PASS'
    assert audit['template_identity_check'].startswith('NOT RUN')
    assert not audit['identical_to_TOPsubmission'] and not audit['identical_to_default_submission']
    service=json.loads((ROOT/'service-check.json').read_text())
    assert service['all_contours_are_train'] and service['all_thermopoints_are_train']
    for path in ROOT.rglob('*'):
        if path.is_file() and path.suffix in {'.txt','.md','.json','.py','.cjs','.html'} and 'node_modules' not in path.parts:
            text=path.read_text(encoding='utf-8-sig')
            assert not re.search(r'AIza[\w-]{30,}|gh[pousr]_[A-Za-z0-9]{30,}',text), f'Possible credential: {path.name}'
    print('PASS: 12 editable slides / 12 PDF pages; text bounds, empty notes, facts, sources and credential-pattern check')

if __name__=='__main__':
    main()
