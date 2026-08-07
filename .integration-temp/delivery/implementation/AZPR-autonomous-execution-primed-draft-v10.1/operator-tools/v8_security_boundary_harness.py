#!/usr/bin/env python3
"""Independent-process release-blocking regressions for all v7 findings."""
from __future__ import annotations
import json,os,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def run(argv,**kw):return subprocess.run(argv,capture_output=True,text=True,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},**kw)
def main():
 cases=[]
 source=(ROOT/'trusted-installation/install.py').read_text();pre=source.find('qualification=_qualification_preflight(args)');reserve=source.find('_reserve_authorization(qualification)');recovery=source.find('recovered=recover_activation_state()',pre)
 cases.append({'id':'blackbox.v8.installer_authorization_before_state','pass':0<=pre<reserve<recovery and "'qualification-authorization'" in source,'detail':f'positions={pre},{reserve},{recovery}'})
 with tempfile.TemporaryDirectory() as td:
  base=Path(td);base.chmod(0o755);fake=base/'fake.json';fake.write_text(json.dumps({'format_version':'3.0','safe_for_unattended_execution_now':False,'candidate_archive_sha256':'a'*64,'bundle_manifest_sha256':'b'*64,'host_id':'fake-host','agent_uid':65534,'agent_gid':65534,'validation_image_digest':'sha256:'+'c'*64,'receipt_signing_key_id':'fake-receipt-key','artifacts':{}}))
  receipt=base/'receipt.json';r=run([sys.executable,str(ROOT/'operator-tools/verify_v8_cleanroom_prerequisites.py'),'--inputs',str(fake),'--receipt-output',str(receipt)])
  cases.append({'id':'blackbox.v8.fabricated_qualification_rejected','pass':r.returncode!=0 and not receipt.exists(),'detail':(r.stderr+r.stdout)[-1000:]})
  marker=Path('/tmp')/('azpr-v8-orphan-'+os.urandom(8).hex());r=run([sys.executable,str(ROOT/'operator-tools/exercise_v8_execution_unit.py'),'--case','descendant','--marker',str(marker)])
  cases.append({'id':'blackbox.v8.complete_process_tree_terminated','pass':r.returncode==0 and not marker.exists(),'detail':(r.stderr+r.stdout)[-1000:]});marker.unlink(missing_ok=True)
  r=run([sys.executable,str(ROOT/'operator-tools/exercise_v8_execution_unit.py'),'--case','duplex'])
  cases.append({'id':'blackbox.v8.duplex_io_deadline','pass':r.returncode==0,'detail':(r.stderr+r.stdout)[-1000:]})
  r=run([sys.executable,str(ROOT/'operator-tools/exercise_v8_execution_unit.py'),'--case','overflow'])
  cases.append({'id':'blackbox.v8.output_overflow_teardown','pass':r.returncode==0,'detail':(r.stderr+r.stdout)[-1000:]})
 runtime=(ROOT/'trusted-controller/secure_runtime.py').read_text()
 cases.append({'id':'blackbox.v8.production_quota_enforcement_present','pass':all(x in runtime for x in ('_mount_run_tmpfs','nr_inodes','max_entries','cleanup_timeout_seconds','seal_agent_run_surface')),'detail':'source-level mount and bounded-cleanup controls'})
 failed=[x for x in cases if not x['pass']];print(json.dumps({'status':'PASS' if not failed else 'FAIL','safe_for_unattended_execution_now':False,'trusted_pre_autonomous_installation_ready':False,'cases':cases},indent=2,sort_keys=True));return 1 if failed else 0
if __name__=='__main__':raise SystemExit(main())
