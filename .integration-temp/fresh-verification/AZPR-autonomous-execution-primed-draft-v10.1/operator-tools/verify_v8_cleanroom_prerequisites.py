#!/usr/bin/env python3
"""Semantic, fail-closed AZPR v8 clean-room qualification evidence verifier.

This tool performs no installation and never enables policy, roadmap, Codex, or
external operations.  A successful receipt means only that the immutable
qualification evidence set is complete, signed, fresh, cross-bound, and
semantically reproducible enough to request a separate installation
authorization.
"""
from __future__ import annotations
import argparse,base64,hashlib,json,os,re,stat,subprocess,sys,zipfile
from datetime import datetime,timezone
from pathlib import Path
from typing import Any
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey,Ed25519PublicKey
import jsonschema
from referencing import Registry,Resource

ROOT=Path(__file__).resolve().parents[1]
SCHEMAS=ROOT/'repository-overlay/automation/schemas'
MAX_JSON=16*1024*1024;MAX_ARTIFACT=2*1024*1024*1024;HEX64=re.compile(r'^[0-9a-f]{64}$')
REPORT_ROLES={
 'codex_isolation_qualification_report':('CODEX_ISOLATION_QUALIFICATION','isolation-qualifier'),
 'remote_anchor_qualification_report':('REMOTE_ANCHOR_QUALIFICATION','anchor-qualifier'),
 'key_custody_qualification_report':('KEY_CUSTODY_QUALIFICATION','key-custody-qualifier'),
 'installer_fault_matrix_report':('INSTALLER_FAULT_MATRIX_QUALIFICATION','installer-fault-qualifier'),
 'supply_chain_rebuild_report':('SUPPLY_CHAIN_REBUILD_QUALIFICATION','build-qualifier'),
 'dedicated_host_policy':('DEDICATED_HOST_POLICY_QUALIFICATION','host-security-qualifier'),
}
ARTIFACT_SPECS={
 'bundle_zip':('implementation_bundle','regular'),'bundle_attestation':('release_attestation','json'),'bundle_signing_public_key':('release_verification_key','public_key'),
 'runtime_private_key':('controller_runtime_signing_key','secret_key'),'runtime_public_key':('controller_runtime_verification_key','public_key'),
 'evidence_private_key':('external_evidence_signing_key','secret_key'),'evidence_public_key':('external_evidence_verification_key','public_key'),
 'installation_signing_private_key':('installation_receipt_signing_key','secret_key'),'installation_signing_public_key':('installation_receipt_verification_key','public_key'),
 'qualification_receipt_signing_private_key':('qualification_receipt_signing_key','secret_key'),'qualification_receipt_signing_public_key':('qualification_receipt_verification_key','public_key'),
 'qualification_authorization_keyring':('qualification_authorization_keyring','json'),'qualification_revocation_list':('qualification_revocation_list','json'),
 'approval_keyring':('approval_authorization_keyring','json'),'evidence_keyring':('external_evidence_keyring','json'),
 'git_binary':('trusted_git_executable','executable'),'python_binary':('trusted_python_executable','executable'),'codex_binary':('pinned_codex_executable','executable'),
 'container_engine':('pinned_container_engine','executable'),'anchor_helper':('rollback_resistant_anchor_helper','executable'),
 'governing_policy_source':('master_operating_prompt_docx','regular'),'requirements_input':('dependency_requirements_input','regular'),'dependency_lock':('hash_locked_dependency_lock','regular'),
 'dependency_mirror_inventory':('offline_mirror_inventory','json'),'dependency_mirror_attestation':('offline_mirror_attestation','json'),'dependency_mirror_public_key':('offline_mirror_verification_key','public_key'),
 'sbom':('validation_image_sbom','json'),'build_provenance':('validation_image_build_provenance','json'),'validation_dockerfile':('validation_image_build_definition','regular'),
 'validation_image_attestation':('validation_image_attestation','json'),'validation_registry_proof':('validation_registry_proof','json'),
 'agent_execution_profile':('agent_execution_profile','json'),'handoff_quota_profile':('handoff_quota_profile','json'),
 **{name:(name.replace('_report',''),'qualification_report') for name in REPORT_ROLES},
}
REQUIRED_ARTIFACTS=frozenset(ARTIFACT_SPECS)

def canonical(v:Any)->bytes:return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def sha(path:Path)->str:
 h=hashlib.sha256()
 with path.open('rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
 return h.hexdigest()
def load_json(path:Path,limit:int=MAX_JSON)->dict[str,Any]:
 raw=path.read_bytes()
 if not raw or len(raw)>limit:raise SystemExit(f'invalid JSON size: {path}')
 try:v=json.loads(raw)
 except Exception as exc:raise SystemExit(f'invalid JSON: {path}') from exc
 if not isinstance(v,dict):raise SystemExit(f'JSON must be an object: {path}')
 return v
def parse_time(value:str,label:str)->datetime:
 try:return datetime.fromisoformat(value.replace('Z','+00:00')).astimezone(timezone.utc)
 except Exception as exc:raise SystemExit(f'invalid {label} time') from exc
def fresh(document:dict[str,Any],label:str)->None:
 now=datetime.now(timezone.utc)
 issued_value=document.get('issued_at',document.get('created_at'))
 issued=parse_time(str(issued_value),label+' issued_at/created_at')
 expires=parse_time(str(document.get('expires_at')),label+' expires_at')
 from datetime import timedelta
 if issued>now or expires<=now or expires-issued>timedelta(days=31):raise SystemExit(f'{label} is stale, future-dated, or excessively long-lived')
def schemas():
 reg=Registry();out={}
 for p in sorted(SCHEMAS.glob('*.json')):
  v=load_json(p);jsonschema.Draft202012Validator.check_schema(v);r=Resource.from_contents(v);out[p.name]=v;reg=reg.with_resource(p.name,r)
  if isinstance(v.get('$id'),str):reg=reg.with_resource(v['$id'],r)
 return out,reg
def validate(s,reg,name,value):
 try:jsonschema.Draft202012Validator(s[name],registry=reg,format_checker=jsonschema.FormatChecker()).validate(value)
 except Exception as exc:raise SystemExit(f'{name} validation failed: {exc}') from exc
def safe_file(path:Path,*,secret=False,executable=False,max_bytes=MAX_ARTIFACT):
 path=path.absolute()
 for x in [path,*path.parents]:
  st=os.lstat(x)
  if stat.S_ISLNK(st.st_mode) or st.st_uid!=0 or st.st_mode&0o022:raise SystemExit(f'untrusted path: {x}')
  if x==x.parent:break
 before=os.lstat(path)
 if not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or before.st_size<1 or before.st_size>max_bytes:raise SystemExit(f'unsafe artifact: {path}')
 mode=before.st_mode&0o777
 if secret and mode not in (0o400,0o600):raise SystemExit(f'secret must be 0400/0600: {path}')
 if secret and {'system.posix_acl_access','system.posix_acl_default'}&set(os.listxattr(path,follow_symlinks=False)):raise SystemExit(f'secret ACL forbidden: {path}')
 if executable and not before.st_mode&0o111:raise SystemExit(f'executable bit missing: {path}')
 digest=sha(path);after=os.lstat(path)
 if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns):raise SystemExit(f'artifact changed during read: {path}')
 return digest,before
def load_pub(raw:str|bytes)->Ed25519PublicKey:
 try:k=serialization.load_pem_public_key(raw.encode() if isinstance(raw,str) else raw)
 except Exception as exc:raise SystemExit('invalid public key') from exc
 if not isinstance(k,Ed25519PublicKey):raise SystemExit('public key is not Ed25519')
 return k
def load_priv(path:Path)->Ed25519PrivateKey:
 try:k=serialization.load_pem_private_key(path.read_bytes(),password=None)
 except Exception as exc:raise SystemExit(f'invalid private key: {path}') from exc
 if not isinstance(k,Ed25519PrivateKey):raise SystemExit('private key is not Ed25519')
 return k
def raw_pub(k:Ed25519PublicKey)->bytes:return k.public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
def keyring(value:dict[str,Any],s,reg,label:str):
 validate(s,reg,'public-keyring.schema.json',value);keys={};signers=set();fingerprints=set()
 for row in value['keys']:
  key=load_pub(row['public_key_pem']);fp=hashlib.sha256(raw_pub(key)).hexdigest()
  if row['key_id'] in keys or row['signer_id'] in signers or fp in fingerprints:raise SystemExit(f'{label} aliases signer/key material')
  if row.get('revoked_at') is not None:raise SystemExit(f'{label} contains active-use revoked key')
  keys[row['key_id']]={'key':key,'signer_id':row['signer_id'],'roles':set(row['roles']),'fingerprint':fp};signers.add(row['signer_id']);fingerprints.add(fp)
 return keys
def verify_document_signature(doc:dict[str,Any],keys:dict[str,dict[str,Any]],role:str,label:str):
 unsigned=dict(doc);sig=unsigned.pop('signature',None);kid=unsigned.get('signer_key_id');declared=unsigned.get('signer_role')
 if declared!=role or kid not in keys or role not in keys[kid]['roles']:raise SystemExit(f'{label} signer role/key mismatch')
 try:keys[kid]['key'].verify(base64.b64decode(str(sig),validate=True),canonical(unsigned))
 except (InvalidSignature,ValueError,TypeError) as exc:raise SystemExit(f'{label} signature invalid') from exc
 return keys[kid]['signer_id']
def verify_multisig(doc:dict[str,Any],keys,required_roles:set[str],label:str):
 signatures=doc.get('signatures');unsigned=dict(doc);unsigned.pop('signatures',None)
 if not isinstance(signatures,list):raise SystemExit(f'{label} signatures missing')
 assigned={};used=set()
 for sig in signatures:
  if not isinstance(sig,dict):continue
  kid=sig.get('key_id')
  if kid not in keys:continue
  try:keys[kid]['key'].verify(base64.b64decode(str(sig.get('ed25519')),validate=True),canonical(unsigned))
  except Exception:continue
  for role in required_roles&keys[kid]['roles']:
   if role not in assigned and keys[kid]['signer_id'] not in used:assigned[role]=kid;used.add(keys[kid]['signer_id'])
 if set(assigned)!=required_roles:raise SystemExit(f'{label} missing distinct roles: {sorted(required_roles-set(assigned))}')
def inspect(name,entry):
 if not isinstance(entry,dict) or set(entry)!={'path','sha256','role','type'}:raise SystemExit(f'{name} descriptor invalid')
 role,typ=ARTIFACT_SPECS[name]
 if entry['role']!=role or entry['type']!=typ or not isinstance(entry['path'],str) or not entry['path'].startswith('/') or not HEX64.fullmatch(str(entry['sha256'])):raise SystemExit(f'{name} identity invalid')
 p=Path(entry['path']);digest,st=safe_file(p,secret=typ=='secret_key',executable=typ=='executable')
 if digest!=entry['sha256']:raise SystemExit(f'{name} hash mismatch')
 return {'path':str(p),'sha256':digest,'size':st.st_size,'dev':st.st_dev,'ino':st.st_ino,'role':role,'type':typ}

def verify_candidate_archive(path:Path,expected_archive:str,expected_manifest:str)->dict[str,Any]:
 if sha(path)!=expected_archive:raise SystemExit('candidate archive hash mismatch')
 with zipfile.ZipFile(path) as z:
  names=z.namelist()
  if not names or len(names)!=len(set(names)):raise SystemExit('candidate archive duplicate/empty inventory')
  roots={n.split('/',1)[0] for n in names if n}
  if len(roots)!=1:raise SystemExit('candidate archive must have one top-level root')
  root=next(iter(roots));manifest_name=root+'/SHA256SUMS.json'
  if manifest_name not in names:raise SystemExit('candidate archive lacks internal manifest')
  total=0;files={}
  for info in z.infolist():
   n=info.filename;parts=Path(n).parts;mode=(info.external_attr>>16)&0o170000
   if n.startswith('/') or '..' in parts or '\\' in n or (mode and mode not in (stat.S_IFREG,stat.S_IFDIR)):raise SystemExit(f'unsafe candidate archive member: {n}')
   if not info.is_dir():files[n]=hashlib.sha256(z.read(n)).hexdigest();total+=info.file_size
  raw=z.read(manifest_name)
  if hashlib.sha256(raw).hexdigest()!=expected_manifest:raise SystemExit('candidate internal manifest hash mismatch')
  try:manifest=json.loads(raw)
  except Exception as exc:raise SystemExit('candidate internal manifest JSON invalid') from exc
  entries=manifest.get('entries') if isinstance(manifest,dict) else None
  expected_files={root+'/'+rel:d for rel,d in (entries or {}).items()};expected_files[manifest_name]=hashlib.sha256(raw).hexdigest()
  if set(files)!=set(expected_files) or any(files[n]!=d for n,d in expected_files.items()):raise SystemExit('candidate internal manifest does not authenticate exact archive')
  return {'root':root,'file_count':len(files),'total_bytes':total,'manifest':manifest}

def probe_executable(name,path:Path):
 cmd=[str(path),'--version']
 if name=='anchor_helper':cmd=[str(path),'identity']
 try:r=subprocess.run(cmd,capture_output=True,timeout=10,env={'PATH':'/usr/bin:/bin','HOME':'/nonexistent','LANG':'C.UTF-8','LC_ALL':'C.UTF-8'},text=False)
 except Exception as exc:raise SystemExit(f'{name} identity probe failed') from exc
 if r.returncode!=0 or not (r.stdout+r.stderr).strip() or len(r.stdout)+len(r.stderr)>65536:raise SystemExit(f'{name} identity probe is not reproducible')
def raw_evidence(report):
 seen=set()
 for row in report['raw_evidence']:
  p=Path(row['path']);digest,st=safe_file(p,max_bytes=2*1024*1024*1024)
  if digest!=row['sha256'] or st.st_size!=row['size']:raise SystemExit(f"raw evidence mismatch: {row['evidence_id']}")
  ident=(st.st_dev,st.st_ino)
  if ident in seen:raise SystemExit('raw evidence path alias')
  seen.add(ident)
def require_measurements(kind,m):
 def truths(*names):
  for n in names:
   if m.get(n) is not True:raise SystemExit(f'{kind} missing true measurement {n}')
 if kind=='CODEX_ISOLATION_QUALIFICATION':
  truths('cgroup_v2','pid_namespace','mount_namespace');
  if len(m.get('process_tree_tests',{}))<5 or not all(m['process_tree_tests'].values()):raise SystemExit('process-tree corpus incomplete')
  if len(m.get('secret_denial_tests',{}))<3 or not all(m['secret_denial_tests'].values()):raise SystemExit('secret-denial corpus incomplete')
  for n in ('capabilities_sha256','lsm_profile_sha256','mount_profile_sha256','quota_profile_sha256'):
   if not HEX64.fullmatch(str(m.get(n))):raise SystemExit(f'isolation measurement missing {n}')
 elif kind=='REMOTE_ANCHOR_QUALIFICATION':truths('rollback_test_passed','restore_test_passed')
 elif kind=='KEY_CUSTODY_QUALIFICATION':truths('hardware_or_brokered','agent_read_denied','rotation_test_passed','revocation_test_passed','compromise_recovery_test_passed')
 elif kind=='INSTALLER_FAULT_MATRIX_QUALIFICATION':
  truths('all_fault_cases_passed','no_partial_state','recovery_deterministic')
  if int(m.get('fault_points_tested',0))<10:raise SystemExit('installer fault evidence too shallow')
 elif kind=='SUPPLY_CHAIN_REBUILD_QUALIFICATION':
  truths('reproducible')
  if int(m.get('resolution_pass_count',0))<2:raise SystemExit('supply-chain rebuild not independently repeated')
  for n in ('wheel_set_sha256','sbom_sha256','build_provenance_sha256','registry_proof_sha256'):
   if not HEX64.fullmatch(str(m.get(n))):raise SystemExit(f'supply-chain measurement missing {n}')
 elif kind=='DEDICATED_HOST_POLICY_QUALIFICATION':
  truths('dedicated_host','cgroup_v2','pid_namespace','mount_namespace')
  for n in ('measured_boot_policy_sha256','os_policy_sha256','cgroup_profile_sha256','mount_profile_sha256','quota_profile_sha256','lsm_profile_sha256'):
   if not HEX64.fullmatch(str(m.get(n))):raise SystemExit(f'host policy missing {n}')
  if not isinstance(m.get('quota_limits'),dict):raise SystemExit('host quota measurements missing')
def verify_sbom(v):
 if v.get('bomFormat')!='CycloneDX' or not isinstance(v.get('components'),list) or not v['components']:raise SystemExit('SBOM is empty or not CycloneDX')
 for c in v['components']:
  if not isinstance(c,dict) or not c.get('name') or not c.get('version') or not any(isinstance(h,dict) and h.get('alg')=='SHA-256' and HEX64.fullmatch(str(h.get('content'))) for h in c.get('hashes',[])):raise SystemExit('SBOM component lacks exact identity')
def verify_lock(path):
 rows=[]
 for line in path.read_text().splitlines():
  line=line.strip()
  if not line or line.startswith('#'):continue
  if not re.fullmatch(r'[A-Za-z0-9_.-]+==[^\s]+ --hash=sha256:[0-9a-f]{64}',line):raise SystemExit('dependency lock is not exact/hash-locked')
  rows.append(line)
 if not rows:raise SystemExit('dependency lock is empty')
def write_once(path:Path,data:bytes):
 path=path.absolute();path.parent.mkdir(parents=True,exist_ok=True,mode=0o700);fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o400)
 try:
  view=memoryview(data)
  while view:view=view[os.write(fd,view):]
  os.fsync(fd)
 finally:os.close(fd)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--inputs',required=True);ap.add_argument('--receipt-output',required=True);a=ap.parse_args()
 if os.geteuid()!=0:raise SystemExit('semantic clean-room verification must run as root')
 s,reg=schemas();value=load_json(Path(a.inputs))
 expected_top={'format_version','safe_for_unattended_execution_now','candidate_archive_sha256','bundle_manifest_sha256','host_id','agent_uid','agent_gid','validation_image_digest','receipt_signing_key_id','artifacts'}
 if set(value)!=expected_top or value.get('format_version')!='3.0' or value.get('safe_for_unattended_execution_now') is not False:raise SystemExit('v8 qualification input manifest identity invalid')
 if not HEX64.fullmatch(str(value['candidate_archive_sha256'])) or not HEX64.fullmatch(str(value['bundle_manifest_sha256'])) or not re.fullmatch(r'sha256:[0-9a-f]{64}',str(value['validation_image_digest'])):raise SystemExit('immutable qualification bindings invalid')
 if not isinstance(value['agent_uid'],int) or value['agent_uid']<=0 or not isinstance(value['agent_gid'],int) or value['agent_gid']<=0:raise SystemExit('non-root agent identity required')
 artifacts=value.get('artifacts');expected=set(ARTIFACT_SPECS)
 if not isinstance(artifacts,dict) or set(artifacts)!=expected:raise SystemExit(f'v8 artifact set incomplete or unknown; missing={sorted(expected-set(artifacts or {}))} extra={sorted(set(artifacts or {})-expected)}')
 results={};ids={}
 for name in sorted(expected):
  r=inspect(name,artifacts[name]);ident=(r['dev'],r['ino'])
  if ident in ids:raise SystemExit(f'artifact alias: {ids[ident]} and {name}')
  ids[ident]=name;results[name]=r
 if results['bundle_zip']['sha256']!=value['candidate_archive_sha256']:raise SystemExit('candidate archive top-level hash mismatch')
 archive_identity=verify_candidate_archive(Path(results['bundle_zip']['path']),value['candidate_archive_sha256'],value['bundle_manifest_sha256'])
 # Key pairs and populated, unique keyrings.
 for label,priv,pub in [('runtime','runtime_private_key','runtime_public_key'),('evidence','evidence_private_key','evidence_public_key'),('installation','installation_signing_private_key','installation_signing_public_key'),('qualification receipt','qualification_receipt_signing_private_key','qualification_receipt_signing_public_key')]:
  if raw_pub(load_priv(Path(results[priv]['path'])).public_key())!=raw_pub(load_pub(Path(results[pub]['path']).read_bytes())):raise SystemExit(f'{label} private/public mismatch')
 approval=keyring(load_json(Path(results['approval_keyring']['path'])),s,reg,'approval keyring')
 keyring(load_json(Path(results['evidence_keyring']['path'])),s,reg,'evidence keyring')
 qkeys=keyring(load_json(Path(results['qualification_authorization_keyring']['path'])),s,reg,'qualification keyring')
 # Signed revocation state must be fresh and independently authorized.
 rev=load_json(Path(results['qualification_revocation_list']['path']));validate(s,reg,'qualification-revocation-list.schema.json',rev);fresh(rev,'qualification revocation list');verify_multisig(rev,qkeys,{'revocation-authority','security-approver'},'qualification revocation list')
 revoked=set(rev['revoked_key_ids'])
 # Release attestation must sign the exact archive and manifest.
 batt=load_json(Path(results['bundle_attestation']['path']));unsigned=dict(batt);sig=unsigned.pop('signature',None)
 if batt.get('format_version')!='2.0' or batt.get('bundle_name')!=archive_identity['root'] or batt.get('bundle_archive_sha256')!=value['candidate_archive_sha256'] or batt.get('bundle_manifest_sha256')!=value['bundle_manifest_sha256'] or batt.get('bundle_file_count')!=archive_identity['file_count'] or batt.get('bundle_total_bytes')!=archive_identity['total_bytes']:raise SystemExit('release attestation does not bind exact v8 archive/manifest')
 try:load_pub(Path(results['bundle_signing_public_key']['path']).read_bytes()).verify(base64.b64decode(str(sig),validate=True),canonical(unsigned))
 except Exception as exc:raise SystemExit('release attestation signature invalid') from exc
 # Profiles and supply-chain semantics.
 execution=load_json(Path(results['agent_execution_profile']['path']));validate(s,reg,'agent-execution-profile.schema.json',execution);fresh(execution,'agent execution profile')
 quota=load_json(Path(results['handoff_quota_profile']['path']));validate(s,reg,'handoff-quota-profile.schema.json',quota)
 if execution['host_id']!=value['host_id'] or execution['agent_uid']!=value['agent_uid'] or execution['agent_gid']!=value['agent_gid'] or execution['quota_profile_sha256']!=results['handoff_quota_profile']['sha256']:raise SystemExit('agent execution profile cross-binding mismatch')
 gate_rel=archive_identity['root']+'/trusted-controller/process_gate.py'
 with zipfile.ZipFile(Path(results['bundle_zip']['path'])) as archive:gate_hash=hashlib.sha256(archive.read(gate_rel)).hexdigest() if gate_rel in archive.namelist() else None
 if execution['process_gate_sha256']!=gate_hash:raise SystemExit('agent execution profile does not bind candidate process gate')
 required_opts={'nodev','nosuid','noexec'}
 if not required_opts.issubset(set(quota['mount_options'])):raise SystemExit('handoff quota mount lacks nodev/nosuid/noexec')
 verify_lock(Path(results['dependency_lock']['path']));sbom_value=load_json(Path(results['sbom']['path']));verify_sbom(sbom_value)
 provenance=load_json(Path(results['build_provenance']['path']));validate(s,reg,'build-provenance.schema.json',provenance)
 if provenance.get('reproducible') is not True or len(provenance.get('resolution_passes',[]))<2 or provenance.get('requirements_input_sha256')!=results['requirements_input']['sha256'] or provenance.get('dependency_lock_sha256')!=results['dependency_lock']['sha256']:raise SystemExit('build provenance is not exact/reproducible')
 if len({x.get('wheel_set_sha256') for x in provenance['resolution_passes']})!=1:raise SystemExit('build resolution passes disagree')
 inv=load_json(Path(results['dependency_mirror_inventory']['path']));validate(s,reg,'dependency-mirror-inventory.schema.json',inv)
 if not inv.get('files'):raise SystemExit('mirror inventory empty')
 inventory_hash=hashlib.sha256(canonical(inv['files'])).hexdigest()
 if inv['inventory_sha256']!=inventory_hash or inv['file_count']!=len(inv['files']) or inv['total_bytes']!=sum(int(x['size']) for x in inv['files']):raise SystemExit('mirror inventory self-identity mismatch')
 matt=load_json(Path(results['dependency_mirror_attestation']['path']));validate(s,reg,'dependency-mirror-attestation.schema.json',matt)
 if matt['mirror_name']!=inv['mirror_name'] or matt['inventory_sha256']!=inventory_hash or matt['file_count']!=inv['file_count'] or matt['total_bytes']!=inv['total_bytes']:raise SystemExit('mirror attestation cross-binding mismatch')
 munsigned=dict(matt);msig=munsigned.pop('signature',None)
 try:load_pub(Path(results['dependency_mirror_public_key']['path']).read_bytes()).verify(base64.b64decode(str(msig),validate=True),canonical(munsigned))
 except Exception as exc:raise SystemExit('mirror attestation signature invalid') from exc
 mirror_expected={'name':inv['mirror_name'],'inventory_sha256':inventory_hash,'attestation_sha256':results['dependency_mirror_attestation']['sha256'],'public_key_sha256':results['dependency_mirror_public_key']['sha256'],'signer_key_id':matt['signer_key_id'],'file_count':inv['file_count']}
 if provenance.get('mirror')!=mirror_expected:raise SystemExit('build provenance mirror binding mismatch')
 sbom_rows=[]
 for c in sbom_value['components']:
  wheel=next((x.get('value') for x in c.get('properties',[]) if isinstance(x,dict) and x.get('name')=='azpr:wheel'),None);digest=next((x.get('content') for x in c.get('hashes',[]) if isinstance(x,dict) and x.get('alg')=='SHA-256'),None)
  if wheel and digest:sbom_rows.append((wheel,digest,str(c['name']).lower().replace('_','-'),str(c['version'])))
 provenance_rows=[(x['filename'],x['sha256'],str(x['name']).lower().replace('_','-'),str(x['version'])) for x in provenance['wheels']]
 if sorted(sbom_rows)!=sorted(provenance_rows):raise SystemExit('SBOM/provenance wheel identities disagree')
 image_att=load_json(Path(results['validation_image_attestation']['path']));validate(s,reg,'validation-image-attestation.schema.json',image_att)
 for k,n in [('sbom_sha256','sbom'),('build_provenance_sha256','build_provenance'),('dockerfile_sha256','validation_dockerfile')]:
  if image_att.get(k)!=results[n]['sha256']:raise SystemExit(f'image attestation does not bind {n}')
 if image_att.get('image_digest')!=value['validation_image_digest']:raise SystemExit('image attestation digest mismatch')
 verify_multisig(image_att,approval,{'build-operator','security-approver'},'validation image attestation')
 registry=load_json(Path(results['validation_registry_proof']['path']))
 if set(registry)!={'format_version','image_digest','registry','observed_digest','proof_sha256','issued_at','expires_at','signer_key_id','signer_role','signature'} or registry['format_version']!='1.0' or registry['image_digest']!=value['validation_image_digest'] or registry['observed_digest']!=value['validation_image_digest'] or not HEX64.fullmatch(str(registry['proof_sha256'])):raise SystemExit('registry proof invalid')
 fresh(registry,'registry proof');verify_document_signature(registry,qkeys,'build-qualifier','registry proof')
 # Executable identity probes are reproduced rather than accepted by hash alone.
 for name in ('git_binary','python_binary','codex_binary','container_engine','anchor_helper'):probe_executable(name,Path(results[name]['path']))
 # Signed qualification reports, immutable raw evidence, exact common bindings, unique human/service signers.
 report_hashes={};report_signers=set();required_common={'bundle_zip','codex_binary','git_binary','python_binary','container_engine','agent_execution_profile','handoff_quota_profile'}
 for name,(kind,role) in REPORT_ROLES.items():
  report=load_json(Path(results[name]['path']));validate(s,reg,'qualification-evidence-report.schema.json',report);fresh(report,name)
  if report['report_kind']!=kind or report['host_id']!=value['host_id'] or report['candidate_archive_sha256']!=value['candidate_archive_sha256'] or report['bundle_manifest_sha256']!=value['bundle_manifest_sha256'] or report['validation_image_digest']!=value['validation_image_digest']:raise SystemExit(f'{name} common binding mismatch')
  if not required_common.issubset(report['artifact_bindings']):raise SystemExit(f'{name} lacks required cross-bindings')
  for n,d in report['artifact_bindings'].items():
   if n not in results or results[n]['sha256']!=d:raise SystemExit(f'{name} substituted artifact binding: {n}')
  signer=verify_document_signature(report,qkeys,role,name)
  if report['signer_key_id'] in revoked:raise SystemExit(f'{name} signed by revoked key')
  if signer in report_signers:raise SystemExit('qualification reports must use distinct signer identities')
  report_signers.add(signer);raw_evidence(report);require_measurements(kind,report['measurements']);report_hashes[name]=results[name]['sha256']
 # Kind-specific cross-checks.
 iso=load_json(Path(results['codex_isolation_qualification_report']['path']))['measurements'];host=load_json(Path(results['dedicated_host_policy']['path']))['measurements'];supply=load_json(Path(results['supply_chain_rebuild_report']['path']))['measurements']
 for k in ('quota_profile_sha256','mount_profile_sha256','lsm_profile_sha256'):
  if iso.get(k)!=host.get(k):raise SystemExit(f'host/isolation profile disagreement: {k}')
 if iso.get('quota_profile_sha256')!=results['handoff_quota_profile']['sha256']:raise SystemExit('qualification reports do not bind exact quota profile')
 if supply.get('sbom_sha256')!=results['sbom']['sha256'] or supply.get('build_provenance_sha256')!=results['build_provenance']['sha256'] or supply.get('registry_proof_sha256')!=results['validation_registry_proof']['sha256']:raise SystemExit('supply-chain report cross-binding mismatch')
 # Sign a setup-blocking semantic receipt with a dedicated key.
 issued=datetime.now(timezone.utc);receipt_id='qual-receipt-'+os.urandom(16).hex();bindings={n:r['sha256'] for n,r in sorted(results.items())}
 unsigned={'format_version':'2.0','receipt_kind':'AZPR_V8_SEMANTIC_CLEANROOM_QUALIFICATION_RECEIPT','receipt_id':receipt_id,'status':'SEMANTIC_QUALIFICATION_EVIDENCE_VERIFIED_INSTALLATION_STILL_BLOCKED','safe_for_unattended_execution_now':False,'trusted_pre_autonomous_installation_ready':False,'issued_at':issued.isoformat(),'expires_at':(issued+__import__('datetime').timedelta(days=7)).isoformat(),'host_id':value['host_id'],'candidate_archive_sha256':value['candidate_archive_sha256'],'bundle_manifest_sha256':value['bundle_manifest_sha256'],'agent_uid':value['agent_uid'],'agent_gid':value['agent_gid'],'validation_image_digest':value['validation_image_digest'],'artifact_bindings':bindings,'qualification_report_hashes':report_hashes,'agent_execution_profile_sha256':results['agent_execution_profile']['sha256'],'handoff_quota_profile_sha256':results['handoff_quota_profile']['sha256'],'revocation_list_sha256':results['qualification_revocation_list']['sha256'],'remaining_closed_gates':['SEPARATE_INSTALLATION_AUTHORIZATION_REQUIRED','ROOT_INSTALLATION_NOT_PERFORMED','CANONICAL_POLICY_NOT_APPROVED','PROMPT_004_NOT_EXECUTED','ROADMAP_NOT_GENERATED_OR_PROMOTED','AUTONOMOUS_AND_EXTERNAL_EXECUTION_NOT_AUTHORIZED','INDEPENDENT_REASSESSMENT_REQUIRED'],'signer_key_id':value['receipt_signing_key_id']}
 private=load_priv(Path(results['qualification_receipt_signing_private_key']['path']));receipt=dict(unsigned);receipt['signature']=base64.b64encode(private.sign(canonical(unsigned))).decode()
 write_once(Path(a.receipt_output),(json.dumps(receipt,indent=2,sort_keys=True)+'\n').encode())
 print(json.dumps({'status':receipt['status'],'safe_for_unattended_execution_now':False,'trusted_pre_autonomous_installation_ready':False,'required_artifact_count':len(results),'receipt_id':receipt_id,'receipt_path':str(Path(a.receipt_output).absolute()),'receipt_sha256':sha(Path(a.receipt_output)),'qualification_report_count':len(report_hashes),'remaining_closed_gates':receipt['remaining_closed_gates']},indent=2,sort_keys=True))
if __name__=='__main__':main()
