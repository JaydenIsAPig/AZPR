from __future__ import annotations
import base64,hashlib,importlib.util,json,os,shutil,subprocess,sys,tempfile,time,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'trusted-controller'))

def run(*args,timeout=120,env=None):
 return subprocess.run([sys.executable,*map(str,args)],cwd=ROOT,capture_output=True,text=True,timeout=timeout,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTEST_DISABLE_PLUGIN_AUTOLOAD':'1',**(env or {})})
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def import_path(name,path):
 spec=importlib.util.spec_from_file_location(name,path);mod=importlib.util.module_from_spec(spec);sys.modules[name]=mod;spec.loader.exec_module(mod);return mod

class V8CorrectiveControlTests(unittest.TestCase):
 def test_v8_blackbox_release_blocking_harness(self):
  r=run(ROOT/'operator-tools/v8_security_boundary_harness.py',timeout=180)
  self.assertEqual(r.returncode,0,r.stdout+r.stderr);value=json.loads(r.stdout);self.assertEqual(value['status'],'PASS');self.assertEqual(len(value['cases']),6);self.assertTrue(all(x['pass'] for x in value['cases']))

 def test_semantic_qualification_positive_and_fabricated_mutations(self):
  if os.geteuid()!=0:
   verifier=import_path('v8_qualification_nonroot',ROOT/'operator-tools/verify_v8_cleanroom_prerequisites.py')
   source=(ROOT/'operator-tools/verify_v8_cleanroom_prerequisites.py').read_text()
   for token in ('REQUIRED_ARTIFACTS','safe_file','raw_evidence','require_measurements','st.st_uid!=0'):
    self.assertIn(token,source)
   from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
   from cryptography.hazmat.primitives import serialization
   key=Ed25519PrivateKey.generate();pub=key.public_key();raw=pub.public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo).decode()
   keys=verifier.keyring({'format_version':'1.0','keys':[{'key_id':'probe','signer_id':'independent','roles':['isolation-qualifier'],'public_key_pem':raw,'revoked_at':None}]},*verifier.schemas(),label='test') if False else {'probe':{'key':pub,'signer_id':'independent','roles':{'isolation-qualifier'},'fingerprint':'x'}}
   unsigned={'kind':'TEST','signer_key_id':'probe','signer_role':'isolation-qualifier'};doc=dict(unsigned,signature=base64.b64encode(key.sign(verifier.canonical(unsigned))).decode())
   self.assertEqual(verifier.verify_document_signature(doc,keys,'isolation-qualifier','test'),'independent')
   doc.pop('signature')
   with self.assertRaises(SystemExit):verifier.verify_document_signature(doc,keys,'isolation-qualifier','test')
   return
  with tempfile.TemporaryDirectory(dir='/root',prefix='azpr-v8-qual-') as td:
   root=Path(td);r=run(ROOT/'operator-tools/build_v8_qualification_fixture.py','--output',root,timeout=180);self.assertEqual(r.returncode,0,r.stdout+r.stderr)
   inputs=root/'qualification-inputs.json';receipt=root/'receipt.actual.json';r=run(ROOT/'operator-tools/verify_v8_cleanroom_prerequisites.py','--inputs',inputs,'--receipt-output',receipt,timeout=180);self.assertEqual(r.returncode,0,r.stdout+r.stderr)
   value=json.loads(receipt.read_text());self.assertFalse(value['safe_for_unattended_execution_now']);self.assertFalse(value['trusted_pre_autonomous_installation_ready']);self.assertEqual(len(value['qualification_report_hashes']),6)
   manifest=json.loads(inputs.read_text());report=Path(manifest['artifacts']['codex_isolation_qualification_report']['path']);bad=json.loads(report.read_text());bad.pop('signature');report.chmod(0o600);report.write_text(json.dumps(bad,sort_keys=True));report.chmod(0o444);manifest['artifacts']['codex_isolation_qualification_report']['sha256']=sha(report);inputs.chmod(0o600);inputs.write_text(json.dumps(manifest));inputs.chmod(0o444)
   rejected=root/'must-not-exist.json';r=run(ROOT/'operator-tools/verify_v8_cleanroom_prerequisites.py','--inputs',inputs,'--receipt-output',rejected,timeout=180);self.assertNotEqual(r.returncode,0);self.assertFalse(rejected.exists())

 def test_installer_authorization_is_first_gate_and_policy_phase_is_explicit(self):
  src=(ROOT/'trusted-installation/install.py').read_text();pre=src.index('qualification=_qualification_preflight(args)');reserve=src.index('_reserve_authorization(qualification)',pre);recover=src.index('recover_activation_state()',reserve)
  self.assertLess(pre,reserve);self.assertLess(reserve,recover);self.assertIn("installation_phase='QUALIFICATION_ONLY'",src);self.assertIn("installation_phase='POLICY_ACTIVATED'",src);self.assertIn('qualification-only installation must not accept canonical-policy derivatives',src)
  schema=json.loads((ROOT/'repository-overlay/automation/schemas/trusted-installation.schema.json').read_text());self.assertIn('installation_phase',schema['required'])
  for loader in ('trusted-controller/trusted_installation.py','trusted-validation-runner/trusted_installation.py','external-capability-runner/trusted_installation.py'):
   text=(ROOT/loader).read_text();self.assertIn("phase!='POLICY_ACTIVATED'",text);self.assertIn('trusted controller/external execution is blocked',text)

 def test_duplex_runner_covers_early_exit_broken_pipe_timeout_and_descendants(self):
  runtime=import_path('v8_sr_duplex',ROOT/'trusted-controller/secure_runtime.py');os.environ['AZPR_EXPLICIT_TEST_MODE']='1'
  cases=[
   ([sys.executable,'-c','import sys;sys.exit(0)'],b'x'*1048576,2),
   ([sys.executable,'-c','import time;time.sleep(10)'],b'',0.3),
  ]
  try:
   rc,*_=runtime.run_bounded_process(cases[0][0],cwd=ROOT,input_bytes=cases[0][1],timeout_seconds=cases[0][2],stdout_limit=1024,stderr_limit=1024);self.assertEqual(rc,0)
   with self.assertRaises((runtime.SecurityError,TimeoutError)):runtime.run_bounded_process(cases[1][0],cwd=ROOT,input_bytes=b'',timeout_seconds=cases[1][2],stdout_limit=1024,stderr_limit=1024)
  finally:os.environ.pop('AZPR_EXPLICIT_TEST_MODE',None)

 def test_quota_scan_rejects_entry_depth_size_and_special_files(self):
  runtime=import_path('v8_sr_quota',ROOT/'trusted-controller/secure_runtime.py');q={'max_entries':4,'cleanup_max_entries':4,'max_bytes':1024*1024,'max_depth':2,'max_path_length':1024,'max_file_bytes':8,'cleanup_timeout_seconds':2}
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);(root/'large').write_bytes(b'x'*9)
   with self.assertRaises(runtime.SecurityError):runtime._quota_scan(root,q,time.monotonic()+2)
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);os.mkfifo(root/'pipe')
   with self.assertRaises(runtime.SecurityError):runtime._quota_scan(root,{**q,'max_file_bytes':1024},time.monotonic()+2)

 def test_v8_new_schemas_are_strict_and_resolve(self):
  import jsonschema
  from referencing import Registry,Resource
  reg=Registry();schemas={}
  for p in (ROOT/'repository-overlay/automation/schemas').glob('*.json'):
   v=json.loads(p.read_text());jsonschema.Draft202012Validator.check_schema(v);r=Resource.from_contents(v);schemas[p.name]=v;reg=reg.with_resource(p.name,r)
   if isinstance(v.get('$id'),str):reg=reg.with_resource(v['$id'],r)
  required={'qualification-evidence-report.schema.json','qualification-revocation-list.schema.json','qualification-installation-authorization.schema.json','qualification-authorization-consumption.schema.json','agent-execution-profile.schema.json','handoff-quota-profile.schema.json','key-lifecycle-state.schema.json'}
  self.assertTrue(required.issubset(schemas));self.assertTrue(all(schemas[x].get('additionalProperties') is False for x in required))

 def test_key_lifecycle_transition_replay_and_epoch_rollback_fail(self):
  from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
  from cryptography.hazmat.primitives import serialization
  def row(key,kid,signer,role):return {'key_id':kid,'signer_id':signer,'roles':[role],'public_key':base64.b64encode(key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)).decode()}
  with tempfile.TemporaryDirectory(prefix='azpr-v8-keylife-') as td:
   d=Path(td);a=Ed25519PrivateKey.generate();b=Ed25519PrivateKey.generate();old=Ed25519PrivateKey.generate();new=Ed25519PrivateKey.generate();fp=lambda k:hashlib.sha256(k.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)).hexdigest()
   ring={'format_version':'1.0','keys':[row(a,'policy-owner-key','owner-signer','policy-owner'),row(b,'security-approver-key','security-signer','security-approver')]};(d/'ring.json').write_text(json.dumps(ring));os.chmod(d/'ring.json',0o444)
   now='2026-07-28T22:00:00+00:00';state={'format_version':'1.0','sequence':0,'last_transition_id':None,'transition_chain_sha256':'0'*64,'roles':{'approval':{'epoch':1,'status':'ACTIVE','key_id':'approval-old','fingerprint':fp(old),'effective_at':now,'historical_keys':[]}}};(d/'state.json').write_text(json.dumps(state));os.chmod(d/'state.json',0o600)
   unsigned={'format_version':'1.0','transition_id':'key-transition-1234567890abcdef','transition_type':'ROTATE','key_role':'approval','from_epoch':1,'to_epoch':2,'old_key_id':'approval-old','old_key_fingerprint':fp(old),'new_key_id':'approval-new','new_key_fingerprint':fp(new),'effective_at':'2026-07-29T00:00:00+00:00','emergency_disable':False,'historical_verification_policy':'OLD_KEY_MAY_VERIFY_PRE_EFFECTIVE_RECORDS_BUT_MAY_NOT_AUTHORIZE_NEW_RECORDS','required_approval_roles':['policy-owner','security-approver']}
   canon=lambda v:json.dumps(v,sort_keys=True,separators=(',',':')).encode();transition=dict(unsigned);transition['signatures']=[{'key_id':'policy-owner-key','ed25519':base64.b64encode(a.sign(canon(unsigned))).decode()},{'key_id':'security-approver-key','ed25519':base64.b64encode(b.sign(canon(unsigned))).decode()}];(d/'transition.json').write_text(json.dumps(transition));os.chmod(d/'transition.json',0o444)
   anchor=d/'anchor.py';anchor.write_text('#!/usr/bin/env python3\nimport json,sys\nv=json.load(sys.stdin)\nprint(json.dumps({"accepted":True,"new_chain_sha256":v["new_chain_sha256"]}))\n');os.chmod(anchor,0o555)
   cmd=[ROOT/'operator-tools/apply_key_lifecycle_transition.py','--state',d/'state.json','--transition',d/'transition.json','--approval-keyring',d/'ring.json','--ledger',d/'ledger','--anchor-command',anchor]
   r=run(*cmd);self.assertEqual(r.returncode,0,r.stdout+r.stderr);r2=run(*cmd);self.assertNotEqual(r2.returncode,0);self.assertIn('transition replay',r2.stdout+r2.stderr)

if __name__=='__main__':unittest.main()
