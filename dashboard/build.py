#!/usr/bin/env python3
"""Rebuild CGIAR dashboard v3.6 from source-faithful CSV. No networking or writes to Git.

See dashboard/README.md for the required schema and deterministic filtering rules.
"""
import argparse
from collections import Counter
import csv
import hashlib
from html import escape, unescape
import json
from pathlib import Path
import re
import sys
import zipfile

BASE = Path(__file__).resolve().parent
CONTRACT = BASE / 'config' / 'approved_dashboard_contract.json'
TEMPLATE = BASE / 'template.html'
EMPTY_TOKENS = {'not reported','not applicable','not specified'}


def load_csv(path):
    with path.open('r', encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError('Empty CSV or missing header')
        rows = list(reader)
    return rows


def split_outside_parentheses(text):
    chunks=[];buf=[];depth=0
    for char in text or '':
        if char=='(':depth+=1
        elif char==')':depth=max(0,depth-1)
        if char in ',;' and depth==0:
            chunks.append(''.join(buf));buf=[]
        else:buf.append(char)
    chunks.append(''.join(buf))
    return chunks


def carry_forward_bibliography(rows, old_rows, contract):
    """Carry only provider enrichment fields by stable filename; source-coded data always win."""
    enrichment=[name for name in contract['expected_columns'] if name.startswith(('lens_','openalex_'))]
    old_by_id={}
    for row in old_rows:
        identifier=row.get('Filenames','').strip()
        if not identifier or identifier in old_by_id:
            raise ValueError('Blank or duplicate filename in bibliography CSV: '+repr(identifier))
        old_by_id[identifier]=row
    carried=0
    for row in rows:
        identifier=row.get('Filenames','').strip()
        previous=old_by_id.get(identifier)
        if previous:
            for field in enrichment:
                if not row.get(field,'').strip():
                    row[field]=previous.get(field,'')
                    if row[field]:carried+=1
        for field in enrichment:row.setdefault(field,'')
    return carried


def sentence_case_product(value):
    """Display-only normalisation; source CSV values are left untouched."""
    name=str(value or '').strip()
    return name[:1].upper()+name[1:].lower() if name else ''


def parse_names(text, exclude_missing=True, preserve_parentheses=False):
    found=[]
    for piece in (split_outside_parentheses(text) if preserve_parentheses else re.split(r'\s*[;,]\s*', text or '')):
        name=piece.strip()
        if name and (not exclude_missing or name.casefold() not in EMPTY_TOKENS) and name not in found:
            found.append(name)
    return found


def parse_country(text):
    if not text.strip():
        return []
    codes = sorted({x.strip().upper() for x in re.split(r'[;,]',text) if x.strip()})
    for code in codes:
        if not re.fullmatch(r'[A-Z]{3}',code):
            raise ValueError(f'Unexpected country code {code!r}; edit and revalidate source')
    return codes


def extract_code_values(text, allowed, label):
    if not text.strip():return []
    codes=[]
    for part in text.split('|||'):
        part=part.strip()
        if not part:continue
        match=re.match(r'^(\d+)\s*\.', part)
        if not match:
            raise ValueError(f'Unrecognised {label} code: {part!r}')
        code=match.group(1)
        if code == '90':continue  # Source: explicit 'Not relevant', never treated as positive nature coding
        if code == '3' and label == 'Adaptation nature':
            raise ValueError('Legacy unmerged adaptation code 3 encountered; merge it in the source first')
        if code not in allowed:
            raise ValueError(f'Unexpected {label} code {code}: {part!r}')
        if code not in codes:codes.append(code)
    return codes


def binary(text, col):
    val=(text or '').strip()
    if val in ('','90','NA','N/A'):return None
    if val not in ('0','1'):
        raise ValueError(f'Unexpected {col} binary value: {val!r}')
    return val


def clean_abstract(value):
    # Strip JATS-like markup and collapse Unicode whitespace, preserving words and punctuation.
    text=str(value or '')
    tags=(r'jats:[A-Za-z-]+|mml:[A-Za-z-]+|AbstractText|CopyrightInformation|'
          r'abstract|p|i|b|sup|sub|em|strong|div|span|br|title')
    for _ in range(2):text=unescape(text)
    text=re.sub(r'</?(?:'+tags+r')\b[^<>]*>', ' ',text,flags=re.IGNORECASE)
    return ' '.join(text.split())


def pick_bibliography(row, key):
    # Explicit provider precedence: exact Lens, exact OpenAlex, manually verified publisher.
    if row.get('lens_match_status','').strip() == 'EXACT_DOI_MATCH' and row.get('lens_'+key,'').strip():
        return clean_abstract(row['lens_'+key]) if key == 'abstract' else row['lens_'+key].strip()
    if row.get('openalex_match_status','').strip() in {'EXACT_DOI_MATCH','MANUAL_PUBLISHER_RECOVERY'}:
        return clean_abstract(row.get('openalex_'+key) or '') if key=='abstract' else (row.get('openalex_'+key) or '').strip()
    return ''


def make_records(rows, contract):
    leaf_columns=contract['leaf_columns']
    master=contract['master_columns']
    valid_countries=contract['country_names']
    allowed_cols=set(contract['expected_columns'])
    missing=allowed_cols-set(rows[0])
    if missing:
        raise ValueError(f'Missing required source/enrichment columns: {sorted(missing)}')
    ids=set();result=[]
    for index,row in enumerate(rows,2):
        file_id=row['Filenames'].strip()
        if not file_id or file_id in ids:
            raise ValueError(f'Blank or duplicate Filenames at CSV row {index}: {file_id!r}')
        ids.add(file_id)
        raw_year=row['Year'].strip()
        if raw_year and not re.fullmatch(r'\d{4}',raw_year):
            raise ValueError(f'Invalid Year at CSV row {index}: {raw_year!r}')
        year=int(raw_year) if raw_year else None
        countries=parse_country(row['Country'])
        unknown_countries=set(countries)-set(valid_countries)
        if unknown_countries:
            raise ValueError(f'New ISO3 country code(s) {sorted(unknown_countries)} in {file_id}; update reviewed country-name mapping')
        themes=set()
        paths=[]
        nodes_in_order=[]
        for root in ['theme1','theme2','theme3','theme4','theme5']:
            subcolumns=[(col,definition) for col,definition in leaf_columns.items()
                        if definition['parent'].startswith(root+'-')]
            master_value=next((row[col].strip() for col,node in master.items() if node==root),'')
            child_groups=[]
            for col,definition in subcolumns:
                raw=(row.get(col) or '').strip()
                if not raw:continue
                mapping=definition['values']
                # Theme 5 purpose branches use independently coded method types from
                # AS:AV. Source cells can contain several approved codes separated
                # by |||, and combinations need not be pre-enumerated in the contract.
                pieces=([v.strip() for v in raw.split('|||') if v.strip()] if root=='theme5' else [raw])
                if any(piece not in mapping for piece in pieces):
                    raise ValueError(f'Unapproved thematic code at CSV row {index} ({file_id}) column {col!r}: {raw!r}. Update reviewed crosswalk first.')
                children=list(dict.fromkeys(node for piece in pieces for node in mapping[piece]))
                if children:child_groups.append((definition['parent'],children))
            if master_value or child_groups:
                themes.add(root);nodes_in_order.append(root)
            for parent,children in child_groups:
                if parent not in themes:
                    themes.add(parent);nodes_in_order.append(parent)
                for node in children:
                    if node not in themes:
                        themes.add(node);nodes_in_order.append(node)
                definition=next(d for col,d in leaf_columns.items() if d['parent']==parent)
                raw_value=next((row[col].strip() for col,d in leaf_columns.items() if d['parent']==parent),'')
                pieces=([v.strip() for v in raw_value.split('|||') if v.strip()] if root=='theme5' else [raw_value])
                for piece in pieces:
                    for path in definition['paths'].get(piece,[]):
                        if path not in paths:paths.append(path)
        node_ids=nodes_in_order
        region=(row.get('Region') or '').strip()
        trait={
          'adaptation_nature':extract_code_values(row['Adaptation nature'],{'1','2','4','5'},'Adaptation nature'),
          'mitigation_nature':extract_code_values(row['Mitigation nature'],{'1','2','3','4'},'Mitigation nature'),
          'adaptation_effectiveness':binary(row['Adaptation effectiveness'],'Adaptation effectiveness'),
          'adaptation_finance':binary(row['Adaptation finance'],'Adaptation finance'),
          'adaptation_cobenefits':binary(row['Adaptation with mitigation benefits'],'Adaptation with mitigation benefits'),
          'mitigation_quantitative':binary(row['Quantitative estimate of GHG mitigated'],'Quantitative estimate of GHG mitigated'),
          'mitigation_cobenefits':binary(row['Mitigation with adaptation benefits'],'Mitigation with adaptation benefits'),
        }
        lens_status=row.get('lens_match_status','').strip()
        rec={
          'id':file_id, 'title':row['Title'].strip(), 'year':year,
          'doi':row['DOI'].strip(), 'citation':(contract.get('manual_citation_overrides',{}).get(row['DOI'].strip()) if row.get('openalex_match_status','').strip()=='MANUAL_PUBLISHER_RECOVERY' else None) or row['Citation'].strip(),
          'countries':countries, 'crops':list(dict.fromkeys(sentence_case_product(name) for name in parse_names(row['Crop/livestock/tree/fish name (CLEAN)'],exclude_missing=False,preserve_parentheses=True))),
          'authors':pick_bibliography(row,'authors'),'source':pick_bibliography(row,'source_journal'),
          'journal':row['Journal'].strip(),
          'volume':pick_bibliography(row,'volume'),'issue':pick_bibliography(row,'issue'),
          'pages':pick_bibliography(row,'pages'),'abstract':pick_bibliography(row,'abstract'),
          'lens_id':row.get('lens_id','').strip() if lens_status=='EXACT_DOI_MATCH' else '',
          'lens_status':lens_status if lens_status=='EXACT_DOI_MATCH' else 'UNMATCHED',
          'theme_paths':paths,'theme_node_ids':node_ids,'traits':trait,
          'filter_crops':parse_names(row['Crop/livestock/tree/fish']),
          'region':region}
        if row.get('openalex_match_status','').strip()=='EXACT_DOI_MATCH':
            rec['openalex_id']=row.get('openalex_id','').strip()
            rec['openalex_status']='EXACT_DOI_MATCH'
        result.append(rec)
    return result


def make_tree(records, contract):
    # Counts are distinct article IDs and refresh with each dataset update.
    tree=json.loads(json.dumps(contract['tree']))
    counts=Counter(node for record in records for node in set(record['theme_node_ids']))
    def visit(node):
        node['count']=counts[node['id']]
        for c in node.get('children',[]):visit(c)
    for theme in tree['themes']:visit(theme)
    tree['meta']['records_total']=len(records)
    tree['meta']['generated_from']='Input CSV (verified CGIAR dashboard pipeline v3.6)'
    return tree


def build_frequency_centered_svg(counts):
    """Frequency-driven SVG: 5 ordered tiers and 3 fixed central leaders.

    The input is counts of DISTINCT articles after sentence-case normalisation.
    The original source cells and all counts are preserved.
    """
    import math
    import numpy as np
    from PIL import ImageFont
    W,H=2400,1350
    palette=('#666666','#e2b100','#756daf','#cb5f0b','#189673')
    def colour(n):
        return (palette[0] if n>=140 else palette[1] if n>=100 else
                palette[2] if n>=40 else palette[3] if n>=15 else palette[4])
    font_path='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    if not Path(font_path).is_file():
        font_path='/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf'
    if not Path(font_path).is_file():
        raise RuntimeError('DejaVu Sans or Liberation Sans is required for centred word cloud')
    occupancy=np.zeros((H//2,W//2),dtype=np.uint8)
    ordered=sorted(counts.items(),key=lambda p:(-p[1],p[0].casefold()))
    placed=[]
    def size(word,points,rotated):
        bb=ImageFont.truetype(font_path,points).getbbox(word)
        a,b=bb[2]-bb[0]+10,bb[3]-bb[1]+13
        return (b,a) if rotated else (a,b)
    def available(x,y,w,h):
        if x<9 or y<8 or x+w>W-9 or y+h>H-8:return False
        return not occupancy[max(0,y//2-3):min(H//2,(y+h)//2+3),
                             max(0,x//2-3):min(W//2,(x+w)//2+3)].any()
    def occupy(name,f,points,rotated,x,y,w,h):
        occupancy[y//2:(y+h)//2,x//2:(x+w)//2]=1
        placed.append((name,f,points,rotated,x,y,w,h))
    anchors={'Maize':(1200,665),'Rice':(1190,485),'Wheat':(1195,845)}
    # Anchor the three leading items only when they are present; otherwise all
    # terms are packed near the centre according to observed article frequency.
    done=set()
    for name,f in ordered:
        if name not in anchors:continue
        pts=int(round(17+111*(f/max(counts.values()))**0.60))
        pts=min(pts,128)
        w,h=size(name,pts,False)
        cx,cy=anchors[name];x=int(cx-w/2);y=int(cy-h/2)
        if available(x,y,w,h):
            occupy(name,f,pts,False,x,y,w,h);done.add(name)
    for index,(name,f) in enumerate(ordered):
        if name in done:continue
        points=int(round(16+111*(f/max(counts.values()))**0.64))
        rotations=[False,True] if (index%4==0 or (index>=26 and index%3==0)) else [False]
        found=None
        for shrink in (0,2,4,6):
            pts=max(14,points-shrink)
            for rotated in rotations:
                w,h=size(name,pts,rotated)
                offset=(index*2.39996323)%(2*math.pi)
                for step in range(1,8500):
                    radius=11*math.sqrt(step)
                    theta=offset+step*2.39996323
                    x=round(W/2+math.cos(theta)*radius*1.55-w/2)
                    y=round(H/2+math.sin(theta)*radius*.91-h/2)
                    if available(x,y,w,h):
                        found=(pts,rotated,x,y,w,h);break
                if found:break
            if found:break
        if not found:
            raise ValueError(f'Unable to place all {len(counts)} word-cloud terms; unplaced: {name}')
        occupy(name,f,*found)
    svg=['<svg role="img" aria-label="Frequency-proportional product word cloud" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 2400 1350" width="2400" height="1350" preserveAspectRatio="xMidYMid meet">',
         '<rect width="2400" height="1350" fill="#ffffff"/>']
    for name,f,points,rotated,x,y,w,h in placed:
        label=escape(name)
        tooltip=escape(f'{name}: {f} articles')
        if rotated:
            svg.append(f'<text transform="translate({x+w-6},{y+2}) rotate(90)" font-family="DejaVu Sans, Arial, sans-serif" font-size="{points}" dominant-baseline="text-before-edge" fill="{colour(f)}"><title>{tooltip}</title>{label}</text>')
        else:
            svg.append(f'<text x="{x+3}" y="{y+1}" font-family="DejaVu Sans, Arial, sans-serif" font-size="{points}" dominant-baseline="text-before-edge" fill="{colour(f)}"><title>{tooltip}</title>{label}</text>')
    svg.append('</svg>')
    return '\n'.join(svg)


def make_wordcloud(rows):
    try:
        from wordcloud import WordCloud
    except ImportError as error:
        raise RuntimeError('Install pinned dependencies with pip install -r dashboard/requirements.txt') from error
    counts=Counter(); articles=0
    for row in rows:
        names={sentence_case_product(name) for name in parse_names(row['Crop/livestock/tree/fish name (CLEAN)'])}
        if names:
            articles+=1;counts.update(names)
    if not counts:
        raise ValueError('No usable names in cleaned product-name column')
    svg=build_frequency_centered_svg(counts)
    ordered=sorted(counts.items(),key=lambda pair:(-pair[1],pair[0].casefold()))
    trs='\n'.join(f'<tr><td>{i}</td><td>{escape(name)}</td><td>{count}</td></tr>' for i,(name,count) in enumerate(ordered,1))
    section=f'''<section class="panel product-wordcloud-panel" id="productWordcloud" aria-label="Product word cloud">
<h2 class="atlas-chart-heading">Products represented in the articles</h2>
<div class="product-wordcloud-figure">{svg}</div>
<p class="product-wordcloud-caption">Word size represents the number of articles mentioning each named product. Frequency determines both font size and colour: grey (140+), yellow (100–139), purple (40–99), red-orange (15–39) and green (1–14). The highest-frequency terms are centred. Product names are standardised to sentence case before counting and plotting, so case-only variants are combined; original source values are unchanged. Based on {articles:,} articles with named products in the cleaned product-name field. All {len(counts):,} distinct names are included, including {sum(n==1 for n in counts.values()):,} mentioned in only one article. When multiple products are named in one article, each is counted once for that article. The full ranked frequency table is below.</p>
<details class="product-frequency-details" id="productFrequency"><summary>View all {len(counts):,} product names and article frequencies</summary>
<div class="product-frequency-controls"><label for="productFrequencySearch">Find a product</label><input id="productFrequencySearch" type="search" placeholder="Filter names in the frequency table" autocomplete="off"/><button id="productFrequencyClear" type="button">Clear search</button><span id="productFrequencyShown" aria-live="polite">{len(counts):,} products</span></div>
<div class="product-frequency-scroll"><table id="productFrequencyTable"><thead><tr><th scope="col">Rank</th><th scope="col">Product</th><th scope="col">Number of articles</th></tr></thead><tbody>{trs}</tbody></table></div>
</details>
</section>'''
    return section,ordered,articles


def build(csv_path,out_dir,contract_path=CONTRACT,template_path=TEMPLATE,bibliography=None):
    input_csv=Path(csv_path).resolve()
    if not input_csv.is_file():raise FileNotFoundError(input_csv)
    out_dir=Path(out_dir);out_dir.mkdir(parents=True,exist_ok=True)
    rows=load_csv(input_csv)
    contract=json.loads(Path(contract_path).read_text(encoding='utf8'))
    if not rows:raise ValueError('CSV contains zero records')
    carried=0
    if bibliography:
        bib_path=Path(bibliography).resolve()
        carried=carry_forward_bibliography(rows,load_csv(bib_path),contract)
    records=make_records(rows,contract)
    cloud_section,frequencies,articles_with_names=make_wordcloud(rows)
    metadata={'articles':len(records),'unmapped_articles':sum(not r['countries'] for r in records),
              'country_names':contract['country_names']}
    tree=make_tree(records,contract)
    html=Path(template_path).read_text(encoding='utf8')
    replacements={
      '__DASHBOARD_RECORDS_JSON__':json.dumps(records,ensure_ascii=False,separators=(',',':')),
      '__DASHBOARD_METADATA_JSON__':json.dumps(metadata,ensure_ascii=False,separators=(',',':')),
      '__THEME_TREE_JSON__':json.dumps(tree,ensure_ascii=False,separators=(',',':')),
      '__WORDCLOUD_SECTION__':cloud_section,
    }
    for before,after in replacements.items():
        if html.count(before)!=1:raise ValueError(f'Missing or duplicate template placeholder: {before}')
        html=html.replace(before,after,1)
    # Remove a stale fixed count in the note: bibliography is separately versioned.
    html=html.replace('Lens enrichment: 2641 exact DOI matches; missing fields not inferred.',
      f"Lens enrichment: {sum(r['lens_status']=='EXACT_DOI_MATCH' for r in records):,} exact DOI matches; missing fields not inferred.")
    # Guard HTML-embedded script: do not allow </script> to occur in data strings.
    # JSON scripts share one HTML document; this protects against accidental script termination.
    for record in records:
        if any('</script' in str(value).lower() for value in record.values()):
            raise ValueError(f'Embedded script tag in record {record["id"]}; clean before rendering')
    html_out=out_dir/'CGIAR_evidence_dashboard.html'
    html_out.write_text(html,encoding='utf8')
    freq_out=out_dir/'product_frequencies.csv'
    with freq_out.open('w',encoding='utf-8-sig',newline='') as handle:
        writer=csv.writer(handle);writer.writerow(['Rank','Product','Number of articles'])
        for i,(name,n) in enumerate(frequencies,1):writer.writerow([i,name,n])
    summary={
      'version':'3.6 locked dashboard rendering contract',
      'input_csv_sha256':hashlib.sha256(input_csv.read_bytes()).hexdigest(),
      'bibliography_csv_sha256':hashlib.sha256(Path(bibliography).read_bytes()).hexdigest() if bibliography else None,
      'bibliography_values_carried_forward':carried,
      'output_html_sha256':hashlib.sha256(html_out.read_bytes()).hexdigest(),
      'records':len(records),'missing_country_codes':metadata['unmapped_articles'],
      'named_product_articles':articles_with_names,'distinct_product_names':len(frequencies),
      'single_occurrence_product_names':sum(n==1 for _,n in frequencies),
      'lens_exact_doi_matches':sum(r['lens_status']=='EXACT_DOI_MATCH' for r in records),
      'top_level_theme_counts':{t['label']:t['count'] for t in tree['themes']},
      'principles':['No automatic thematic remapping','High-income ISO3 exclusions are map-only',
                    'All word-cloud products included','No data or secrets committed to Git'],
    }
    (out_dir/'build_manifest.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf8')
    zip_out=out_dir/'CGIAR_evidence_dashboard.zip'
    with zipfile.ZipFile(zip_out,'w',zipfile.ZIP_DEFLATED) as bundle:
        for path in (html_out,freq_out,out_dir/'build_manifest.json'):
            bundle.write(path,arcname=path.name)
    return summary,html_out,zip_out


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--csv',required=True,type=Path,help='Updated 63-column CSV (source data plus Lens/OpenAlex enrichment)')
    parser.add_argument('--out',required=True,type=Path,help='Output directory for HTML, CSV, manifest and ZIP')
    parser.add_argument('--bibliography',type=Path,help='Previous enriched CSV (carry Lens/OpenAlex metadata forward by Filenames)')
    args=parser.parse_args()
    try:manifest,html_file,zip_file=build(args.csv,args.out,bibliography=args.bibliography)
    except Exception as error:
        print(f'ERROR: {error}',file=sys.stderr);return 1
    print(json.dumps(manifest,indent=2))
    print(f'HTML: {html_file}\nZIP: {zip_file}')
    return 0

if __name__=='__main__':raise SystemExit(main())