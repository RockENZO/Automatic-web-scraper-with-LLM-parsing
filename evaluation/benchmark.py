"""Paired real-model benchmark on fixed synthetic HTML fixtures; never tune on results."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import platform
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import config
from content import extract_body_content, clean_body_content, split_dom_content
from parse import parse_with_ollama
from ollama_client import OllamaClient
from structured_content import extract_blocks, chunk_blocks
from structured_parse import extract_structured


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def score(predicted, expected, fields, source):
    def records(rows):
        return Counter(json.dumps({f:row.get(f) for f in fields},sort_keys=True,ensure_ascii=False) for row in rows)
    def field_items(rows):
        # Anchor each field to the first requested field to penalize cross-record mixing.
        return Counter((row.get(fields[0]),f,row.get(f)) for row in rows for f in fields if row.get(f) is not None)
    def counts(pred,truth):
        return {'tp':sum((pred&truth).values()),'predicted':sum(pred.values()),'expected':sum(truth.values())}
    nonnull=[row.get(f) for row in predicted for f in fields if row.get(f) is not None]
    return {'records':counts(records(predicted),records(expected)),
            'fields':counts(field_items(predicted),field_items(expected)),
            'unsupported_values':sum(not isinstance(value,str) or value not in source for value in nonnull),
            'predicted_nonnull_values':len(nonnull)}


def rates(counts):
    precision=counts['tp']/counts['predicted'] if counts['predicted'] else 0.0
    recall=counts['tp']/counts['expected'] if counts['expected'] else 0.0
    return {**counts,'precision':precision,'recall':recall,'f1':2*precision*recall/(precision+recall) if precision+recall else 0.0}


def decode_legacy(text, fields):
    # Free-text mode may concatenate JSON outputs from multiple chunks.
    # Tolerate Markdown fences but never repair values or deduplicate old outputs.
    text=text.replace('```json','').replace('```','').strip()
    if not text:
        return []
    decoder=json.JSONDecoder();rows=[]
    while text:
        obj,end=decoder.raw_decode(text)
        raw=obj['records'] if isinstance(obj,dict) else obj
        if not isinstance(raw,list) or any(not isinstance(row,dict) or set(row)!=set(fields) or any(v is not None and not isinstance(v,str) for v in row.values()) for row in raw):
            raise ValueError('Free-text JSON does not match requested fields')
        rows.extend(raw);text=text[end:].strip()
    return rows


class RecordedClient(OllamaClient):
    def __init__(self,model,traces):
        super().__init__(model);self.traces=traces
    def invoke(self,prompt,schema=None):
        start=time.perf_counter()
        try:
            response=super().invoke(prompt,schema)
            self.traces.append({'model':self.model,'prompt_sha256':hashlib.sha256(prompt.encode()).hexdigest(),'structured_format':schema is not None,'response':response,'seconds':time.perf_counter()-start})
            return response
        except Exception as error:
            self.traces.append({'model':self.model,'error_type':type(error).__name__,'seconds':time.perf_counter()-start})
            raise


def run(model,output):
    if output.exists():
        raise ValueError('Benchmark output already exists; preserve frozen results')
    manifest=json.loads((ROOT/'evaluation/fixtures/manifest.json').read_text())
    budget=manifest['chunk_budget']
    config.OLLAMA_MODEL=config.OLLAMA_FALLBACK_MODEL=model
    output.mkdir(parents=True)
    with urllib.request.urlopen(config.OLLAMA_BASE_URL.rstrip('/')+'/api/tags',timeout=10) as response:
        installed=json.load(response)['models']
    identity=next((item for item in installed if item['name']==model),None)
    if identity is None:raise ValueError('Model identity is not available')
    reports=[]
    fixture_hashes={}
    for index,case_id in enumerate(manifest['case_ids']):
        path=ROOT/'evaluation/fixtures'/(case_id+'.json');fixture_hashes[case_id]=sha(path)
        case=json.loads(path.read_text());blocks=extract_blocks(case['html'])
        source='\n'.join(block.text for block in blocks)
        # Alternate run order to reduce systematic warmup/order bias.
        variants=['legacy','structured'] if index%2==0 else ['structured','legacy']
        for variant in variants:
            traces=[];factory=lambda name:RecordedClient(name,traces)
            start=time.perf_counter();decode_error=None
            if variant=='legacy':
                text=clean_body_content(extract_body_content(case['html']))
                chunks=split_dom_content(text,budget)
                instruction=case['task']+' Use exactly these field names: '+', '.join(case['fields'])+'. Copy values verbatim; absent fields are null. Return ONLY a JSON object with a records array of field-value objects.'
                try:
                    result=parse_with_ollama(chunks,instruction,model_factory=factory)
                    rows=decode_legacy(result.text,case['fields'])
                    status=result.status;completed=result.completed_chunks;failed=result.failed_chunks
                except ValueError as error:
                    rows=[];status='failed';completed=0;failed=list(range(1,len(chunks)+1));decode_error=str(error)
                rejected=[];duplicates=0
            else:
                chunks=chunk_blocks(blocks,budget)
                result=extract_structured(chunks,case['task'],case['fields'],model_factory=factory)
                rows=[row['values'] for row in result.records]
                status=result.status;completed=result.completed_chunks;failed=result.failed_chunks
                rejected=result.rejected_records;duplicates=result.duplicate_records
            elapsed=time.perf_counter()-start
            report={'case':case_id,'variant':variant,'status':status,'seconds':elapsed,'total_chunks':len(chunks),'completed_chunks':completed,'failed_chunks':failed,'decode_error':decode_error,'rejected_records':rejected,'deduplicated_records':duplicates,'predictions':rows,'metrics':score(rows,case['expected'],case['fields'],source),'calls':len(traces)}
            (output/(case_id+'-'+variant+'.json')).write_text(json.dumps({'report':report,'traces':traces, 'grounded_records':result.records if variant=='structured' else None},ensure_ascii=False,indent=2)+'\n')
            reports.append(report)
            print(json.dumps({'case':case_id,'variant':variant,'status':status,'seconds':round(elapsed,2),'records':len(rows)},ensure_ascii=False),flush=True)
    aggregates={}
    for variant in ['legacy','structured']:
        subset=[r for r in reports if r['variant']==variant]
        metrics={kind:rates({key:sum(r['metrics'][kind][key] for r in subset) for key in ['tp','predicted','expected']}) for kind in ['records','fields']}
        unsupported=sum(r['metrics']['unsupported_values'] for r in subset);values=sum(r['metrics']['predicted_nonnull_values'] for r in subset)
        aggregates[variant]={**metrics,'unsupported_values':unsupported,'predicted_nonnull_values':values,'unsupported_value_rate':unsupported/values if values else 0.0,'total_seconds':sum(r['seconds'] for r in subset),'model_calls':sum(r['calls'] for r in subset),'failed_cases':sum(r['status']=='failed' for r in subset),'partial_cases':sum(r['status']=='partial' for r in subset),'no_match_case_correct':all(not r['predictions'] and r['status']!='failed' for r in subset if r['case']=='no_matches')}
    summary={'protocol':'all predefined synthetic regression fixtures; same real model and character budget; alternating variant order; one frozen run without result-driven tuning', 'model':identity,'runtime':{'python':platform.python_version(),'platform':platform.platform()},'chunk_budget':budget,'fixture_manifest_sha256':sha(ROOT/'evaluation/fixtures/manifest.json'),'fixture_hashes':fixture_hashes,'code_hashes':{f:sha(ROOT/f) for f in ['parse.py','content.py','structured_content.py','structured_parse.py','ollama_client.py','evaluation/benchmark.py']},'metrics_definitions':{'record':'micro multiset exact match over all requested fields, including nulls','field':'micro multiset exact match of (first-field record identity, field name, verbatim nonnull value)','unsupported_value':'nonnull output value absent from visible canonical source text; lexical grounding only, not semantic truth or instruction immunity','latency':'whole extraction wall time per case including retries and generation; excludes browser retrieval; one run, not a production throughput benchmark'},'aggregate':aggregates,'cases':reports,'limitations':['16 synthetic hand-specified fixtures; not a representative sample of live websites.','Grounding checks source presence, not correct field semantics or resistance to all prompt injections.','No OCR, pagination, CAPTCHA or live browser reliability measured.','Results apply only to this installed model/runtime; default gpt-oss and fallback models were not evaluated.']}
    (output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(aggregates,indent=2),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model',required=True)
    parser.add_argument('--output',type=Path,default=ROOT/'runs/structured-benchmark')
    args=parser.parse_args();run(args.model,args.output)
