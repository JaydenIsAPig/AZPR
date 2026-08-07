#!/usr/bin/env python3
"""Offline verifier for the frozen AZPR v9 corrective implementation candidate."""
from __future__ import annotations
import argparse, ast, hashlib, json, os, re, signal, stat, subprocess, sys, tempfile
from pathlib import Path, PurePosixPath
from zipfile import ZipFile

ROOT=Path(__file__).resolve().parent
MAX_OUTPUT=8*1024*1024
PROMPT_SHA='3b235cb7e33ca409241ff26523f60f8fee89cec524b3f09e91a69927a0aa4880'

def progress(msg:str)->None:
    if os.environ.get('AZPR_VERIFY_PROGRESS')=='1': print(f'[verify-v9] {msg}',file=sys.stderr,flush=True)
def fail(msg:str): raise SystemExit(f'VERIFY V9 FAILED: {msg}')
def sha(path:Path)->str:
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()
def load(path:Path):
    try: value=json.loads(Path(path).read_bytes())
    except Exception as exc: fail(f'invalid JSON {path.relative_to(ROOT)}: {exc}')
    if not isinstance(value,dict): fail(f'JSON must be object: {path.relative_to(ROOT)}')
    return value

def run_group(command:list[str],*,env:dict[str,str],timeout:int,label:str):
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        proc=subprocess.Popen(command,cwd=ROOT,env=env,stdout=out,stderr=err,start_new_session=True)
        timed=False
        try: proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed=True
            try: os.killpg(proc.pid,signal.SIGKILL)
            except ProcessLookupError: pass
            proc.wait(timeout=10)
        out.seek(0);err.seek(0);ob=out.read(MAX_OUTPUT+1);eb=err.read(MAX_OUTPUT+1)
    if len(ob)>MAX_OUTPUT or len(eb)>MAX_OUTPUT: fail(f'{label} output limit exceeded')
    if timed: fail(f'{label} timed out')
    return proc.returncode,ob.decode('utf-8','replace'),eb.decode('utf-8','replace')

def verify_safety():
    d=load(ROOT/'REMEDIATION-STATUS.json'); decision=d.get('decision',{})
    if d.get('candidate')!='AZPR-autonomous-execution-primed-draft-v9': fail('candidate identity mismatch')
    if decision.get('status')!='V9_CORRECTIVE_IMPLEMENTATION_CANDIDATE_INDEPENDENT_REASSESSMENT_REQUIRED': fail('status mismatch')
    if decision.get('safe_for_unattended_execution_now') is not False or decision.get('trusted_pre_autonomous_installation_ready') is not False: fail('readiness flags changed')
    if decision.get('organization_release_signature_status')!='NOT_PROVIDED_UNSIGNED_DEVELOPMENT_CANDIDATE': fail('unsigned status missing')
    forbidden=[ROOT/'repository-overlay/automation/roadmap.json',ROOT/'repository-overlay/automation/roadmap.proposed.json',ROOT/'repository-overlay/automation/policy/AZPR-master-operating-prompt.md',ROOT/'repository-overlay/automation/policy/canonical-policy-section-map.json']
    for p in forbidden:
        if p.exists(): fail(f'forbidden active authority: {p.relative_to(ROOT)}')
    for p in ROOT.rglob('*'):
        if p.name in {'__pycache__','.pytest_cache'} or p.suffix in {'.pyc','.pyo'}: fail(f'cache artifact present: {p.relative_to(ROOT)}')

def verify_python()->int:
    paths=sorted(p for p in ROOT.rglob('*.py') if '__pycache__' not in p.parts)
    for p in paths:
        try: source=p.read_text(); compile(source,str(p),'exec'); ast.parse(source,filename=str(p))
        except Exception as exc: fail(f'Python syntax: {p.relative_to(ROOT)}: {exc}')
    return len(paths)

def verify_schemas()->int:
    try:
        import jsonschema
        from referencing import Registry,Resource
    except ImportError: fail('jsonschema/referencing unavailable')
    reg=Registry();schemas={}
    for p in sorted((ROOT/'repository-overlay/automation/schemas').glob('*.json')):
        v=load(p)
        try: jsonschema.Draft202012Validator.check_schema(v);r=Resource.from_contents(v)
        except Exception as exc: fail(f'schema invalid {p.name}: {exc}')
        schemas[p.name]=v;reg=reg.with_resource(p.name,r)
        if isinstance(v.get('$id'),str): reg=reg.with_resource(v['$id'],r)
    required={'cleanroom-qualification-receipt-v9.schema.json','qualified-artifact-inputs-v9.schema.json','qualification-installation-authorization-v9.schema.json','qualification-phase-transition-authorization-v9.schema.json','qualification-probe-result-envelope-v9.schema.json','qualification-probe-envelopes-manifest-v9.schema.json','qualification-raw-evidence-v9.schema.json','host-bootstrap-roots-v9.schema.json','external-receipt-signing-request-v9.schema.json','external-receipt-signing-response-v9.schema.json','key-lifecycle-transition-v9.schema.json','trust-store-epoch-v9.schema.json'}
    if not required.issubset(schemas): fail(f'missing v9 schemas: {sorted(required-set(schemas))}')
    for name in required:
        if schemas[name].get('additionalProperties') is not False: fail(f'non-strict v9 schema: {name}')
    bindings=schemas['cleanroom-qualification-receipt-v9.schema.json']['properties']['artifact_bindings']
    if len(bindings.get('required',[]))!=39 or set(bindings['required'])!=set(bindings['properties']): fail('receipt does not require exact 39 bindings')
    if 'qualification_probe_envelopes_manifest' in bindings['required'] or 'key_lifecycle_state' not in bindings['required']: fail('v9 binding contract mismatch')
    return len(schemas)

def front(text:str,path:Path):
    if not text.startswith('---\n'): fail(f'front matter missing: {path.name}')
    end=text.find('\n---\n',4)
    if end<0: fail(f'front matter unterminated: {path.name}')
    out={}
    for line in text[4:end].splitlines():
        if ':' in line:
            k,v=line.split(':',1);out[k.strip()]=v.strip().strip('"\'')
    return out

def verify_prompts():
    auto=ROOT/'repository-overlay/automation';numbered=sorted((auto/'numbered').glob('*.md'));apps=sorted((auto/'appendices').glob('*.md'))
    if len(numbered)!=38 or len(apps)!=3: fail('prompt count differs from 38+3')
    expected={};ids=set()
    for p in numbered:
        text=p.read_text();m=front(text,p);pid=m.get('prompt_id')
        if pid not in {f'{i:03d}' for i in range(1,39)} or not p.name.startswith(pid+'-') or int(m.get('sequence','-1'))!=int(pid) or text.count('BEGIN PROMPT')!=1 or text.count('END PROMPT')!=1: fail(f'numbered prompt invalid: {p.name}')
        ids.add(pid);expected[p.relative_to(ROOT/'repository-overlay').as_posix()]=p.read_bytes()
    for p in apps:
        text=p.read_text();m=front(text,p)
        if m.get('appendix_id') not in {'A','B','C'} or m.get('normal_execution_eligible')!='false' or m.get('requires_explicit_invocation')!='true' or text.count('BEGIN PROMPT')!=1 or text.count('END PROMPT')!=1: fail(f'appendix invalid: {p.name}')
        expected[p.relative_to(ROOT/'repository-overlay').as_posix()]=p.read_bytes()
    zp=ROOT/'markdown-prompts-autonomous-priming-draft.zip'
    if sha(zp)!=PROMPT_SHA: fail('embedded prompt archive hash mismatch')
    with ZipFile(zp) as z:
        if len(z.namelist())!=len(set(z.namelist())) or set(z.namelist())!=set(expected): fail('prompt ZIP inventory mismatch')
        for i in z.infolist():
            pp=PurePosixPath(i.filename);mode=(i.external_attr>>16)&0o170000
            if pp.is_absolute() or '..' in pp.parts or '\\' in i.filename or (mode and mode!=stat.S_IFREG): fail(f'unsafe prompt member: {i.filename}')
            if z.read(i.filename)!=expected[i.filename]: fail(f'prompt byte mismatch: {i.filename}')
    return len(numbered),len(apps),sha(zp)

def verify_controls()->int:
    files={
      'installer':'trusted-installation/install.py','tx':'trusted-installation/v9_transaction.py','binding':'trusted-installation/v9_binding.py','verifier':'operator-tools/verify_v9_cleanroom_prerequisites.py','probe':'operator-tools/v9_probe_boundary.py','signer':'operator-tools/v9_external_signer_client.py','derive':'operator-tools/v9_evidence_derivation.py','life':'operator-tools/apply_key_lifecycle_transition_v9.py'}
    src={k:(ROOT/v).read_text() for k,v in files.items()}
    required={
      'installer':['InstallerGlobalLock(GLOBAL_INSTALLER_LOCK).acquire()','recovered=recover_activation_state()','_reserve_authorization(qualification)','verify_complete_artifact_bindings','verify_bootstrap_roots',"receipt['probe_envelopes_manifest_sha256']!=sha",'verify_phase_transition',"installation_phase=qualification['authorization']['installation_phase']",'_complete_authorization'],
      'tx':['fcntl.flock','PENDING.json','compare_and_publish','authorization ledger/anchor mismatch','authorization authorization' if False else 'qualification authorization sequence is not the exact next monotonic value','authorization ID replay','authorization nonce replay','COMPLETED_ANCHORED_PENDING_TRANSACTION'],
      'binding':['assert len(REQUIRED_QUALIFIED_ARTIFACTS) == 39','key_lifecycle_state','qualified artifact alias','caller-selected qualification, receipt, phase, or anchor root differs from pinned bootstrap','first installation may only be QUALIFICATION_ONLY'],
      'verifier':['v9 cleanroom verifier refuses root execution','never executes a qualified target','external_signer_client','verify_report_derivation','qualification_receipt_signing_private_key'],
      'probe':['run_as_uid','no_secrets','daemon_sockets','resource_exhaustion_contained','evidence_mutation_denied'],
      'signer':['external signer client identity mismatch','external receipt signature verification failed','request_nonce'],
      'derive':['raw evidence decisive check failed or missing','signed qualification measurements do not match machine-derived raw evidence'],
      'life':['TRUST_STORES','after_anchor','active trust epoch pointer rollback detected','ROLLED_BACK_UNANCHORED_EPOCH']}
    # Private-key name must be absent from executable verifier source.
    if 'qualification_receipt_signing_private_key' in src['verifier']: fail('receipt private-key material remains in v9 verifier')
    required['verifier'].remove('qualification_receipt_signing_private_key')
    count=0
    for label,tokens in required.items():
        for token in tokens:
            if token not in src[label]: fail(f'missing {label} control marker: {token}')
            count+=1
    return count

def catalog():
    rows=[]
    for p in sorted((ROOT/'tests').glob('test_*.py')):
        tree=ast.parse(p.read_text(),filename=str(p))
        for node in tree.body:
            if isinstance(node,ast.ClassDef):
                for child in node.body:
                    if isinstance(child,(ast.FunctionDef,ast.AsyncFunctionDef)) and child.name.startswith('test_'):
                        rows.append({'id':f'{p.stem}.{node.name}.{child.name}','node':f'{p.relative_to(ROOT)}::{node.name}::{child.name}'})
            elif isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name.startswith('test_'):
                rows.append({'id':f'{p.stem}.{node.name}','node':f'{p.relative_to(ROOT)}::{node.name}'})
    return sorted(rows,key=lambda x:x['id'])

def run_tests():
    rows=catalog(); ids=[r['id'] for r in rows]
    required={'test_v9_security_closures.test_f01_no_secret_probe_envelopes_never_execute_targets','test_v9_security_closures.test_f01_external_signing_protocol_has_no_receipt_private_key_in_verifier','test_v9_security_closures.test_f03_exact_39_bindings_and_each_substitution_fails','test_v9_security_closures.test_f02_f04_twenty_process_same_sequence_exactly_one_advances','test_v9_security_closures.test_f04_rollback_delete_restore_and_pending_recovery_fail_closed','test_v9_security_closures.test_f07_atomic_trust_epoch_and_interruption_recovery','test_v9_security_closures.test_installer_exact_enforcing_order_and_phase_not_policy_derived','test_v8_corrective_controls.V8CorrectiveControlTests.test_v8_blackbox_release_blocking_harness'}
    if not required.issubset(ids): fail(f'required test IDs absent: {sorted(required-set(ids))}')
    base={'PATH':os.environ.get('PATH','/usr/bin:/bin'),'PYTHONDONTWRITEBYTECODE':'1','PYTHONHASHSEED':'0','PYTEST_DISABLE_PLUGIN_AUTOLOAD':'1','LANG':'C.UTF-8','LC_ALL':'C.UTF-8','GIT_CONFIG_NOSYSTEM':'1'}
    results=[]
    for row in rows:
        progress('test '+row['id'])
        with tempfile.TemporaryDirectory(prefix='azpr-v9-test-',dir='/root') as td:
            env=dict(base,HOME=td,TMPDIR=td,XDG_CONFIG_HOME=str(Path(td)/'xdg'))
            rc,out,err=run_group([sys.executable,'-m','pytest','-q','-p','no:cacheprovider',row['node']],env=env,timeout=120,label=row['id'])
        if rc:
            print(out);print(err,file=sys.stderr);fail(f'test failed: {row["id"]}; exit={rc}')
        if not re.search(r'\b1 passed\b',out+err): fail(f'exact one-test result missing: {row["id"]}')
        results.append({'test_id':row['id'],'status':'PASS'})
    progress('v8 black-box harness')
    rc,out,err=run_group([sys.executable,str(ROOT/'operator-tools/v8_security_boundary_harness.py')],env=base,timeout=120,label='v8 black-box harness')
    if rc: print(out);print(err,file=sys.stderr);fail('v8 black-box harness failed')
    try: bb=json.loads(out)
    except Exception as exc: fail(f'black-box JSON invalid: {exc}')
    cases=bb.get('cases',[]);case_ids=sorted(x.get('id') for x in cases if isinstance(x,dict) and x.get('pass') is True)
    if bb.get('status')!='PASS' or len(case_ids)!=6: fail('black-box case mismatch')
    return len(rows),ids,results,case_ids

def verify_manifest()->int:
    d=load(ROOT/'SHA256SUMS.json')
    if d.get('format_version')!='1.0' or d.get('algorithm')!='SHA-256' or d.get('bundle_name')!='AZPR-autonomous-execution-primed-draft-v9' or d.get('bundle_type')!='implementation' or d.get('excludes')!=['SHA256SUMS.json']: fail('internal manifest metadata invalid')
    entries=d.get('entries');actual={p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*') if p.is_file() and p.name!='SHA256SUMS.json'}
    if not isinstance(entries,dict) or set(entries)!=actual: fail(f'internal inventory mismatch missing={sorted(actual-set(entries or {}))[:10]} extra={sorted(set(entries or {})-actual)[:10]}')
    if d.get('expected_inventory_count')!=len(entries): fail('manifest count mismatch')
    for rel,digest in entries.items():
        if not re.fullmatch(r'[0-9a-f]{64}',str(digest)) or sha(ROOT/rel)!=digest: fail(f'manifest hash mismatch: {rel}')
    return len(entries)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--fresh-extraction',action='store_true');args=ap.parse_args()
    verify_safety();py=verify_python();schemas=verify_schemas();num,apps,prompt=verify_prompts();markers=verify_controls();tests,ids,executions,bb=run_tests();manifest=verify_manifest()
    actual={'manifest_entries_verified':manifest,'python_files_compiled':py,'schemas_verified':schemas,'numbered_prompts_verified':num,'appendices_verified':apps,'security_tests_passed':tests,'control_markers_verified':markers,'prompt_zip_sha256':prompt,'security_test_ids':ids,'blackbox_case_ids':bb}
    expected=load(ROOT/'FINAL-VERIFICATION.json').get('verification',{})
    for key,value in actual.items():
        if expected.get(key)!=value: fail(f'FINAL-VERIFICATION mismatch {key}: expected={expected.get(key)!r} actual={value!r}')
    print(json.dumps({'status':'PASS_V9_CORRECTIVE_IMPLEMENTATION_INDEPENDENT_REASSESSMENT_REQUIRED','fresh_extraction_invocation':args.fresh_extraction,'safe_for_unattended_execution_now':False,'trusted_pre_autonomous_installation_ready':False,'organization_release_signature_status':'NOT_PROVIDED_UNSIGNED_DEVELOPMENT_CANDIDATE','test_execution':executions,**actual},indent=2,sort_keys=True))
if __name__=='__main__': main()
