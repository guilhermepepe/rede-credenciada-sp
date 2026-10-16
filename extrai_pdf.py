# -*- coding: utf-8 -*-
"""Extrai a lista 'Encontre seu Dentista' do PDF para JSON."""
import re, json, sys, collections
import pdfplumber

ORDEM=['cro','nome','data','esp','end','tel','cel','atend']
TIT={'CRO/CNPJ':'cro','Nome':'nome','Data':'data','Atuação':'esp','Endereço':'end',
     'Telefone':'tel','Celular':'cel','Atendimento':'atend'}
COLS=[('cro',0,130),('nome',130,255),('data',255,322),('esp',322,425),
      ('end',425,556),('tel',556,616),('cel',616,678),('atend',678,900)]

def bandas(pag):
    """Le a posicao das colunas no cabecalho da propria pagina."""
    ws=pag.extract_words(x_tolerance=1.2,y_tolerance=0.5)
    pos={}
    for w in ws:
        c=TIT.get(w['text'])
        if c and c not in pos: pos[c]=w['x0']
    if len(pos)<len(ORDEM): return None
    xs=[pos[c] for c in ORDEM]
    out=[]
    for i,c in enumerate(ORDEM):
        a=0 if i==0 else xs[i]-2
        b=900 if i==len(ORDEM)-1 else xs[i+1]-2
        out.append((c,a,b))
    return out
CAB={'CRO/CNPJ','Nome','Data','de','Associação','Atuação','Endereço','Telefone','Celular','Atendimento'}
RE_CNPJ=re.compile(r'^\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}$')
RE_CRO=re.compile(r'^\d{3,7}[A-Z]?$')
RE_VINC=re.compile(r'^\d{3,7}[A-Z]?/(?:\d{3,7}[A-Z]?|\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})$')
RE_CEP=re.compile(r'(\d{5}-\d{3})')

VOCAB=['CIRURGIA','CIRURGIA BUCO MAXILO FACIAL','CLÍNICO GERAL','DENTÍSTICA','DIAGNOSTICO',
       'EMERGÊNCIA','ENDODONTIA','ESTOMATOLOGIA','ODONTOPEDIATRIA','PERIODONTIA','PREVENCAO',
       'PROTESE','RADIOLOGIA','URGÊNCIA','URGÊNCIA 24H']
VOCAB_ORD=sorted(VOCAB,key=len,reverse=True)
RE_FONE=re.compile(r'\(\d{2}\)\s*\d{4,5}-?\d{4}')

def linhas(pag,COLS):
    ws=pag.extract_words(x_tolerance=1.2,y_tolerance=0.5,keep_blank_chars=False)
    ws=sorted(ws,key=lambda w:(w['top'],w['x0']))
    g=[]; atual=[]; base=None
    for w in ws:                      # agrupa por linha visual, nao por faixa fixa
        if base is None or w['top']-base<=4.2: 
            if base is None: base=w['top']
            atual.append(w)
        else:
            g.append(atual); atual=[w]; base=w['top']
    if atual: g.append(atual)
    out=[]
    for grp in g:
        ws2=sorted(grp,key=lambda w:w['x0'])
        cel={c:[] for c,_,_ in COLS}
        for w in ws2:
            for c,a,b in COLS:
                if a<=w['x0']<b: cel[c].append(w['text']); break
        d={c:' '.join(v).strip() for c,v in cel.items()}
        d['_top']=min(w['top'] for w in ws2)
        out.append(d)
    return out

def extrai(caminho):
    pdf=pdfplumber.open(caminho)
    regs=[]; cidade=bairro=''; atual=None
    cols=None
    for pag in pdf.pages:
        txt=pag.extract_text() or ''
        if txt.lstrip().startswith('Legenda'): continue
        b=bandas(pag)
        if b: cols=b
        if cols is None: continue
        imgs=[im['top'] for im in (pag.images or [])]
        napag=[]
        for L in linhas(pag,cols):
            junto=' '.join(L[c] for c,_,_ in cols).strip()
            if not junto: continue
            if re.match(r'^\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}$',junto) or 'Encontre seu Dentista' in junto \
               or junto.startswith('Profissionais em') or junto.startswith('Página '): continue
            if set(junto.split())<=CAB: continue
            if junto.startswith('Legenda'): atual=None; break   # bloco de legenda no fim
            m=re.match(r'^Hor[áa]rios de Atendimento:\s*(.*)$',junto)
            if m:                                   # linha larga no rodape da pagina
                if atual is not None:
                    atual['atend']=(atual['atend']+' '+m.group(1)).strip()
                continue
            c0=L['cro']
            m=re.match(r'^Cidade:\s*(.+)$',junto)
            if m: cidade=m.group(1).strip(); atual=None; continue
            m=re.match(r'^Bairro:\s*(.+)$',junto)
            if m: bairro=m.group(1).strip(); atual=None; continue
            novo = RE_CNPJ.match(c0) or RE_CRO.match(c0) or RE_VINC.match(c0)
            if novo:
                tipo = 2 if RE_VINC.match(c0) else (0 if RE_CNPJ.match(c0) else 1)
                atual={'cidade':cidade,'bairro':bairro,'id':c0,'tipo':tipo,'nome':L['nome'],
                       'data':L['data'],'esp':L['esp'],'end':L['end'],'tel':L['tel'],
                       'cel':L['cel'],'atend':L['atend'],'y0':L['_top'],'y1':L['_top'],'selo':0}
                regs.append(atual); napag.append(atual); continue
            if atual is None: continue
            atual['y1']=L['_top']
            for c in ('nome','esp','end','tel','cel','atend'):
                if L[c]: atual[c]=(atual[c]+' '+L[c]).strip()
            if L['data'] and not atual['data']: atual['data']=L['data']
        for y in imgs:                       # o selo fica na linha do credenciado
            cand=[r for r in napag if r['y0']<=y+2]
            alvo=cand[-1] if cand else (regs[-1] if regs else None)
            if alvo is not None: alvo['selo']=1
    pdf.close()
    # pos-processamento
    for r in regs:
        r['nome']=re.sub(r'\s+',' ',r['nome']).strip()
        r['end']=re.sub(r'\s+',' ',r['end']).strip()
        itens=[e.strip() for e in re.sub(r'\s+',' ',r['esp']).split(',') if e.strip()]
        r['esp']=[]; sobra=[]
        for it in itens:
            if it in VOCAB: r['esp'].append(it); continue
            resto=it                                  # quebra itens grudados
            while resto:
                for v in VOCAB_ORD:
                    if resto.startswith(v): r['esp'].append(v); resto=resto[len(v):].strip(); break
                else:
                    sobra.append(resto); resto=''
        if sobra: r['atend']=(r['atend']+' '+' '.join(sobra)).strip()
        m=RE_CEP.search(r['end'])
        r['cep']=m.group(1) if m else ''
        r['endereco']=re.sub(r'\s*,?\s*'+re.escape(r['cep'])+r'\s*$','',r['end']).strip().rstrip(',').strip() if r['cep'] else r['end']
        r['vinculado_a']=''
        m=re.search(r'\s*-\s*\[(.+)\]\s*$',r['nome'])
        if m: r['vinculado_a']=m.group(1).strip(); r['nome']=r['nome'][:m.start()].strip()
        # telefones podem cair na coluna vizinha: reparte pelo conteudo
        junta=re.sub(r'\s+',' ',(r['tel']+' '+r['cel']+' '+r['atend'])).strip()
        fones=RE_FONE.findall(junta)
        resto=RE_FONE.sub(' ',junta)
        resto=re.sub(r'(?<!\d)\d{8,9}(?!\d)',' ',resto)        # numero solto sem o DDD
        r['tel']=fones[0] if len(fones)>1 else ''
        r['cel']=fones[-1] if fones else ''
        r['atend']=re.sub(r'\s+',' ',resto).strip(' ,;/-')
        if not re.search(r'[A-Za-zÀ-ú]',r['atend']): r['atend']=''
        r.pop('y0',None); r.pop('y1',None)
        r['cro']='' if r['tipo']==0 else r['id'].split('/')[0]
        r['cnpj']=r['id'] if r['tipo']==0 else ('/'.join(r['id'].split('/')[1:]) if r['tipo']==2 else '')
    return regs

if __name__=='__main__':
    regs=extrai(sys.argv[1])
    json.dump(regs,open(sys.argv[2],'w'),ensure_ascii=False)
    print('registros:',len(regs))
    print('por tipo:',collections.Counter(r['tipo'] for r in regs))
    print('cidades:',len(set(r['cidade'] for r in regs)))
    print('sem CEP:',sum(1 for r in regs if not r['cep']))
    for r in regs[:2]: print(json.dumps(r,ensure_ascii=False)[:300])
