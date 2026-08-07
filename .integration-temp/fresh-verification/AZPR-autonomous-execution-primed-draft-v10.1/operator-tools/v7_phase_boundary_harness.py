#!/usr/bin/env python3
"""Independent-process v7 phase-boundary regression harness.

The harness never imports controller/runtime modules. Every sensitive check is
exercised through a command-line entrypoint in a separate process.
"""
from __future__ import annotations
import json,os,subprocess,sys,tempfile,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def run(argv,*,cwd=None):return subprocess.run(argv,cwd=cwd,capture_output=True,text=True,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
def git(root,*args):return subprocess.run(['git',*args],cwd=root,capture_output=True,text=True,check=True).stdout.strip()
def init_repo(root):
 git(root,'init','-q');git(root,'config','user.email','harness@example.invalid');git(root,'config','user.name','Harness');(root/'x').write_text('x');git(root,'add','x');git(root,'commit','-qm','base')
def docx(path):
 xml='''<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>A</w:t><w:tab/><w:t>B</w:t><w:br/><w:t>C</w:t></w:r></w:p><w:sectPr/></w:body></w:document>'''
 with zipfile.ZipFile(path,'w') as z:z.writestr('[Content_Types].xml','<Types/>');z.writestr('word/document.xml',xml)
def main():
 cases=[]
 with tempfile.TemporaryDirectory() as td:
  base=Path(td);base.chmod(0o711)
  handoff=base/'handoff';handoff.mkdir(mode=0o711);protected=base/'protected';protected.write_text('secret');protected.chmod(0o400)
  result=run([sys.executable,str(ROOT/'operator-tools/exercise_agent_handoff.py'),'--handoff-root',str(handoff),'--agent-uid','65534','--agent-gid','65534','--protected-path',str(protected),'--controller-output',str(base/'controller-result.json')])
  cases.append({'id':'blackbox.nonroot_agent_handoff','pass':result.returncode==0,'detail':result.stderr[-1000:]})
  empty=base/'empty.json';empty.write_text(json.dumps({'format_version':'2.0','safe_for_unattended_execution_now':False,'agent_uid':65534,'agent_gid':65534,'validation_image_digest':'sha256:'+'a'*64,'installation_signing_key_id':'fixture-key-id','artifacts':{}}));empty.chmod(0o444)
  result=run([sys.executable,str(ROOT/'operator-tools/verify_v7_cleanroom_prerequisites.py'),'--inputs',str(empty),'--receipt-output',str(base/'empty.receipt')])
  cases.append({'id':'blackbox.cleanroom_completeness','pass':result.returncode!=0 and 'missing=' in result.stderr,'detail':result.stderr[-1000:]})
  repo=base/'graft';repo.mkdir();init_repo(repo);(repo/'.git/info/grafts').write_text(git(repo,'rev-parse','HEAD')+'\n')
  result=run([sys.executable,str(ROOT/'operator-tools/verify_repository_topology.py'),'--repository',str(repo)])
  cases.append({'id':'blackbox.git_graft_rejection','pass':result.returncode!=0,'detail':result.stderr[-1000:]})
  repo2=base/'submodule';repo2.mkdir();init_repo(repo2);(repo2/'.gitmodules').write_text('[submodule "x"]\npath=x\nurl=x\n')
  result=run([sys.executable,str(ROOT/'operator-tools/verify_repository_topology.py'),'--repository',str(repo2)])
  cases.append({'id':'blackbox.submodule_preflight','pass':result.returncode!=0,'detail':result.stderr[-1000:]})
  source=base/'policy.docx';docx(source);canonical=base/'canonical.txt';manifest=base/'manifest.json';mapping=base/'map.json'
  result=run([sys.executable,str(ROOT/'operator-tools/extract_master_prompt_docx.py'),'--docx',str(source),'--canonical-output',str(canonical),'--source-manifest-output',str(manifest),'--section-map-output',str(mapping)])
  ok=result.returncode==0 and canonical.read_bytes()==b'A\tB\nC\n' and json.loads(manifest.read_text())['feature_inventory']['tabs']==1 and json.loads(manifest.read_text())['feature_inventory']['breaks']==1
  cases.append({'id':'blackbox.docx_structure_preservation','pass':ok,'detail':result.stderr[-1000:]})
 failed=[c for c in cases if not c['pass']]
 print(json.dumps({'status':'PASS' if not failed else 'FAIL','safe_for_unattended_execution_now':False,'cases':cases},indent=2,sort_keys=True))
 return 0 if not failed else 1
if __name__=='__main__':raise SystemExit(main())
