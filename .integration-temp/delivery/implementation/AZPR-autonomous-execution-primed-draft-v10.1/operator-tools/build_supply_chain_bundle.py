#!/usr/bin/env python3
"""Build a reproducible, hash-locked AZPR Python dependency bundle.

The initial dependency source is an operator-approved offline mirror with a
signed deterministic inventory. Resolution is run twice into isolated
workspaces; any wheel-set or byte mismatch is fatal.
"""
from __future__ import annotations
import argparse,base64,hashlib,json,os,re,shutil,stat,subprocess,sys,tempfile,zipfile
from datetime import datetime,timezone
from pathlib import Path
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
PIN=re.compile(r'^([A-Za-z0-9_.-]+)==([^\s;]+)$')
MAX_MIRROR_FILES=10000;MAX_MIRROR_BYTES=5_000_000_000

def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def read_once(path:Path,limit:int=4*1024*1024)->bytes:
 path=path.expanduser().absolute();fd=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
 try:
  before=os.fstat(fd)
  if not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or before.st_size>limit:raise SystemExit(f'unsafe input: {path}')
  data=bytearray()
  while True:
   chunk=os.read(fd,65536)
   if not chunk:break
   data.extend(chunk)
   if len(data)>limit:raise SystemExit(f'input too large: {path}')
  after=os.fstat(fd)
  if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns):raise SystemExit(f'input changed during read: {path}')
  return bytes(data)
 finally:os.close(fd)
def sha(path:Path)->str:
 h=hashlib.sha256()
 with path.open('rb') as f:
  for c in iter(lambda:f.read(1024*1024),b''):h.update(c)
 return h.hexdigest()
def safe_tree(root:Path):
 root=root.absolute();owner=os.geteuid();files=[];total=0
 for p in [root,*root.parents]:
  st=os.lstat(p)
  if stat.S_ISLNK(st.st_mode) or st.st_mode&0o022:raise SystemExit(f'unsafe writable/symlink mirror ancestor: {p}')
  if p==p.parent:break
 if not root.is_dir():raise SystemExit('offline mirror is not a directory')
 for p in sorted(root.rglob('*')):
  st=os.lstat(p)
  if stat.S_ISLNK(st.st_mode) or st.st_mode&0o022:raise SystemExit(f'unsafe mirror entry: {p}')
  if p.is_dir():continue
  if not stat.S_ISREG(st.st_mode) or st.st_nlink!=1:raise SystemExit(f'non-regular mirror entry: {p}')
  rel=str(p.relative_to(root)).replace(os.sep,'/');files.append({'path':rel,'sha256':sha(p),'size':st.st_size});total+=st.st_size
  if len(files)>MAX_MIRROR_FILES or total>MAX_MIRROR_BYTES:raise SystemExit('offline mirror exceeds limits')
 if not files:raise SystemExit('offline mirror is empty')
 return files,total
def verify_mirror(root:Path,att_path:Path,key_path:Path,key_id:str):
 files,total=safe_tree(root);inventory=hashlib.sha256(canonical(files)).hexdigest()
 att=json.loads(read_once(att_path).decode());signature=att.get('signature');unsigned=dict(att);unsigned.pop('signature',None)
 expected={'format_version':'1.0','mirror_name':root.name,'inventory_sha256':inventory,'file_count':len(files),'total_bytes':total,'signer_key_id':key_id}
 for k,v in expected.items():
  if att.get(k)!=v:raise SystemExit(f'dependency mirror attestation mismatch: {k}')
 try:
  key=serialization.load_pem_public_key(read_once(key_path,64*1024))
  if not isinstance(key,Ed25519PublicKey):raise SystemExit('mirror public key is not Ed25519')
  key.verify(base64.b64decode(str(signature),validate=True),canonical(unsigned))
 except (InvalidSignature,ValueError,TypeError) as exc:raise SystemExit('dependency mirror signature verification failed') from exc
 return files,inventory
def metadata(wheel:Path):
 with zipfile.ZipFile(wheel) as z:
  names=[n for n in z.namelist() if n.endswith('.dist-info/METADATA')]
  if len(names)!=1:raise SystemExit(f'ambiguous wheel metadata: {wheel.name}')
  text=z.read(names[0]).decode('utf-8','replace')
 name=version=None
 for line in text.splitlines():
  if line.startswith('Name: '):name=line[6:].strip()
  elif line.startswith('Version: '):version=line[9:].strip()
 if not name or not version:raise SystemExit(f'incomplete wheel metadata: {wheel.name}')
 return name,version
def inventory_wheels(root:Path):
 rows=[]
 for wheel in sorted(root.glob('*.whl')):
  name,version=metadata(wheel);rows.append({'filename':wheel.name,'sha256':sha(wheel),'name':name.lower().replace('_','-'),'version':version,'size':wheel.stat().st_size})
 if not rows:raise SystemExit('resolver produced no wheels')
 return rows
def write_once(path:Path,data:bytes,mode:int=0o600):
 path=path.absolute();path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
 fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),mode)
 try:os.write(fd,data);os.fsync(fd)
 finally:os.close(fd)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--requirements-in',required=True);ap.add_argument('--output-dir',required=True);ap.add_argument('--offline-mirror',required=True);ap.add_argument('--mirror-attestation',required=True);ap.add_argument('--mirror-public-key',required=True);ap.add_argument('--mirror-key-id',required=True);ap.add_argument('--python',default=sys.executable);a=ap.parse_args()
 inp=Path(a.requirements_in).absolute();out=Path(a.output_dir).absolute();mirror=Path(a.offline_mirror).absolute()
 if out.exists():raise SystemExit('output directory must not already exist')
 mirror_files,mirror_inventory=verify_mirror(mirror,Path(a.mirror_attestation).absolute(),Path(a.mirror_public_key).absolute(),a.mirror_key_id)
 raw_requirements=read_once(inp);lines=[]
 for raw in raw_requirements.decode().splitlines():
  value=raw.strip()
  if not value or value.startswith('#'):continue
  if not PIN.fullmatch(value):raise SystemExit(f'direct requirement is not an exact pin: {value}')
  lines.append(value)
 if not lines:raise SystemExit('requirements input is empty')
 python_path=Path(a.python).absolute();python_hash=sha(python_path)
 with tempfile.TemporaryDirectory(prefix='azpr-supply-chain-') as td:
  temp=Path(td);req=temp/'requirements.in';req.write_text('\n'.join(lines)+'\n')
  passes=[]
  for index in (1,2):
   wheelhouse=temp/f'wheelhouse-{index}';wheelhouse.mkdir();home=temp/f'home-{index}';home.mkdir()
   cmd=[str(python_path),'-m','pip','download','--no-index','--find-links',str(mirror),'--only-binary=:all:','--dest',str(wheelhouse),'-r',str(req)]
   subprocess.run(cmd,check=True,env={'PATH':'/usr/bin:/bin','HOME':str(home),'PIP_DISABLE_PIP_VERSION_CHECK':'1','PYTHONNOUSERSITE':'1','PIP_NO_INDEX':'1'})
   rows=inventory_wheels(wheelhouse);passes.append({'index':index,'command':cmd,'wheel_set_sha256':hashlib.sha256(canonical(rows)).hexdigest(),'wheels':rows,'path':wheelhouse})
  if passes[0]['wheels']!=passes[1]['wheels']:raise SystemExit('dependency resolution is not reproducible across two isolated passes')
  wheels=passes[0]['wheels'];components=[]
  for row in wheels:components.append({'type':'library','name':row['name'],'version':row['version'],'hashes':[{'alg':'SHA-256','content':row['sha256']}],'properties':[{'name':'azpr:wheel','value':row['filename']}]})
  lock_text='# Generated from a signed offline mirror; install with --require-hashes and --no-index.\n'+'\n'.join(f"{r['name']}=={r['version']} --hash=sha256:{r['sha256']}" for r in wheels)+'\n'
  now=datetime.now(timezone.utc).isoformat();pip_version=subprocess.run([str(python_path),'-m','pip','--version'],capture_output=True,text=True,check=True,env={'PATH':'/usr/bin:/bin','PYTHONNOUSERSITE':'1'}).stdout.strip()
  sbom={'bomFormat':'CycloneDX','specVersion':'1.5','version':1,'metadata':{'timestamp':now,'component':{'type':'application','name':'azpr-trusted-python-runtime'}},'components':components}
  provenance={'format_version':'2.0','created_at':now,'builder':{'python_path':str(python_path),'python_sha256':python_hash,'python_version':subprocess.run([str(python_path),'--version'],capture_output=True,text=True,check=True).stdout.strip(),'pip_version':pip_version},'requirements_input_sha256':hashlib.sha256(raw_requirements).hexdigest(),'dependency_lock_sha256':hashlib.sha256(lock_text.encode()).hexdigest(),'mirror':{'name':mirror.name,'inventory_sha256':mirror_inventory,'attestation_sha256':sha(Path(a.mirror_attestation).absolute()),'public_key_sha256':sha(Path(a.mirror_public_key).absolute()),'signer_key_id':a.mirror_key_id,'file_count':len(mirror_files)},'resolution_passes':[{'index':p['index'],'command':p['command'],'wheel_set_sha256':p['wheel_set_sha256']} for p in passes],'reproducible':True,'wheels':wheels}
  mirror_inventory_doc={'format_version':'1.0','mirror_name':mirror.name,'inventory_sha256':mirror_inventory,'file_count':len(mirror_files),'total_bytes':sum(int(x['size']) for x in mirror_files),'files':mirror_files}
  staging=temp/'output';staging.mkdir();shutil.copytree(passes[0]['path'],staging/'wheelhouse')
  (staging/'requirements-security.in').write_bytes(raw_requirements)
  (staging/'requirements-security.lock').write_text(lock_text)
  (staging/'dependency-mirror-inventory.json').write_text(json.dumps(mirror_inventory_doc,indent=2,sort_keys=True)+'\n')
  shutil.copy2(Path(a.mirror_attestation).absolute(),staging/'dependency-mirror-attestation.json')
  shutil.copy2(Path(a.mirror_public_key).absolute(),staging/'dependency-mirror-public-key.pem')
  (staging/'sbom.cyclonedx.json').write_text(json.dumps(sbom,indent=2,sort_keys=True)+'\n')
  (staging/'build-provenance.json').write_text(json.dumps(provenance,indent=2,sort_keys=True)+'\n')
  testenv=temp/'venv';subprocess.run([str(python_path),'-m','venv','--copies',str(testenv)],check=True);subprocess.run([str(testenv/'bin/pip'),'install','--no-index','--find-links',str(staging/'wheelhouse'),'--require-hashes','-r',str(staging/'requirements-security.lock')],check=True,env={'PATH':'/usr/bin:/bin','HOME':str(temp/'install-home'),'PIP_NO_INDEX':'1','PIP_DISABLE_PIP_VERSION_CHECK':'1','PYTHONNOUSERSITE':'1'});subprocess.run([str(testenv/'bin/python'),'-c','import cryptography,jsonschema,referencing'],check=True)
  shutil.copytree(staging,out)
 print(json.dumps({'output_dir':str(out),'wheel_count':len(wheels),'mirror_inventory_sha256':mirror_inventory,'reproducible':True,'requirements_input_sha256':sha(out/'requirements-security.in'),'lock_sha256':sha(out/'requirements-security.lock'),'mirror_attestation_sha256':sha(out/'dependency-mirror-attestation.json'),'mirror_public_key_sha256':sha(out/'dependency-mirror-public-key.pem'),'sbom_sha256':sha(out/'sbom.cyclonedx.json'),'provenance_sha256':sha(out/'build-provenance.json')},indent=2))
if __name__=='__main__':main()
