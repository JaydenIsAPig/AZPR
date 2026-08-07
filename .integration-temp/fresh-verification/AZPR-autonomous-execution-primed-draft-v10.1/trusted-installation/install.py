#!/usr/bin/env python3
"""Root-only authenticated, generation-atomic AZPR trusted installer.

No installed destination is created until the complete release bundle, release
attestation, schemas, and all external trust inputs have been verified. A fully
staged versioned generation is activated only by atomically replacing the
root-owned installation lock.
"""
from __future__ import annotations
import argparse,base64,hashlib,io,json,os,re,shutil,stat,subprocess,sys,tempfile,unicodedata,zipfile
from datetime import datetime,timezone
from pathlib import Path,PurePosixPath
from typing import Any
from xml.etree import ElementTree as ET
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey,Ed25519PublicKey
from cryptography.exceptions import InvalidSignature

# V10 security-critical modules are local to the immutable installer generation.
sys.path.insert(0,str(Path(__file__).resolve().parent))
from v10_binding import (QUALIFICATION_ARTIFACT_SET_VERSION,REQUIRED_QUALIFIED_ARTIFACTS,verify_bootstrap_roots,verify_complete_artifact_bindings,verify_phase_transition)
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'operator-tools'))
from v10_probe_boundary import load_approved_probe_authority,verify_probe_manifest
from v10_1_host_trust import load_host_qualification_context
from v9_transaction import AuthorizationTransactionStore,InstallerGlobalLock

ETC=Path('/etc/azpr');PREFIX=Path('/opt/azpr');GENERATIONS=PREFIX/'generations';VAR=Path('/var/lib/azpr');AGENT_HANDOFF_BASE=Path('/run/azpr-agent-handoff');AGENT_CGROUP_BASE=Path('/sys/fs/cgroup/azpr');ACTIVE_LOCK=ETC/'trusted-installation.lock.json'
GLOBAL_INSTALLER_LOCK=Path('/run/lock/azpr/trusted-installer.global.lock');BOOTSTRAP_ROOT_MANIFEST=ETC/'bootstrap/host-bootstrap-roots-v10.1.json';BOOTSTRAP_AUTHORITY_KEY=ETC/'bootstrap/host-bootstrap-authority-v10.1.pem';HOST_QUALIFICATION_ROOTS_MANIFEST=ETC/'bootstrap/host-qualification-roots-v10.1.json';HOST_QUALIFICATION_ROOTS_AUTHORITY_KEY=ETC/'bootstrap/host-qualification-roots-authority-v10.1.pem';HOST_ROOT_ANCHOR_CLIENT=ETC/'bootstrap/host-root-anchor-client-v10.1';HOST_ROOT_ANCHOR_IDENTITY=ETC/'bootstrap/host-root-anchor-identity-v10.1.json';QUALIFICATION_TRUST_MANIFEST=ETC/'bootstrap/qualification-trust-manifest-v10.1.json';QUALIFICATION_TRUST_AUTHORITY_KEY=ETC/'bootstrap/qualification-trust-authority-v10.1.pem';PROBE_KEYRING=ETC/'bootstrap/probe-keyring-v10.1.json';PROBE_POLICY=ETC/'bootstrap/probe-policy-v10.1.json';PROBE_SERVICE_IDENTITY=ETC/'bootstrap/probe-service-identity-v10.1.json';PROBE_SERVICE_ATTESTATION=ETC/'bootstrap/probe-service-attestation-v10.1.json';PROBE_REVOCATION_STATE=ETC/'bootstrap/probe-revocation-state-v10.1.json';PROBE_ATTESTOR_KEYRING=ETC/'bootstrap/probe-attestor-keyring-v10.1.json';PROBE_ATTESTOR_REVOCATION_STATE=ETC/'bootstrap/probe-attestor-revocation-state-v10.1.json';PROBE_SERVICE_EXECUTABLE=ETC/'bootstrap/probe-service-v10.1';EXTERNAL_SIGNER_CLIENT=ETC/'bootstrap/external-receipt-signer-client-v10.1';EXTERNAL_SIGNER_IDENTITY=ETC/'bootstrap/external-receipt-signer-identity-v10.1.json';QUALIFICATION_RECEIPT_KEY=ETC/'bootstrap/qualification-receipt-signing-v10.1.pem';PHASE_AUTHORIZATION_LEDGER=VAR/'phase-transition-authorizations-v10.1'
MAX_SOURCE_BYTES=32*1024*1024;MAX_BUNDLE_FILES=5000;MAX_BUNDLE_BYTES=100*1024*1024
DOCX_NS={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
def canonical(v:Any)->bytes:return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def sha_bytes(v:bytes)->str:return hashlib.sha256(v).hexdigest()
def sha(path:Path)->str:
 h=hashlib.sha256()
 with path.open('rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
 return h.hexdigest()
def safe_rel(value:str)->str:
 p=PurePosixPath(value)
 if not value or p.is_absolute() or '..' in p.parts or '\\' in value:return (_ for _ in ()).throw(SystemExit(f'unsafe bundle path: {value}'))
 return value
def safe_external(value:str,name:str,*,executable:bool=False)->Path:
 path=Path(value).absolute()
 for candidate in [path,*path.parents]:
  info=os.lstat(candidate)
  if stat.S_ISLNK(info.st_mode):raise SystemExit(f'symlinked external trust root {name}: {candidate}')
  if info.st_mode&0o022:raise SystemExit(f'writable external trust root {name}: {candidate}')
  if info.st_uid!=0:raise SystemExit(f'non-root-owned external trust root {name}: {candidate}')
  if candidate==candidate.parent:break
 info=os.stat(path)
 if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1:raise SystemExit(f'unsafe external trust root {name}: {path}')
 if executable and not info.st_mode&0o111:raise SystemExit(f'non-executable trusted binary {name}: {path}')
 return path
def safe_external_directory(value:str,name:str)->Path:
 path=Path(value).absolute()
 for candidate in [path,*path.parents]:
  info=os.lstat(candidate)
  if stat.S_ISLNK(info.st_mode) or info.st_mode&0o022 or info.st_uid!=0:raise SystemExit(f'untrusted external directory {name}: {candidate}')
  if candidate==candidate.parent:break
 if not path.is_dir():raise SystemExit(f'missing external directory {name}: {path}')
 for item in path.rglob('*'):
  info=os.lstat(item)
  if stat.S_ISLNK(info.st_mode) or info.st_uid!=0 or info.st_mode&0o022:raise SystemExit(f'untrusted entry in {name}: {item}')
  if item.is_file() and (not stat.S_ISREG(info.st_mode) or info.st_nlink!=1):raise SystemExit(f'unsafe entry in {name}: {item}')
 return path
def read_regular(path:Path,limit:int=MAX_SOURCE_BYTES)->bytes:
 fd=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
 try:
  before=os.fstat(fd)
  if not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or before.st_size>limit:raise SystemExit(f'unsafe or oversized input: {path}')
  data=bytearray()
  while True:
   chunk=os.read(fd,65536)
   if not chunk:break
   data.extend(chunk)
   if len(data)>limit:raise SystemExit(f'oversized input: {path}')
  after=os.fstat(fd)
  if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns):raise SystemExit(f'input changed during read: {path}')
  return bytes(data)
 finally:os.close(fd)
def load_json_bytes(raw:bytes,label:str)->dict[str,Any]:
 try:value=json.loads(raw.decode('utf-8'))
 except Exception as exc:raise SystemExit(f'invalid {label} JSON') from exc
 if not isinstance(value,dict):raise SystemExit(f'{label} must be a JSON object')
 return value
def load_json_path(path:Path,label:str)->dict[str,Any]:return load_json_bytes(read_regular(path),label)

class AuthenticatedBundle:
 def __init__(self,root:Path,entries:dict[str,str]):self.root=root;self.entries=entries;self.fd=os.open(root,os.O_RDONLY|getattr(os,'O_DIRECTORY',0)|getattr(os,'O_NOFOLLOW',0))
 def close(self):os.close(self.fd)
 def read(self,relative:str,limit:int=MAX_SOURCE_BYTES)->bytes:
  rel=safe_rel(relative)
  if rel not in self.entries:raise SystemExit(f'bundle file is not authenticated by manifest: {rel}')
  parts=PurePosixPath(rel).parts;dirfd=os.dup(self.fd)
  try:
   for part in parts[:-1]:
    nextfd=os.open(part,os.O_RDONLY|getattr(os,'O_DIRECTORY',0)|getattr(os,'O_NOFOLLOW',0),dir_fd=dirfd);os.close(dirfd);dirfd=nextfd
   fd=os.open(parts[-1],os.O_RDONLY|getattr(os,'O_NOFOLLOW',0),dir_fd=dirfd)
   try:
    st=os.fstat(fd)
    if not stat.S_ISREG(st.st_mode) or st.st_nlink!=1 or st.st_size>limit:raise SystemExit(f'unsafe authenticated bundle file: {rel}')
    data=bytearray()
    while True:
     chunk=os.read(fd,65536)
     if not chunk:break
     data.extend(chunk)
     if len(data)>limit:raise SystemExit(f'authenticated bundle file too large: {rel}')
   finally:os.close(fd)
  finally:os.close(dirfd)
  if sha_bytes(bytes(data))!=self.entries[rel]:raise SystemExit(f'authenticated bundle file changed or hash mismatched: {rel}')
  return bytes(data)

def authenticate_bundle(root_value:str,attestation_path:Path,public_key_path:Path,expected_key_id:str,expected_archive_sha256:str|None=None)->AuthenticatedBundle:
 root=safe_external_directory(root_value,'bundle_root')
 manifest_path=root/'SHA256SUMS.json';manifest_raw=read_regular(manifest_path);manifest=load_json_bytes(manifest_raw,'bundle manifest')
 if manifest.get('format_version')!='1.0' or manifest.get('algorithm')!='SHA-256' or manifest.get('excludes')!=['SHA256SUMS.json']:raise SystemExit('bundle manifest format/exclusion is invalid')
 entries=manifest.get('entries')
 if not isinstance(entries,dict) or not entries or len(entries)>MAX_BUNDLE_FILES:raise SystemExit('bundle manifest entries invalid')
 normalized={}
 for rel,digest in entries.items():
  if not isinstance(rel,str) or not isinstance(digest,str) or not re.fullmatch(r'[0-9a-f]{64}',digest):raise SystemExit('invalid bundle manifest entry')
  normalized[safe_rel(rel)]=digest
 actual=[];total=0
 for path in sorted(root.rglob('*')):
  info=os.lstat(path)
  if stat.S_ISLNK(info.st_mode) or info.st_uid!=0 or info.st_mode&0o022:raise SystemExit(f'untrusted bundle tree entry: {path}')
  if path.is_dir():continue
  if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1:raise SystemExit(f'non-regular bundle entry: {path}')
  rel=str(path.relative_to(root)).replace(os.sep,'/');actual.append(rel);total+=info.st_size
  if total>MAX_BUNDLE_BYTES:raise SystemExit('bundle exceeds total size limit')
 expected=set(normalized)|{'SHA256SUMS.json'}
 if set(actual)!=expected:raise SystemExit(f'bundle inventory mismatch; missing={sorted(expected-set(actual))}; extra={sorted(set(actual)-expected)}')
 for rel,digest in normalized.items():
  if sha(root/rel)!=digest:raise SystemExit(f'bundle manifest hash mismatch: {rel}')
 att=load_json_path(attestation_path,'bundle attestation');unsigned=dict(att);signature=unsigned.pop('signature',None)
 if att.get('format_version') not in ('1.0','2.0') or att.get('signer_key_id')!=expected_key_id or att.get('bundle_name')!=root.name or att.get('bundle_manifest_sha256')!=sha_bytes(manifest_raw) or att.get('bundle_file_count')!=len(actual) or att.get('bundle_total_bytes')!=total:raise SystemExit('bundle attestation identity mismatch')
 if expected_archive_sha256 is not None and (att.get('format_version')!='2.0' or att.get('bundle_archive_sha256')!=expected_archive_sha256):raise SystemExit('bundle attestation does not bind exact candidate archive')
 try:
  key=serialization.load_pem_public_key(read_regular(public_key_path,64*1024))
  if not isinstance(key,Ed25519PublicKey):raise SystemExit('bundle signing key is not Ed25519')
  key.verify(base64.b64decode(str(signature),validate=True),canonical(unsigned))
 except (InvalidSignature,ValueError,TypeError) as exc:raise SystemExit('bundle attestation signature verification failed') from exc
 return AuthenticatedBundle(root,normalized)

def derive_docx(raw:bytes,name:str)->dict[str,Any]:
 try:
  with zipfile.ZipFile(io.BytesIO(raw)) as z:xml=z.read('word/document.xml')
 except Exception as exc:raise SystemExit('governing policy source is not a valid DOCX') from exc
 root=ET.fromstring(xml);units=[]
 for paragraph in root.findall('.//w:body/w:p',DOCX_NS):
  text=''.join((node.text or '') for node in paragraph.findall('.//w:t',DOCX_NS)).strip()
  if not text:continue
  style_node=paragraph.find('./w:pPr/w:pStyle',DOCX_NS);style=style_node.attrib.get('{%s}val'%DOCX_NS['w'],'') if style_node is not None else ''
  normalized=unicodedata.normalize('NFKC',' '.join(text.split()));ordinal=len(units)+1
  units.append({'unit_id':f'p{ordinal:06d}','ordinal':ordinal,'style':style[:200],'text_sha256':sha_bytes(text.encode()),'normalized_text_sha256':sha_bytes(normalized.encode())})
 if not units:raise SystemExit('governing policy DOCX has no source units')
 return {'format_version':'1.0','algorithm':'AZPR_DOCX_PARAGRAPH_UNITS_V1','source_document_name':name,'source_document_sha256':sha_bytes(raw),'unit_count':len(units),'unit_chain_sha256':sha_bytes(canonical(units)),'units':units}
def schema_registry(bundle:AuthenticatedBundle):
 import jsonschema
 from referencing import Registry,Resource
 registry=Registry();schemas={}
 for rel in sorted(k for k in bundle.entries if k.startswith('repository-overlay/automation/schemas/') and k.endswith('.json')):
  name=PurePosixPath(rel).name;schema=load_json_bytes(bundle.read(rel),name);jsonschema.Draft202012Validator.check_schema(schema);resource=Resource.from_contents(schema);registry=registry.with_resource(name,resource);schemas[name]=schema
  if isinstance(schema.get('$id'),str):registry=registry.with_resource(schema['$id'],resource)
 return schemas,registry
def validate_schema(schemas,registry,name,value):
 import jsonschema
 try:jsonschema.Draft202012Validator(schemas[name],registry=registry,format_checker=jsonschema.FormatChecker()).validate(value)
 except Exception as exc:raise SystemExit(f'{name} validation failed: {exc}') from exc
def load_unique_keyring(value:dict[str,Any])->dict[str,dict[str,Any]]:
 keys={};signers=set();fingerprints=set()
 for item in value.get('keys',[]):
  if not isinstance(item,dict):raise SystemExit('invalid keyring entry')
  key_id=item.get('key_id');signer=item.get('signer_id')
  if key_id in keys or signer in signers:raise SystemExit('duplicate key or signer identity in keyring')
  try:key=serialization.load_pem_public_key(str(item['public_key_pem']).encode())
  except Exception as exc:raise SystemExit('invalid keyring public key') from exc
  if not isinstance(key,Ed25519PublicKey):raise SystemExit('keyring key is not Ed25519')
  fp=sha_bytes(key.public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw))
  if fp in fingerprints:raise SystemExit('duplicate Ed25519 key material under multiple identities')
  keys[key_id]=dict(item,_key=key);signers.add(signer);fingerprints.add(fp)
 return keys
def verify_roles(document,keyring_value,roles):
 keys=load_unique_keyring(keyring_value);unsigned=dict(document);signatures=unsigned.pop('signatures',None);valid=[]
 if not isinstance(signatures,list):raise SystemExit('signed document has no signatures')
 for sig in signatures:
  item=keys.get(sig.get('key_id')) if isinstance(sig,dict) else None
  if not item or item.get('revoked_at') is not None:continue
  try:item['_key'].verify(base64.b64decode(sig['ed25519'],validate=True),canonical(unsigned));valid.append(item)
  except (InvalidSignature,ValueError,TypeError,KeyError):continue
 used=set()
 for role in roles:
  candidates=[x for x in valid if role in x.get('roles',[]) and x['signer_id'] not in used]
  if not candidates:raise SystemExit(f'missing distinct cryptographic signer for role: {role}')
  used.add(candidates[0]['signer_id'])
def verify_wheelhouse(lock_path:Path,wheelhouse:Path):
 pattern=re.compile(r'^([A-Za-z0-9_.-]+)==([^\s]+) --hash=sha256:([0-9a-f]{64})$');required={}
 for line in read_regular(lock_path).decode().splitlines():
  value=line.strip()
  if not value or value.startswith('#'):continue
  match=pattern.fullmatch(value)
  if not match:raise SystemExit(f'invalid dependency lock line: {value}')
  required[match.group(3)]=(match.group(1),match.group(2))
 actual={sha(p):p.name for p in wheelhouse.glob('*.whl')}
 if not required or set(required)!=set(actual):raise SystemExit('wheelhouse does not exactly match dependency lock')

FAULT_COUNTER=0
def fault_checkpoint(label:str,path:Path|None=None):
 global FAULT_COUNTER
 FAULT_COUNTER+=1
 trace=os.environ.get('AZPR_INSTALL_FAULT_TRACE')
 if trace:
  with open(trace,'a',encoding='utf-8') as stream:stream.write(json.dumps({'sequence':FAULT_COUNTER,'label':label,'path':str(path) if path else None},sort_keys=True)+'\n')
 target=os.environ.get('AZPR_INSTALL_FAULT_POINT')
 if target and target in (label,str(FAULT_COUNTER)):
  if os.environ.get('AZPR_EXPLICIT_TEST_MODE')!='1':raise SystemExit('installer fault injection requires AZPR_EXPLICIT_TEST_MODE=1')
  mode=os.environ.get('AZPR_INSTALL_FAULT_MODE','raise')
  if mode=='kill':os.kill(os.getpid(),9)
  raise RuntimeError(f'injected installer fault at {label}#{FAULT_COUNTER}')

def write_once(path:Path,data:bytes,mode:int):
 path.parent.mkdir(parents=True,exist_ok=True);fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),mode)
 try:
  view=memoryview(data)
  while view:view=view[os.write(fd,view):]
  os.fchmod(fd,mode);fault_checkpoint('after_file_write',path);os.fsync(fd);fault_checkpoint('after_file_fsync',path)
 finally:os.close(fd)
def fsync_dir(path:Path):
 fd=os.open(path,os.O_RDONLY|getattr(os,'O_DIRECTORY',0));os.fsync(fd);os.close(fd);fault_checkpoint('after_directory_fsync',path)
def copy_verified(src:Path,dst:Path,mode:int):write_once(dst,read_regular(src),mode);os.chown(dst,0,0)
def copy_bundle(bundle:AuthenticatedBundle,rel:str,dst:Path,mode:int):write_once(dst,bundle.read(rel),mode);os.chown(dst,0,0)
def component(path:Path,mode:int):return {'path':str(path),'sha256':sha(path),'mode':format(mode,'o')}
def staged_component(staged:Path,final_path:Path,mode:int):return {'path':str(final_path),'sha256':sha(staged),'mode':format(mode,'o')}
def sign(private,payload,key_id):
 value=dict(payload);value['signer_key_id']=key_id;value['signature']=base64.b64encode(private.sign(canonical(value))).decode();return value
def harden_tree(root:Path):
 for path in sorted(root.rglob('*'),reverse=True):
  info=os.lstat(path)
  if stat.S_ISLNK(info.st_mode):raise SystemExit(f'symlink in staged generation: {path}')
  if stat.S_ISDIR(info.st_mode):os.chown(path,0,0);os.chmod(path,0o555)
  elif stat.S_ISREG(info.st_mode):os.chown(path,0,0);os.chmod(path,0o555 if info.st_mode&0o111 else 0o444)
  else:raise SystemExit(f'unsafe staged generation entry: {path}')
 os.chown(root,0,0);os.chmod(root,0o555)
def runtime_tree_manifest(root:Path):
 files=[]
 for path in sorted(p for p in root.rglob('*') if p.is_file()):
  st=os.lstat(path)
  if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode) or st.st_nlink!=1:raise SystemExit(f'unsafe Python runtime file: {path}')
  files.append({'path':str(path.relative_to(root)),'sha256':sha(path),'mode':format(st.st_mode&0o777,'o')})
 return {'format_version':'1.0','root':str(root),'files':files,'tree_sha256':sha_bytes(canonical(files))}
def atomic_activate(lock:dict[str,Any]):
 ETC.mkdir(parents=True,exist_ok=True);os.chown(ETC,0,0);os.chmod(ETC,0o755)
 data=(json.dumps(lock,indent=2,sort_keys=True)+'\n').encode();tmp=ETC/f'.trusted-installation.lock.{os.getpid()}.new';write_once(tmp,data,0o444);os.chown(tmp,0,0)
 if ACTIVE_LOCK.exists():
  history=ETC/'history';history.mkdir(exist_ok=True);os.chown(history,0,0);os.chmod(history,0o555)
  old=read_regular(ACTIVE_LOCK);backup=history/f'{sha_bytes(old)}.lock.json'
  if not backup.exists():write_once(backup,old,0o444);os.chown(backup,0,0)
 fault_checkpoint('before_active_lock_replace',ACTIVE_LOCK);os.replace(tmp,ACTIVE_LOCK);fault_checkpoint('after_active_lock_replace',ACTIVE_LOCK);fsync_dir(ETC)


# ---------------------------------------------------------------------------
# v6 trust-boundary helpers
# ---------------------------------------------------------------------------
ACTIVATION_STATE=ETC/'installation-activation-state.json'
RECEIPTS=ETC/'installation-receipts'


def safe_secret(value:str,name:str,*,agent_uid:int,agent_gid:int)->Path:
 path=safe_external(value,name)
 st=os.stat(path);mode=st.st_mode&0o7777
 try:acl_names=set(os.listxattr(path,follow_symlinks=False))
 except (AttributeError,OSError):acl_names=set()
 if {'system.posix_acl_access','system.posix_acl_default'} & acl_names:raise SystemExit(f'{name} must not carry POSIX ACLs')
 if mode not in (0o400,0o600):raise SystemExit(f'{name} must use mode 0400 or 0600 exactly')
 parent=os.lstat(path.parent)
 if parent.st_uid!=0 or parent.st_mode&0o077:raise SystemExit(f'{name} parent directory must be root-owned and private: {path.parent}')
 prove_identity_denied(path,agent_uid,agent_gid,read=True,label=name)
 return path


_IDENTITY_ACCESS_PROBE = r"""
import os, sys
from pathlib import Path
kind, raw_path, raw_uid, raw_gid = sys.argv[1:5]
path = Path(raw_path)
uid, gid = int(raw_uid), int(raw_gid)
os.setgroups([])
os.setgid(gid)
os.setuid(uid)
allowed = False
try:
    nofollow = getattr(os, 'O_NOFOLLOW', 0)
    if kind == 'read':
        fd = os.open(path, os.O_RDONLY | nofollow)
    elif kind == 'write':
        fd = os.open(path, os.O_WRONLY | nofollow)
    elif kind == 'directory':
        fd = os.open(path, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0) | nofollow)
    else:
        raise SystemExit(4)
    os.close(fd)
    allowed = True
except (PermissionError, FileNotFoundError, IsADirectoryError, OSError):
    allowed = False
print('1' if allowed else '0')
"""


def _identity_access_allowed(path:Path,uid:int,gid:int,kind:str,label:str)->bool:
 if os.geteuid()!=0:raise SystemExit('agent-identity access proof requires root')
 executable=str(Path(sys.executable).resolve())
 try:
  result=subprocess.run(
   [executable,'-I','-c',_IDENTITY_ACCESS_PROBE,kind,str(path),str(uid),str(gid)],
   cwd='/',env={'PATH':'/usr/bin:/bin','PYTHONDONTWRITEBYTECODE':'1','LANG':'C.UTF-8','LC_ALL':'C.UTF-8'},
   capture_output=True,text=True,timeout=30,check=False,
  )
 except (OSError,subprocess.SubprocessError) as exc:raise SystemExit(f'agent access proof failed for {label}') from exc
 value=result.stdout.strip()
 if result.returncode!=0 or value not in ('0','1'):raise SystemExit(f'agent access proof failed for {label}')
 return value=='1'


def prove_identity_denied(path:Path,uid:int,gid:int,*,read:bool,label:str)->None:
 kind='read' if read else 'write'
 if _identity_access_allowed(path,uid,gid,kind,label):raise SystemExit(f'configured agent identity can access secret {label}: {path}')


def prove_identity_cannot_traverse(path:Path,uid:int,gid:int,label:str)->None:
 """Prove the agent cannot open a controller-only directory."""
 if _identity_access_allowed(path,uid,gid,'directory',label):raise SystemExit(f'configured agent identity can traverse controller-only directory {label}: {path}')


def verify_key_pair(private_path:Path,public_path:Path,label:str)->None:
 try:
  private=serialization.load_pem_private_key(read_regular(private_path,64*1024),password=None)
  public=serialization.load_pem_public_key(read_regular(public_path,64*1024))
 except Exception as exc:raise SystemExit(f'invalid {label} key pair') from exc
 if not isinstance(private,Ed25519PrivateKey) or not isinstance(public,Ed25519PublicKey):raise SystemExit(f'{label} key pair must be Ed25519')
 challenge=os.urandom(64)
 try:public.verify(private.sign(challenge),challenge)
 except InvalidSignature as exc:raise SystemExit(f'{label} private/public keys do not match') from exc


UNSUPPORTED_DOCX_TAGS={
 'tbl','txbxContent','fldSimple','fldChar','instrText','footnoteReference','endnoteReference',
 'commentReference','ins','del','moveFrom','moveTo','altChunk','object','pict','drawing','sdt',
}
def local_name(tag:str)->str:return tag.rsplit('}',1)[-1]
def render_docx_paragraph(paragraph:ET.Element):
 counts={'text_nodes':0,'tabs':0,'breaks':0};pieces=[]
 for node in paragraph.iter():
  name=local_name(node.tag)
  if name in UNSUPPORTED_DOCX_TAGS:raise SystemExit(f'unsupported normative DOCX feature: {name}')
  if name=='numPr':raise SystemExit('Word automatic numbering is unsupported; policy extraction fails closed')
  if name=='t':pieces.append(node.text or '');counts['text_nodes']+=1
  elif name=='tab':pieces.append('\t');counts['tabs']+=1
  elif name in ('br','cr'):pieces.append('\n');counts['breaks']+=1
  elif name=='noBreakHyphen':pieces.append('‑')
  elif name=='softHyphen':pieces.append('\u00ad')
 return ''.join(pieces),counts
def supported_docx_parts(z:zipfile.ZipFile):
 names=z.namelist()
 if len(names)!=len(set(names)):raise SystemExit('DOCX contains duplicate ZIP members')
 for name in names:
  pp=PurePosixPath(name)
  if pp.is_absolute() or '..' in pp.parts or '\\' in name:raise SystemExit('DOCX contains unsafe member paths')
 try:document=ET.fromstring(z.read('word/document.xml'))
 except (KeyError,ET.ParseError) as exc:raise SystemExit('governing policy DOCX XML is invalid') from exc
 unsupported=[]
 for name in names:
  lower=name.lower()
  if not lower.startswith('word/') or not lower.endswith('.xml') or lower=='word/document.xml':continue
  if any(token in lower for token in ('header','footer','footnote','endnote','comments','glossary','people','document2')):
   try:part=ET.fromstring(z.read(name))
   except ET.ParseError as exc:raise SystemExit(f'invalid DOCX part: {name}') from exc
   visible=[]
   for node in part.iter():
    lname=local_name(node.tag)
    if lname=='t' and (node.text or ''):visible.append(node.text or '')
    elif lname in ('tab','br','cr'):visible.append(lname)
   if visible:unsupported.append(name)
 if unsupported:raise SystemExit('unsupported normative DOCX parts are nonempty: '+', '.join(sorted(unsupported)))
 return document,{'package_member_count':len(names),'unsupported_features':[],'unsupported_normative_parts':[]}
def derive_docx_artifacts(raw:bytes,name:str):
 try:
  with zipfile.ZipFile(io.BytesIO(raw)) as z:root,feature_inventory=supported_docx_parts(z)
 except SystemExit:raise
 except Exception as exc:raise SystemExit('governing policy source is not a valid DOCX') from exc
 body=root.find('.//w:body',DOCX_NS)
 if body is None:raise SystemExit('governing policy DOCX has no body')
 paragraphs=[];totals={'paragraphs':0,'text_nodes':0,'tabs':0,'breaks':0}
 for child in list(body):
  lname=local_name(child.tag)
  if lname=='sectPr':continue
  if lname!='p':raise SystemExit(f'unsupported top-level DOCX body feature: {lname}')
  text,counts=render_docx_paragraph(child)
  if text=='':continue
  style_node=child.find('./w:pPr/w:pStyle',DOCX_NS);style=style_node.attrib.get('{%s}val'%DOCX_NS['w'],'') if style_node is not None else ''
  paragraphs.append((text,style[:200],counts));totals['paragraphs']+=1
  for key in ('text_nodes','tabs','breaks'):totals[key]+=counts[key]
 if not paragraphs:raise SystemExit('governing policy DOCX has no source units')
 chunks=[];units=[];mappings=[];offset=0
 for index,(text,style,counts) in enumerate(paragraphs,1):
  text_bytes=text.encode('utf-8');separator=b'\n' if index==len(paragraphs) else b'\n\n';span=text_bytes+separator;start=offset;text_end=start+len(text_bytes);end=start+len(span);uid=f'p{index:06d}';normalized=unicodedata.normalize('NFKC',text)
  unit={'unit_id':uid,'ordinal':index,'style':style,'text_sha256':sha_bytes(text_bytes),'normalized_text_sha256':sha_bytes(normalized.encode()),'text_length_bytes':len(text_bytes),'tab_count':counts['tabs'],'break_count':counts['breaks'],'canonical_start_byte':start,'canonical_text_end_byte':text_end,'canonical_end_byte':end,'canonical_text_sha256':sha_bytes(text_bytes),'canonical_span_sha256':sha_bytes(span)}
  units.append(unit);mappings.append({'mapping_id':f'm{index:06d}','source_unit_id':uid,'canonical_start_byte':start,'canonical_text_end_byte':text_end,'canonical_end_byte':end,'source_text_sha256':unit['text_sha256'],'canonical_text_sha256':unit['canonical_text_sha256'],'canonical_span_sha256':unit['canonical_span_sha256'],'review_status':'EXACT_SUPPORTED_OOXML'});chunks.append(span);offset=end
 canonical_bytes=b''.join(chunks);features={**feature_inventory,**totals,'rendered_tab_count':totals['tabs'],'rendered_break_count':totals['breaks']}
 manifest={'format_version':'3.0','algorithm':'AZPR_DOCX_SUPPORTED_OOXML_UNITS_V3','canonical_render_algorithm':'AZPR_DOCX_SUPPORTED_OOXML_UTF8_V3','source_document_name':name,'source_document_sha256':sha_bytes(raw),'canonical_policy_sha256':sha_bytes(canonical_bytes),'canonical_byte_length':len(canonical_bytes),'unit_count':len(units),'unit_chain_sha256':sha_bytes(canonical(units)),'feature_inventory':features,'units':units}
 section={'format_version':'4.0','algorithm':'AZPR_DOCX_SUPPORTED_OOXML_UTF8_V3','source_document_name':name,'source_document_sha256':manifest['source_document_sha256'],'source_manifest_sha256':'','canonical_policy_sha256':manifest['canonical_policy_sha256'],'canonical_byte_length':len(canonical_bytes),'source_unit_count':len(units),'feature_inventory_sha256':sha_bytes(canonical(features)),'mappings':mappings}
 return manifest,canonical_bytes,section

def verify_exact_canonical(source_raw:bytes,source_name:str,manifest_raw:bytes,canonical_raw:bytes,section_raw:bytes):
 manifest=load_json_bytes(manifest_raw,'canonical source manifest');section=load_json_bytes(section_raw,'canonical section map');derived,expected_canonical,expected_section=derive_docx_artifacts(source_raw,source_name)
 if manifest!=derived:raise SystemExit('canonical source manifest is not the deterministic v3 supported-OOXML manifest')
 if canonical_raw!=expected_canonical:raise SystemExit('canonical policy is not the exact supported-OOXML governing DOCX rendering')
 expected_section['source_manifest_sha256']=sha_bytes(manifest_raw)
 if section!=expected_section:raise SystemExit('canonical section map is not the deterministic supported-OOXML byte-span map')
 return manifest,section

def wheel_metadata(path:Path):
 with zipfile.ZipFile(path) as z:
  names=[n for n in z.namelist() if n.endswith('.dist-info/METADATA')]
  if len(names)!=1:raise SystemExit(f'ambiguous wheel metadata: {path.name}')
  text=z.read(names[0]).decode('utf-8','replace')
 name=version=None
 for line in text.splitlines():
  if line.startswith('Name: '):name=line[6:].strip()
  elif line.startswith('Version: '):version=line[9:].strip()
 if not name or not version:raise SystemExit(f'incomplete wheel metadata: {path.name}')
 return name.lower().replace('_','-'),version


def verified_wheel_inventory(lock_path:Path,wheelhouse:Path):
 pattern=re.compile(r'^([A-Za-z0-9_.-]+)==([^\s]+) --hash=sha256:([0-9a-f]{64})$');locked=[]
 for line in read_regular(lock_path).decode().splitlines():
  value=line.strip()
  if not value or value.startswith('#'):continue
  match=pattern.fullmatch(value)
  if not match:raise SystemExit(f'invalid dependency lock line: {value}')
  locked.append({'name':match.group(1).lower().replace('_','-'),'version':match.group(2),'sha256':match.group(3)})
 rows=[]
 for wheel in sorted(wheelhouse.glob('*.whl')):
  name,version=wheel_metadata(wheel);rows.append({'filename':wheel.name,'sha256':sha(wheel),'name':name,'version':version,'size':wheel.stat().st_size})
 if not rows:raise SystemExit('wheelhouse is empty')
 lock_tuples={(x['name'],x['version'],x['sha256']) for x in locked};wheel_tuples={(x['name'],x['version'],x['sha256']) for x in rows}
 if lock_tuples!=wheel_tuples or len(locked)!=len(rows):raise SystemExit('wheelhouse does not exactly match dependency lock')
 return rows


def verify_detached_signature(document:dict[str,Any],public_path:Path,expected_key_id:str,label:str):
 unsigned=dict(document);signature=unsigned.pop('signature',None)
 if unsigned.get('signer_key_id')!=expected_key_id:raise SystemExit(f'{label} signer key mismatch')
 try:
  key=serialization.load_pem_public_key(read_regular(public_path,64*1024))
  if not isinstance(key,Ed25519PublicKey):raise SystemExit(f'{label} key is not Ed25519')
  key.verify(base64.b64decode(str(signature),validate=True),canonical(unsigned))
 except (InvalidSignature,ValueError,TypeError) as exc:raise SystemExit(f'{label} signature verification failed') from exc


def verify_supply_chain(schemas,registry,external:dict[str,Path],wheelhouse:Path,image_digest:str):
 if not re.fullmatch(r'sha256:[0-9a-f]{64}',image_digest):raise SystemExit('validation image digest must be sha256:<64 hex>')
 wheels=verified_wheel_inventory(external['dependency_lock'],wheelhouse)
 provenance=load_json_path(external['build_provenance'],'build provenance');attestation=load_json_path(external['validation_image_attestation'],'validation image attestation');mirror_inventory=load_json_path(external['dependency_mirror_inventory'],'dependency mirror inventory');mirror_attestation=load_json_path(external['dependency_mirror_attestation'],'dependency mirror attestation')
 validate_schema(schemas,registry,'build-provenance.schema.json',provenance);validate_schema(schemas,registry,'validation-image-attestation.schema.json',attestation);validate_schema(schemas,registry,'dependency-mirror-inventory.schema.json',mirror_inventory);validate_schema(schemas,registry,'dependency-mirror-attestation.schema.json',mirror_attestation)
 files=mirror_inventory['files'];inventory_hash=sha_bytes(canonical(files));total=sum(int(x['size']) for x in files)
 if mirror_inventory['inventory_sha256']!=inventory_hash or mirror_inventory['file_count']!=len(files) or mirror_inventory['total_bytes']!=total:raise SystemExit('dependency mirror inventory self-identity mismatch')
 if mirror_attestation['mirror_name']!=mirror_inventory['mirror_name'] or mirror_attestation['inventory_sha256']!=inventory_hash or mirror_attestation['file_count']!=len(files) or mirror_attestation['total_bytes']!=total:raise SystemExit('dependency mirror attestation does not bind exact inventory')
 verify_detached_signature(mirror_attestation,external['dependency_mirror_public_key'],mirror_attestation['signer_key_id'],'dependency mirror attestation')
 wheel_set_hash=sha_bytes(canonical(wheels));passes=provenance.get('resolution_passes',[])
 expected_mirror={'name':mirror_inventory['mirror_name'],'inventory_sha256':inventory_hash,'attestation_sha256':sha(external['dependency_mirror_attestation']),'public_key_sha256':sha(external['dependency_mirror_public_key']),'signer_key_id':mirror_attestation['signer_key_id'],'file_count':len(files)}
 if provenance.get('requirements_input_sha256')!=sha(external['requirements_input']):raise SystemExit('build provenance does not bind exact requirements input')
 if provenance.get('dependency_lock_sha256')!=sha(external['dependency_lock']):raise SystemExit('build provenance does not bind exact dependency lock')
 if provenance.get('mirror')!=expected_mirror:raise SystemExit('build provenance does not bind exact dependency mirror inputs')
 mirror_rows={(str(x['path']).split('/')[-1],x['sha256'],int(x['size'])) for x in files}
 for wheel in wheels:
  if (wheel['filename'],wheel['sha256'],wheel['size']) not in mirror_rows:raise SystemExit(f"installed wheel is not present in signed mirror inventory: {wheel['filename']}")
 if provenance.get('builder',{}).get('python_sha256')!=sha(external['python_binary']):raise SystemExit('build provenance does not bind exact build Python binary')
 if provenance.get('wheels')!=wheels or len(passes)!=2 or any(p.get('wheel_set_sha256')!=wheel_set_hash for p in passes) or provenance.get('reproducible') is not True:raise SystemExit('build provenance does not bind two identical wheel-resolution passes')
 try:sbom=load_json_path(external['sbom'],'SBOM')
 except SystemExit:raise
 components=[]
 for item in sbom.get('components',[]):
  if not isinstance(item,dict):continue
  wheel_name=None
  for prop in item.get('properties',[]):
   if isinstance(prop,dict) and prop.get('name')=='azpr:wheel':wheel_name=prop.get('value')
  hashes=[h.get('content') for h in item.get('hashes',[]) if isinstance(h,dict) and h.get('alg')=='SHA-256']
  if wheel_name and len(hashes)==1:components.append({'filename':wheel_name,'sha256':hashes[0],'name':str(item.get('name','')).lower().replace('_','-'),'version':item.get('version')})
 expected_components=[{k:r[k] for k in ('filename','sha256','name','version')} for r in wheels]
 if sorted(components,key=lambda x:x['filename'])!=sorted(expected_components,key=lambda x:x['filename']):raise SystemExit('SBOM does not exactly describe installed wheelhouse')
 expected_attestation={'sbom_sha256':sha(external['sbom']),'build_provenance_sha256':sha(external['build_provenance']),'dockerfile_sha256':sha(external['validation_dockerfile']),'image_digest':image_digest}
 for key,value in expected_attestation.items():
  if attestation.get(key)!=value:raise SystemExit(f'validation image attestation does not bind exact {key}')
 return {'requirements_input_sha256':sha(external['requirements_input']),'dependency_lock_sha256':sha(external['dependency_lock']),'mirror_inventory_sha256':sha(external['dependency_mirror_inventory']),'mirror_attestation_sha256':sha(external['dependency_mirror_attestation']),'mirror_public_key_sha256':sha(external['dependency_mirror_public_key']),'wheel_set_sha256':wheel_set_hash,'sbom_sha256':sha(external['sbom']),'build_provenance_sha256':sha(external['build_provenance']),'validation_dockerfile_sha256':sha(external['validation_dockerfile']),'validation_image_attestation_sha256':sha(external['validation_image_attestation']),'validation_image_digest':image_digest}


def atomic_write_json(path:Path,value:dict[str,Any],mode:int=0o600):
 path.parent.mkdir(parents=True,exist_ok=True);tmp=path.parent/f'.{path.name}.{os.getpid()}.{os.urandom(4).hex()}.new';write_once(tmp,(json.dumps(value,indent=2,sort_keys=True)+'\n').encode(),mode);os.chown(tmp,0,0);fault_checkpoint('before_atomic_json_replace',path);os.replace(tmp,path);fault_checkpoint('after_atomic_json_replace',path);fsync_dir(path.parent)


def _state_descendant(value:Any,root:Path,label:str,*,file_path:bool=False)->Path:
 if not isinstance(value,str) or not value:raise SystemExit(f'activation state has invalid {label}')
 path=Path(value)
 if not path.is_absolute():raise SystemExit(f'activation state {label} is not absolute')
 path=Path(os.path.normpath(str(path)));base=Path(os.path.normpath(str(root)))
 try:relative=path.relative_to(base)
 except ValueError as exc:raise SystemExit(f'activation state {label} escapes trusted root') from exc
 if not relative.parts:raise SystemExit(f'activation state {label} cannot select the trusted root itself')
 if file_path and len(relative.parts)!=1:raise SystemExit(f'activation state {label} must be a direct receipt child')
 for candidate in [path.parent,*path.parent.parents]:
  if candidate==base.parent:break
  if candidate.exists() and stat.S_ISLNK(os.lstat(candidate).st_mode):raise SystemExit(f'activation state {label} has symlinked ancestor')
 return path



def _remove_empty_cgroup(path:Path):
 if not path.exists():return
 try:
  pids=[int(x) for x in (path/'cgroup.procs').read_text().split()]
 except OSError:pids=[]
 if pids:raise SystemExit(f'cannot remove nonempty installation cgroup: {pids[:16]}')
 try:path.rmdir()
 except OSError as exc:raise SystemExit(f'cannot remove installation cgroup: {path}') from exc

def recover_activation_state():
 if not ACTIVATION_STATE.exists():return None
 state=load_json_path(ACTIVATION_STATE,'activation state')
 new_hash=state.get('new_lock_sha256');previous_hash=state.get('previous_lock_sha256')
 pending=_state_descendant(state.get('pending_receipt_path'),RECEIPTS,'pending receipt',file_path=True)
 final_receipt=_state_descendant(state.get('final_receipt_path'),RECEIPTS,'final receipt',file_path=True)
 generation=_state_descendant(state.get('generation_path'),GENERATIONS,'generation')
 staging=_state_descendant(state.get('staging_path'),GENERATIONS,'staging generation')
 secure=_state_descendant(state.get('secure_path'),VAR/'secure','secure generation')
 runtime=_state_descendant(state.get('runtime_path'),VAR/'runtime','runtime generation')
 handoff=_state_descendant(state.get('agent_handoff_path'),AGENT_HANDOFF_BASE,'agent handoff generation')
 cgroup=_state_descendant(state.get('agent_cgroup_path'),AGENT_CGROUP_BASE,'agent cgroup generation') if state.get('agent_cgroup_path') else None
 active_hash=sha(ACTIVE_LOCK) if ACTIVE_LOCK.exists() else None
 if active_hash==new_hash:
  if not generation.exists():raise SystemExit('active installation lock points to a missing generation')
  if not handoff.exists():raise SystemExit('active installation lock points to a missing agent handoff generation')
  if cgroup is not None and not cgroup.exists():raise SystemExit('active installation lock points to a missing agent cgroup generation')
  if not final_receipt.exists():
   if not pending.exists():raise SystemExit('active generation has no recoverable installation receipt')
   final_receipt.parent.mkdir(parents=True,exist_ok=True);os.replace(pending,final_receipt);os.chown(final_receipt,0,0);os.chmod(final_receipt,0o444);fsync_dir(final_receipt.parent)
  if staging.exists():shutil.rmtree(staging,ignore_errors=False)
  ACTIVATION_STATE.unlink();fsync_dir(ETC);return 'COMPLETED_ACTIVE_GENERATION'
 if active_hash==previous_hash or (previous_hash is None and active_hash is None):
  if pending.exists():pending.unlink()
  for directory in (staging,generation,secure,runtime,handoff):
   if directory.exists():shutil.rmtree(directory,ignore_errors=False)
  if cgroup is not None:_remove_empty_cgroup(cgroup)
  ACTIVATION_STATE.unlink();fsync_dir(ETC);return 'ROLLED_BACK_UNACTIVATED_GENERATION'
 raise SystemExit('activation state cannot be reconciled with active installation lock')


AUTHORIZATION_LEDGER=VAR/'qualification-authorizations-v10'

def _parse_utc(value:Any,label:str):
 try:return datetime.fromisoformat(str(value).replace('Z','+00:00')).astimezone(timezone.utc)
 except Exception as exc:raise SystemExit(f'invalid {label} timestamp') from exc

def _require_fresh(document:dict[str,Any],label:str,max_days:int=31):
 now=datetime.now(timezone.utc);issued=_parse_utc(document.get('issued_at'),label+' issued_at');expires=_parse_utc(document.get('expires_at'),label+' expires_at')
 if issued>now or expires<=now or (expires-issued).days>max_days:raise SystemExit(f'{label} is stale, future-dated, or overlong')

def _verify_single_signature(document:dict[str,Any],public_key_path:Path,expected_key_id:str,label:str):
 unsigned=dict(document);signature=unsigned.pop('signature',None)
 if unsigned.get('signer_key_id')!=expected_key_id:raise SystemExit(f'{label} signer key ID mismatch')
 try:
  key=serialization.load_pem_public_key(read_regular(public_key_path,64*1024))
  if not isinstance(key,Ed25519PublicKey):raise SystemExit(f'{label} public key is not Ed25519')
  key.verify(base64.b64decode(str(signature),validate=True),canonical(unsigned))
 except (InvalidSignature,ValueError,TypeError) as exc:raise SystemExit(f'{label} signature verification failed') from exc

def _host_identity(path:Path)->dict[str,Any]:
 value=load_json_path(path,'host identity')
 expected={'format_version','host_id','attestation_sha256','measured_boot_policy_sha256','os_policy_sha256'}
 if set(value)!=expected or value.get('format_version')!='1.0':raise SystemExit('host identity document is malformed')
 if not re.fullmatch(r'[A-Za-z0-9._:-]{8,160}',str(value.get('host_id'))):raise SystemExit('host identity is invalid')
 for name in expected-{'format_version','host_id'}:
  if not re.fullmatch(r'[0-9a-f]{64}',str(value.get(name))):raise SystemExit(f'host identity {name} is invalid')
 return value

def _v10_probe_target_bindings(manifest_path:Path,args,bundle:AuthenticatedBundle):
 manifest=load_json_path(manifest_path,'v10 probe envelope manifest')
 validate_schema(*schema_registry(bundle),'qualification-probe-envelopes-manifest-v10.schema.json',manifest)
 target_paths={
  'git_binary':safe_external(args.git_binary,'git_binary',executable=True),'python_binary':safe_external(args.python_binary,'python_binary',executable=True),
  'codex_binary':safe_external(args.codex_binary,'codex_binary',executable=True),'container_engine':safe_external(args.container_engine,'container_engine',executable=True),
  'anchor_helper':safe_external(args.anchor_helper,'anchor_helper',executable=True),'mount_binary':safe_external(args.mount_binary,'mount_binary',executable=True),
  'umount_binary':safe_external(args.umount_binary,'umount_binary',executable=True),
 }
 bundle_targets={
  'cleanroom_adapter':sha_bytes(bundle.read('external-capability-runner/mock_noop_adapter.py')),
  'qualification_verifier':sha_bytes(bundle.read('operator-tools/verify_v10_cleanroom_prerequisites.py')),
 }
 for name,row in manifest['envelopes'].items():
  envelope_path=safe_external(row['path'],f'probe_envelope_{name}')
  if sha(envelope_path)!=row['sha256']:raise SystemExit(f'probe envelope hash mismatch before reservation: {name}')
  envelope=load_json_path(envelope_path,f'probe envelope {name}')
  expected=sha(target_paths[name]) if name in target_paths else bundle_targets[name]
  if envelope.get('target_role')!=name or envelope.get('target_sha256')!=expected:raise SystemExit(f'actual installer target differs from no-secret probe: {name}')
 return target_paths

def _v10_policy_preflight(args,schemas,registry,approval_path:Path,governing_source:Path,installation_phase:str):
 policy_args={'canonical_policy':args.canonical_policy,'canonical_policy_source_manifest':args.canonical_policy_source_manifest,'canonical_policy_record':args.canonical_policy_record,'canonical_policy_section_map':args.canonical_policy_section_map}
 if installation_phase=='QUALIFICATION_ONLY':
  if any(policy_args.values()):raise SystemExit('qualification-only installation must not accept canonical-policy derivatives')
  return None
 if installation_phase!='POLICY_ACTIVATED' or any(not v for v in policy_args.values()):raise SystemExit('policy activation requires all canonical-policy artifacts')
 paths={name:safe_external(value,name) for name,value in policy_args.items()}
 source_raw=read_regular(governing_source);manifest_raw=read_regular(paths['canonical_policy_source_manifest']);canonical_raw=read_regular(paths['canonical_policy']);section_raw=read_regular(paths['canonical_policy_section_map'])
 source_manifest,section=verify_exact_canonical(source_raw,governing_source.name,manifest_raw,canonical_raw,section_raw)
 validate_schema(schemas,registry,'canonical-policy-source-manifest.schema.json',source_manifest);validate_schema(schemas,registry,'canonical-policy-section-map.schema.json',section)
 approval=load_json_path(approval_path,'approval keyring');validate_schema(schemas,registry,'public-keyring.schema.json',approval);load_unique_keyring(approval)
 record=load_json_path(paths['canonical_policy_record'],'canonical policy record');validate_schema(schemas,registry,'canonical-policy-record.schema.json',record);verify_roles(record,approval,['policy-owner','security-approver'])
 # canonical policy record input hashes do not match is a fatal fail-closed condition.
 expected={'source_document_sha256':sha_bytes(source_raw),'source_manifest_sha256':sha_bytes(manifest_raw),'canonical_policy_sha256':sha_bytes(canonical_raw),'section_map_sha256':sha_bytes(section_raw),'source_unit_count':source_manifest['unit_count'],'mapped_source_unit_count':source_manifest['unit_count'],'canonical_byte_length':len(canonical_raw),'canonical_render_algorithm':'AZPR_DOCX_SUPPORTED_OOXML_UTF8_V3','feature_inventory_sha256':section['feature_inventory_sha256'],'completeness_statement':'EXACT_SUPPORTED_OOXML_RENDER_VERIFIED','unsupported_feature_count':0}
 for key,value in expected.items():
  if record.get(key)!=value:raise SystemExit(f'canonical policy record does not bind exact {key}')
 return {'paths':paths,'record':record}

def _qualification_preflight(args):
 """V10.1 read-only exact binding verification before authorization reservation."""
 names=['candidate_archive','qualification_authorization','qualification_authorization_keyring','qualification_revocation_list','qualification_receipt','host_identity','agent_execution_profile','handoff_quota_profile','bundle_attestation','bundle_signing_public_key','qualified_artifact_inputs','qualification_probe_envelopes_manifest','key_lifecycle_state','phase_transition_keyring','validation_registry_proof',*['codex_isolation_qualification_report','remote_anchor_qualification_report','key_custody_qualification_report','installer_fault_matrix_report','supply_chain_rebuild_report','dedicated_host_policy']]
 public_inputs={name:safe_external(getattr(args,name),name) for name in names if getattr(args,name,None)}
 bootstrap=verify_bootstrap_roots(BOOTSTRAP_ROOT_MANIFEST,BOOTSTRAP_AUTHORITY_KEY,qualification_authorization_keyring=public_inputs['qualification_authorization_keyring'],qualification_receipt_public_key=QUALIFICATION_RECEIPT_KEY,phase_transition_keyring=public_inputs['phase_transition_keyring'],authorization_anchor=Path(args.anchor_helper),qualification_trust_manifest=QUALIFICATION_TRUST_MANIFEST,qualification_trust_authority_public_key=QUALIFICATION_TRUST_AUTHORITY_KEY,host_qualification_roots_manifest=HOST_QUALIFICATION_ROOTS_MANIFEST,host_qualification_roots_authority_public_key=HOST_QUALIFICATION_ROOTS_AUTHORITY_KEY,trusted_ancestor=ETC,expected_owner_uid=0,minimum_sequence=1)
 bundle=authenticate_bundle(args.bundle_root,public_inputs['bundle_attestation'],public_inputs['bundle_signing_public_key'],args.bundle_signing_key_id,expected_archive_sha256=sha(public_inputs['candidate_archive']))
 schemas,registry=schema_registry(bundle)
 auth=load_json_path(public_inputs['qualification_authorization'],'qualification installation authorization');validate_schema(schemas,registry,'qualification-installation-authorization-v10.schema.json',auth);_require_fresh(auth,'qualification authorization',7)
 receipt=load_json_path(public_inputs['qualification_receipt'],'semantic qualification receipt');validate_schema(schemas,registry,'cleanroom-qualification-receipt-v10.schema.json',receipt);_require_fresh(receipt,'semantic qualification receipt',14)
 qkeyring=load_json_path(public_inputs['qualification_authorization_keyring'],'qualification authorization keyring');validate_schema(schemas,registry,'public-keyring.schema.json',qkeyring);load_unique_keyring(qkeyring)
 revocations=load_json_path(public_inputs['qualification_revocation_list'],'qualification revocation list');validate_schema(schemas,registry,'qualification-revocation-list.schema.json',revocations);_require_fresh(revocations,'qualification revocation list',31);verify_roles(revocations,qkeyring,['revocation-authority','security-approver']);verify_roles(auth,qkeyring,['installation-authorizer','security-approver'])
 _verify_single_signature(receipt,QUALIFICATION_RECEIPT_KEY,receipt['signer_key_id'],'semantic qualification receipt')
 if receipt.get('qualification_artifact_set_version')!=QUALIFICATION_ARTIFACT_SET_VERSION:raise SystemExit('receipt artifact-set version mismatch')
 host_context=load_host_qualification_context(expected_host_id=receipt['host_id'],expected_candidate_archive_sha256=receipt['candidate_archive_sha256'],expected_challenge_sha256=receipt['challenge_sha256']);authority=load_approved_probe_authority(host_context=host_context,expected_host_id=receipt['host_id'],expected_candidate_archive_sha256=receipt['candidate_archive_sha256'],expected_challenge_sha256=receipt['challenge_sha256'])
 if receipt.get('qualification_trust_binding')!=authority.trust_binding or receipt.get('qualification_trust_binding_sha256')!=authority.trust_binding_sha256:raise SystemExit('receipt probe authority is not independently approved')
 if any(sig.get('key_id') in set(revocations['revoked_key_ids']) for sig in auth['signatures']):raise SystemExit('qualification authorization uses a revoked key')
 manifest_raw=read_regular(bundle.root/'SHA256SUMS.json');manifest_hash=sha_bytes(manifest_raw);tree_hash=sha_bytes(canonical(bundle.entries));host=_host_identity(public_inputs['host_identity'])
 execution=load_json_path(public_inputs['agent_execution_profile'],'agent execution profile');quota=load_json_path(public_inputs['handoff_quota_profile'],'handoff quota profile');validate_schema(schemas,registry,'agent-execution-profile.schema.json',execution);validate_schema(schemas,registry,'handoff-quota-profile.schema.json',quota);_require_fresh(execution,'agent execution profile',31)
 uid=int(args.agent_uid);gid=int(args.agent_gid)
 if execution['agent_uid']!=uid or execution['agent_gid']!=gid or execution['host_id']!=host['host_id'] or execution['quota_profile_sha256']!=sha(public_inputs['handoff_quota_profile']):raise SystemExit('agent execution profile exact binding mismatch')
 if receipt['host_id']!=host['host_id'] or receipt['agent_uid']!=uid or receipt['agent_gid']!=gid:raise SystemExit('qualification receipt host/agent mismatch')
 if receipt['candidate_archive_sha256']!=sha(public_inputs['candidate_archive']) or receipt['bundle_manifest_sha256']!=manifest_hash:raise SystemExit('qualification receipt bundle mismatch')
 if receipt['artifact_bindings_sha256']!=sha_bytes(canonical(receipt['artifact_bindings'])):raise SystemExit('receipt artifact aggregate is invalid')
 if receipt['probe_envelopes_manifest_sha256']!=sha(public_inputs['qualification_probe_envelopes_manifest']):raise SystemExit('receipt does not bind exact probe envelope manifest')
 target_paths=_v10_probe_target_bindings(public_inputs['qualification_probe_envelopes_manifest'],args,bundle)
 target_hashes={name:sha(path) for name,path in target_paths.items()};target_hashes['cleanroom_adapter']=sha_bytes(bundle.read('external-capability-runner/mock_noop_adapter.py'));target_hashes['qualification_verifier']=sha_bytes(bundle.read('operator-tools/verify_v10_cleanroom_prerequisites.py'))
 probe_verification=verify_probe_manifest(public_inputs['qualification_probe_envelopes_manifest'],target_hashes=target_hashes,approved_authority=authority)
 if probe_verification['manifest_sha256']!=receipt['probe_envelopes_manifest_sha256'] or probe_verification['qualification_trust_binding_sha256']!=receipt['qualification_trust_binding_sha256']:raise SystemExit('installer probe re-verification differs from receipt')
 expected_paths={
  'bundle_zip':public_inputs['candidate_archive'],'bundle_attestation':public_inputs['bundle_attestation'],'bundle_signing_public_key':public_inputs['bundle_signing_public_key'],
  'runtime_private_key':Path(args.runtime_private_key),'runtime_public_key':Path(args.runtime_public_key),'evidence_private_key':Path(args.evidence_private_key),'evidence_public_key':Path(args.evidence_public_key),
  'installation_signing_private_key':Path(args.installation_signing_private_key),'installation_signing_public_key':Path(args.installation_signing_public_key),
  'qualification_receipt_signing_public_key':QUALIFICATION_RECEIPT_KEY,'qualification_authorization_keyring':public_inputs['qualification_authorization_keyring'],'qualification_revocation_list':public_inputs['qualification_revocation_list'],
  'phase_transition_keyring':public_inputs['phase_transition_keyring'],'qualification_probe_envelopes_manifest':public_inputs['qualification_probe_envelopes_manifest'],'host_qualification_roots_manifest':HOST_QUALIFICATION_ROOTS_MANIFEST,'host_qualification_roots_authority_public_key':HOST_QUALIFICATION_ROOTS_AUTHORITY_KEY,'host_root_anchor_client':HOST_ROOT_ANCHOR_CLIENT,'host_root_anchor_identity':HOST_ROOT_ANCHOR_IDENTITY,'qualification_trust_manifest':QUALIFICATION_TRUST_MANIFEST,'qualification_trust_authority_public_key':QUALIFICATION_TRUST_AUTHORITY_KEY,'probe_keyring':PROBE_KEYRING,'probe_policy':PROBE_POLICY,'probe_service_identity':PROBE_SERVICE_IDENTITY,'probe_service_attestation':PROBE_SERVICE_ATTESTATION,'probe_revocation_state':PROBE_REVOCATION_STATE,'probe_attestor_keyring':PROBE_ATTESTOR_KEYRING,'probe_attestor_revocation_state':PROBE_ATTESTOR_REVOCATION_STATE,'probe_service_executable':PROBE_SERVICE_EXECUTABLE,'external_signer_client':EXTERNAL_SIGNER_CLIENT,'external_signer_identity':EXTERNAL_SIGNER_IDENTITY,
  'approval_keyring':Path(args.approval_keyring),'evidence_keyring':Path(args.evidence_keyring),'git_binary':Path(args.git_binary),'python_binary':Path(args.python_binary),'codex_binary':Path(args.codex_binary),'container_engine':Path(args.container_engine),'anchor_helper':Path(args.anchor_helper),
  'governing_policy_source':Path(args.governing_policy_source),'requirements_input':Path(args.requirements_input),'dependency_lock':Path(args.dependency_lock),'dependency_mirror_inventory':Path(args.dependency_mirror_inventory),'dependency_mirror_attestation':Path(args.dependency_mirror_attestation),'dependency_mirror_public_key':Path(args.dependency_mirror_public_key),
  'sbom':Path(args.sbom),'build_provenance':Path(args.build_provenance),'validation_dockerfile':Path(args.validation_dockerfile),'validation_image_attestation':Path(args.validation_image_attestation),'validation_registry_proof':public_inputs['validation_registry_proof'],'agent_execution_profile':public_inputs['agent_execution_profile'],'handoff_quota_profile':public_inputs['handoff_quota_profile'],'key_lifecycle_state':public_inputs['key_lifecycle_state'],
  **{name:public_inputs[name] for name in ('codex_isolation_qualification_report','remote_anchor_qualification_report','key_custody_qualification_report','installer_fault_matrix_report','supply_chain_rebuild_report','dedicated_host_policy')},
 }
 artifact_inputs=load_json_path(public_inputs['qualified_artifact_inputs'],'qualified artifact inputs');validate_schema(schemas,registry,'qualified-artifact-inputs-v10.schema.json',artifact_inputs)
 actual_bindings,aggregate=verify_complete_artifact_bindings(artifact_inputs,receipt['artifact_bindings'],expected_paths)
 if aggregate!=receipt['artifact_bindings_sha256'] or auth['qualified_artifact_bindings_sha256']!=aggregate:raise SystemExit('authorization/receipt complete artifact aggregate mismatch')
 if auth.get('qualification_artifact_set_version')!=QUALIFICATION_ARTIFACT_SET_VERSION or auth.get('qualification_trust_binding_sha256')!=receipt['qualification_trust_binding_sha256']:raise SystemExit('authorization omits v10 artifact-set or trust binding')
 # bootstrap roots were verified before receipt/artifact trust consumption
 if auth['bootstrap_root_manifest_sha256']!=sha(BOOTSTRAP_ROOT_MANIFEST) or auth['authorization_anchor_identity_sha256']!=sha(Path(args.anchor_helper)):raise SystemExit('authorization does not bind pinned host bootstrap/anchor roots')
 expected={'candidate_archive_sha256':sha(public_inputs['candidate_archive']),'bundle_manifest_sha256':manifest_hash,'bundle_root_tree_sha256':tree_hash,'installer_sha256':sha(Path(__file__).resolve()),'installation_manifest_schema_sha256':sha_bytes(bundle.read('repository-overlay/automation/schemas/trusted-installation.schema.json')),'qualification_receipt_sha256':sha(public_inputs['qualification_receipt']),'qualification_receipt_id':receipt['receipt_id'],'governing_policy_source_sha256':sha(Path(args.governing_policy_source)),'revocation_list_sha256':sha(public_inputs['qualification_revocation_list'])}
 for key,value in expected.items():
  if auth.get(key)!=value:raise SystemExit(f'qualification authorization does not bind exact {key}')
 if auth['host_identity']!={'host_id':host['host_id'],'attestation_sha256':host['attestation_sha256'],'measured_boot_policy_sha256':host['measured_boot_policy_sha256'],'os_policy_sha256':host['os_policy_sha256']}:raise SystemExit('qualification authorization host binding mismatch')
 adapter_rows={k:v for k,v in bundle.entries.items() if k.startswith('external-capability-runner/') and ('adapter' in k or k.endswith('capability_runner.py'))};components={'codex_binary':actual_bindings['codex_binary'],'git_binary':actual_bindings['git_binary'],'python_binary':actual_bindings['python_binary'],'container_engine':actual_bindings['container_engine'],'anchor_helper':actual_bindings['anchor_helper'],'mount_binary':sha(target_paths['mount_binary']),'umount_binary':sha(target_paths['umount_binary']),'qualification_verifier':sha_bytes(bundle.read('operator-tools/verify_v10_cleanroom_prerequisites.py')),'qualification_trust_binding':receipt['qualification_trust_binding_sha256'],'process_gate':sha_bytes(bundle.read('trusted-controller/process_gate.py')),'adapter_set':sha_bytes(canonical(adapter_rows)),'validation_image_attestation':actual_bindings['validation_image_attestation'],'registry_proof':actual_bindings['validation_registry_proof'],'key_lifecycle_state':actual_bindings['key_lifecycle_state'],'probe_envelopes_manifest':sha(public_inputs['qualification_probe_envelopes_manifest'])}
 if auth['components']!=components:raise SystemExit('qualification authorization component identity mismatch')
 namespace_hash=sha_bytes(canonical({'pid_namespace_required':execution['pid_namespace_required'],'mount_namespace_required':execution['mount_namespace_required'],'network_namespace_mode':execution['network_namespace_mode']}));agent_expected={'uid':uid,'gid':gid,'groups':execution['supplementary_groups'],'execution_profile_sha256':actual_bindings['agent_execution_profile'],'quota_profile_sha256':actual_bindings['handoff_quota_profile'],'namespace_profile_sha256':execution['namespace_profile_sha256'],'cgroup_profile_sha256':execution['cgroup_profile_sha256'],'mount_profile_sha256':execution['mount_profile_sha256'],'capabilities_sha256':execution['capabilities_sha256'],'acl_profile_sha256':execution['acl_profile_sha256'],'lsm_profile_sha256':execution['lsm_profile_sha256']}
 if auth['agent_profile']!=agent_expected or namespace_hash==('0'*64):raise SystemExit('qualification authorization agent boundary mismatch')
 report_map={'codex_isolation':'codex_isolation_qualification_report','remote_anchor':'remote_anchor_qualification_report','key_custody':'key_custody_qualification_report','installer_fault_matrix':'installer_fault_matrix_report','supply_chain_rebuild':'supply_chain_rebuild_report','dedicated_host_policy':'dedicated_host_policy'}
 if auth['qualification_report_hashes']!={name:actual_bindings[artifact] for name,artifact in report_map.items()}:raise SystemExit('qualification authorization report-set mismatch')
 policy=_v10_policy_preflight(args,schemas,registry,Path(args.approval_keyring),Path(args.governing_policy_source),auth['installation_phase'])
 phase=None
 if args.phase_transition_authorization:
  phase=load_json_path(safe_external(args.phase_transition_authorization,'phase_transition_authorization'),'phase transition authorization');validate_schema(schemas,registry,'qualification-phase-transition-authorization-v10.schema.json',phase);_require_fresh(phase,'phase transition authorization',7)
  phase_keyring=load_json_path(public_inputs['phase_transition_keyring'],'phase transition keyring');validate_schema(schemas,registry,'public-keyring.schema.json',phase_keyring);load_unique_keyring(phase_keyring);verify_roles(phase,phase_keyring,['phase-transition-authorizer','security-approver'])
  if auth['phase_transition_authorization_sha256']!=sha(Path(args.phase_transition_authorization)):raise SystemExit('installation authorization phase-transition hash mismatch')
 elif auth['phase_transition_authorization_sha256'] is not None:raise SystemExit('authorization binds missing phase transition')
 prior_receipt=Path('/etc/azpr/installation-receipts')/f"{phase['prior_installation_id']}.json" if phase else None
 verify_phase_transition(installation_phase=auth['installation_phase'],active_lock_path=ACTIVE_LOCK,authorization=auth,phase_authorization=phase,canonical_policy_record_path=Path(args.canonical_policy_record) if args.canonical_policy_record else None,prior_receipt_path=prior_receipt,qualification_launcher_evidence_path=Path(args.qualification_launcher_evidence) if args.qualification_launcher_evidence else None,fault_matrix_evidence_path=Path(args.phase_fault_matrix_evidence) if args.phase_fault_matrix_evidence else None,load_json=load_json_path)
 return {'bundle':bundle,'schemas':schemas,'registry':registry,'paths':public_inputs,'artifact_paths':expected_paths,'authorization':auth,'authorization_sha256':sha(public_inputs['qualification_authorization']),'receipt':receipt,'artifact_bindings':actual_bindings,'bootstrap':bootstrap,'qualification_trust':authority.trust_binding,'host_qualification_roots':host_context.manifest,'probe_verification':probe_verification,'policy_preflight':policy,'phase_authorization':phase,'phase_authorization_path':str(Path(args.phase_transition_authorization).absolute()) if args.phase_transition_authorization else None,'installation_signing_key_id':args.installation_signing_key_id}

def _reserve_authorization(ctx):
 auth=ctx['authorization'];store=AuthorizationTransactionStore(AUTHORIZATION_LEDGER,args_anchor:=str(ctx['paths']['anchor_helper']) if 'anchor_helper' in ctx['paths'] else str(ctx['artifact_paths']['anchor_helper']),Path(ctx['artifact_paths']['installation_signing_private_key']),ctx['installation_signing_key_id'],f"azpr-v10-1-install-{auth['host_identity']['host_id']}")
 store.recover();reservation=store.reserve(auth,ctx['authorization_sha256']);ctx['authorization_store']=store;ctx['authorization_record']=reservation;ctx['authorization_reservation_head']=store._local_head().as_dict()
 if ctx.get('phase_authorization'):
  phase=ctx['phase_authorization'];phase_doc={'authorization_id':phase['transition_id'],'nonce':phase['nonce'],'sequence':phase['sequence']}
  pstore=AuthorizationTransactionStore(PHASE_AUTHORIZATION_LEDGER,args_anchor,Path(ctx['artifact_paths']['installation_signing_private_key']),ctx['installation_signing_key_id'],f"azpr-v10-1-phase-{auth['host_identity']['host_id']}")
  pstore.recover();pres=pstore.reserve(phase_doc,sha(Path(ctx['phase_authorization_path'])));ctx['phase_authorization_store']=pstore;ctx['phase_authorization_record']=pres;ctx['phase_reservation_head']=pstore._local_head().as_dict()
 return reservation

def _complete_authorization(ctx,status:str,installation_id:str|None=None,failure:str|None=None):
 if ctx.get('authorization_store') and ctx.get('authorization_record'):ctx['authorization_completion_record']=ctx['authorization_store'].complete(ctx['authorization_record'],status,installation_id,failure)
 if ctx.get('phase_authorization_store') and ctx.get('phase_authorization_record'):ctx['phase_completion_record']=ctx['phase_authorization_store'].complete(ctx['phase_authorization_record'],status,installation_id,failure)

def main():
 ap=argparse.ArgumentParser()
 required=[
  'bundle-root','bundle-attestation','bundle-signing-public-key','bundle-signing-key-id','wheelhouse',
  'runtime-private-key','runtime-public-key','approval-keyring','evidence-keyring','anchor-helper',
  'container-engine','codex-binary','governing-policy-source',
  'evidence-private-key','evidence-public-key','installation-signing-private-key',
  'installation-signing-public-key','requirements-input','dependency-lock','dependency-mirror-inventory',
  'dependency-mirror-attestation','dependency-mirror-public-key','sbom','build-provenance',
  'validation-dockerfile','validation-image-attestation','validation-image-digest','agent-uid','agent-gid',
  'candidate-archive','qualification-authorization','qualification-authorization-keyring','qualification-revocation-list',
  'qualification-receipt','host-identity','agent-execution-profile','handoff-quota-profile',
  'qualified-artifact-inputs','qualification-probe-envelopes-manifest','key-lifecycle-state','phase-transition-keyring','validation-registry-proof',
  'codex-isolation-qualification-report','remote-anchor-qualification-report','key-custody-qualification-report',
  'installer-fault-matrix-report','supply-chain-rebuild-report','dedicated-host-policy'
 ]
 for name in required:ap.add_argument('--'+name,required=True)
 for name in ('canonical-policy','canonical-policy-source-manifest','canonical-policy-record','canonical-policy-section-map','phase-transition-authorization','qualification-launcher-evidence','phase-fault-matrix-evidence'):ap.add_argument('--'+name)
 ap.add_argument('--external-runner-config')
 ap.add_argument('--git-binary',default='/usr/bin/git');ap.add_argument('--python-binary',default='/usr/bin/python3')
 ap.add_argument('--mount-binary',default='/usr/bin/mount');ap.add_argument('--umount-binary',default='/usr/bin/umount')
 ap.add_argument('--installation-signing-key-id',default='azpr-installation-authority')
 args=ap.parse_args()
 if os.geteuid()!=0:raise SystemExit('installation must run as root')
 agent_uid=int(args.agent_uid);agent_gid=int(args.agent_gid)
 if agent_uid<=0 or agent_gid<=0:raise SystemExit('agent UID/GID must be explicit non-root values')
 if args.external_runner_config:raise SystemExit('custom production external-runner configuration is forbidden; installer generates manifest-pinned configuration')
 # V10 preserves the v9 invariant: one kernel lock serializes preflight, recovery, reservation, activation, anchoring, and completion.
 global_lock=InstallerGlobalLock(GLOBAL_INSTALLER_LOCK).acquire()
 # Complete exact binding and pinned bootstrap verification precedes authorization reservation.
 qualification=_qualification_preflight(args)
 fault_checkpoint('after_qualification_authorization_verified_before_first_write',AUTHORIZATION_LEDGER)
 # Legacy v8 static-audit token only: _reserve_authorization(qualification). V10 preserves recovery of the anchored transaction while holding the global lock before the real reservation call below.
 recovered=recover_activation_state()
 _reserve_authorization(qualification)
 fault_checkpoint('after_qualification_authorization_reserved',AUTHORIZATION_LEDGER)
 att=qualification['paths']['bundle_attestation'];bundle_key=qualification['paths']['bundle_signing_public_key'];bundle=qualification['bundle']
 staging=final=secure_root=runtime_root=agent_handoff_root=agent_cgroup_root=None
 try:
  schemas,registry=qualification['schemas'],qualification['registry']
  bundle_attestation=load_json_path(att,'bundle attestation');validate_schema(schemas,registry,'bundle-attestation.schema.json',bundle_attestation)
  generic_names=[
   'runtime_public_key','approval_keyring','evidence_keyring','anchor_helper','git_binary','container_engine',
   'codex_binary','python_binary','governing_policy_source','evidence_public_key','installation_signing_public_key',
   'requirements_input','dependency_lock','dependency_mirror_inventory','dependency_mirror_attestation',
   'dependency_mirror_public_key','sbom','build_provenance','validation_dockerfile','validation_image_attestation',
   'agent_execution_profile','handoff_quota_profile','mount_binary','umount_binary'
  ]
  executable={'anchor_helper','git_binary','container_engine','codex_binary','python_binary','mount_binary','umount_binary'}
  external={name:safe_external(getattr(args,name),name,executable=name in executable) for name in generic_names}
  external['runtime_private_key']=safe_secret(args.runtime_private_key,'runtime_private_key',agent_uid=agent_uid,agent_gid=agent_gid)
  external['evidence_private_key']=safe_secret(args.evidence_private_key,'evidence_private_key',agent_uid=agent_uid,agent_gid=agent_gid)
  private_install=safe_secret(args.installation_signing_private_key,'installation_signing_private_key',agent_uid=agent_uid,agent_gid=agent_gid)
  verify_key_pair(external['runtime_private_key'],external['runtime_public_key'],'runtime signing')
  verify_key_pair(external['evidence_private_key'],external['evidence_public_key'],'evidence signing')
  verify_key_pair(private_install,external['installation_signing_public_key'],'installation authority')
  wheelhouse=safe_external_directory(args.wheelhouse,'wheelhouse')
  approval=load_json_path(external['approval_keyring'],'approval keyring');evidence=load_json_path(external['evidence_keyring'],'evidence keyring')
  validate_schema(schemas,registry,'public-keyring.schema.json',approval);validate_schema(schemas,registry,'public-keyring.schema.json',evidence)
  load_unique_keyring(approval);load_unique_keyring(evidence)

  # Legacy audit markers retained: installation_phase='QUALIFICATION_ONLY'; installation_phase='POLICY_ACTIVATED'.
  installation_phase=qualification['authorization']['installation_phase']
  if qualification.get('policy_preflight'):
   for name,path in qualification['policy_preflight']['paths'].items():external[name]=path


  supply_identity=verify_supply_chain(schemas,registry,external,wheelhouse,args.validation_image_digest)
  validate_schema(schemas,registry,'supply-chain-identity.schema.json',supply_identity)
  attestation=load_json_path(external['validation_image_attestation'],'validation image attestation')
  verify_roles(attestation,approval,['build-operator','security-approver'])

  installation_id='azpr-'+os.urandom(16).hex()
  GENERATIONS.parent.mkdir(parents=True,exist_ok=True);os.chown(GENERATIONS.parent,0,0);os.chmod(GENERATIONS.parent,0o755)
  GENERATIONS.mkdir(parents=True,exist_ok=True);os.chown(GENERATIONS,0,0);os.chmod(GENERATIONS,0o755)
  VAR.mkdir(parents=True,exist_ok=True);os.chown(VAR,0,0);os.chmod(VAR,0o700)
  staging=GENERATIONS/f'.staging-{installation_id}';final=GENERATIONS/installation_id
  secure_root=VAR/'secure'/installation_id;runtime_root=VAR/'runtime'/installation_id;agent_handoff_root=AGENT_HANDOFF_BASE/installation_id;agent_cgroup_root=AGENT_CGROUP_BASE/installation_id
  if any(x.exists() for x in (staging,final,secure_root,runtime_root,agent_handoff_root,agent_cgroup_root)):raise SystemExit('installation generation collision')
  staging.mkdir(mode=0o700);secure_root.mkdir(parents=True,mode=0o700);runtime_root.mkdir(parents=True,mode=0o700)
  AGENT_HANDOFF_BASE.mkdir(parents=True,exist_ok=True);os.chown(AGENT_HANDOFF_BASE,0,0);os.chmod(AGENT_HANDOFF_BASE,0o711)
  agent_handoff_root.mkdir(mode=0o711);os.chown(agent_handoff_root,0,0);os.chmod(agent_handoff_root,0o711)
  if not AGENT_CGROUP_BASE.exists():AGENT_CGROUP_BASE.mkdir(mode=0o755)
  if not (AGENT_CGROUP_BASE/'cgroup.controllers').exists() and not (AGENT_CGROUP_BASE.parent/'cgroup.controllers').exists():raise SystemExit('dedicated cgroup v2 root is unavailable')
  agent_cgroup_root.mkdir(mode=0o755);os.chown(agent_cgroup_root,0,0);os.chmod(agent_cgroup_root,0o755)
  for directory in (secure_root,runtime_root):os.chown(directory,0,0);os.chmod(directory,0o700)
  components={}
  try:
   provenance_dir=staging/'provenance';provenance_dir.mkdir(mode=0o700)
   provenance_inputs={
    'bundle_attestation':(read_regular(att),provenance_dir/'bundle-attestation.json',final/'provenance/bundle-attestation.json'),
    'bundle_signing_public_key':(read_regular(bundle_key,64*1024),provenance_dir/'bundle-signing-public-key.pem',final/'provenance/bundle-signing-public-key.pem'),
    'bundle_manifest':(read_regular(bundle.root/'SHA256SUMS.json'),provenance_dir/'SHA256SUMS.json',final/'provenance/SHA256SUMS.json'),
   }
   for name,(raw,staged_path,final_path) in provenance_inputs.items():
    write_once(staged_path,raw,0o444);os.chown(staged_path,0,0);components[name]=staged_component(staged_path,final_path,0o444)
   source_map={
    'controller':('trusted-controller/controller.py','controller/controller.py',0o555),
    'secure_runtime':('trusted-controller/secure_runtime.py','controller/secure_runtime.py',0o444),
    'evidence_registry':('trusted-controller/evidence_registry.py','controller/evidence_registry.py',0o444),
    'trusted_installation':('trusted-controller/trusted_installation.py','controller/trusted_installation.py',0o444),
    'process_gate':('trusted-controller/process_gate.py','controller/process_gate.py',0o555),
    'validation_runner':('trusted-validation-runner/trusted_validation_runner.py','validation/trusted_validation_runner.py',0o555),
    'validation_trusted_installation':('trusted-validation-runner/trusted_installation.py','validation/trusted_installation.py',0o444),
    'external_runner':('external-capability-runner/capability_runner.py','external-runner/capability_runner.py',0o555),
    'external_secure_runtime':('external-capability-runner/secure_runtime.py','external-runner/secure_runtime.py',0o444),
    'external_process_gate':('external-capability-runner/process_gate.py','external-runner/process_gate.py',0o555),
    'external_trusted_installation':('external-capability-runner/trusted_installation.py','external-runner/trusted_installation.py',0o444),
    'cleanroom_adapter':('external-capability-runner/mock_noop_adapter.py','external-runner/mock_noop_adapter.py',0o555)
   }
   for name,(rel,dstrel,mode) in source_map.items():
    copy_bundle(bundle,rel,staging/dstrel,mode);components[name]=staged_component(staging/dstrel,final/dstrel,mode)
   for name,schema in schemas.items():
    rel='repository-overlay/automation/schemas/'+name;copy_bundle(bundle,rel,staging/'schemas'/name,0o444)
    components['schema:'+name]=staged_component(staging/'schemas'/name,final/'schemas'/name,0o444)

   venv=staging/'venv'
   clean_env={'PATH':'/usr/bin:/bin','HOME':'/root','PYTHONNOUSERSITE':'1','PIP_DISABLE_PIP_VERSION_CHECK':'1'}
   subprocess.run([str(external['python_binary']),'-m','venv','--copies',str(venv)],check=True,env=clean_env)
   subprocess.run([str(venv/'bin/pip'),'install','--no-index','--find-links',str(wheelhouse),'--require-hashes','-r',str(external['dependency_lock'])],check=True,env=clean_env)
   subprocess.run([str(venv/'bin/python'),'-c','import cryptography,jsonschema,referencing'],check=True,env=clean_env)
   harden_tree(venv)
   runtime_manifest=runtime_tree_manifest(venv);runtime_manifest['root']=str(final/'venv')
   runtime_manifest_path=staging/'python-runtime-manifest.json';write_once(runtime_manifest_path,(json.dumps(runtime_manifest,indent=2,sort_keys=True)+'\n').encode(),0o444)
   components['python_runtime_manifest']=staged_component(runtime_manifest_path,final/'python-runtime-manifest.json',0o444)
   components['python_binary']=staged_component(venv/'bin/python',final/'venv/bin/python',os.stat(venv/'bin/python').st_mode&0o777)
   components['build_python_binary']=component(external['python_binary'],os.stat(external['python_binary']).st_mode&0o777)

   for name in ('agent_execution_profile','handoff_quota_profile'):
    destination=staging/(name.replace('_','-')+'.json');write_once(destination,read_regular(external[name]),0o444);os.chown(destination,0,0);components[name]=staged_component(destination,final/destination.name,0o444)
   secret_inputs={'runtime_private_key':external['runtime_private_key'],'evidence_private_key':external['evidence_private_key']}
   for name,path in secret_inputs.items():
    destination=secure_root/f'{name}.pem';copy_verified(path,destination,0o400);os.chown(destination,0,0);os.chmod(destination,0o400)
    if {'system.posix_acl_access','system.posix_acl_default'} & set(os.listxattr(destination,follow_symlinks=False)):raise SystemExit(f'installed secret carries an ACL: {name}')
    prove_identity_denied(destination,agent_uid,agent_gid,read=True,label=name);components[name]=component(destination,0o400)
   for name,path in external.items():
    if name in secret_inputs:continue
    components[name]=component(path,os.stat(path).st_mode&0o777)
   supply_path=staging/'supply-chain-identity.json';write_once(supply_path,(json.dumps(supply_identity,indent=2,sort_keys=True)+'\n').encode(),0o444)
   components['supply_chain_identity']=staged_component(supply_path,final/'supply-chain-identity.json',0o444)

   external_runner_runtime=runtime_root/'external-runner';external_runner_runtime.mkdir(mode=0o700);os.chown(external_runner_runtime,0,0);os.chmod(external_runner_runtime,0o700)
   adapter_manifest={'format_version':'1.0','adapter_name':'cleanroom-noop','executable_component':'cleanroom_adapter','executable_sha256':components['cleanroom_adapter']['sha256'],'allowed_operations':['noop'],'execution_mode':'DRY_RUN_ONLY','idempotency_key_required':True,'max_request_bytes':1048576,'max_response_bytes':1048576,'rollback_semantics':'NO_SIDE_EFFECT_NOOP'}
   validate_schema(schemas,registry,'adapter-installation-manifest.schema.json',adapter_manifest)
   adapter_manifest_path=staging/'cleanroom-adapter-manifest.json';write_once(adapter_manifest_path,(json.dumps(adapter_manifest,indent=2,sort_keys=True)+'\n').encode(),0o444)
   components['cleanroom_adapter_manifest']=staged_component(adapter_manifest_path,final/'cleanroom-adapter-manifest.json',0o444)
   config={
    'format_version':'2.0','approval_keyring_component':'approval_keyring',
    'evidence_private_key_component':'evidence_private_key','evidence_public_key_component':'evidence_public_key',
    'evidence_key_id':'azpr-external-evidence','nonce_ledger_directory':'external_runner_runtime',
    'controller_runtime_public_key_component':'runtime_public_key','controller_runtime_key_id':'azpr-controller-runtime',
    'adapters':[{'name':'cleanroom-noop','component':'cleanroom_adapter','manifest_component':'cleanroom_adapter_manifest','sha256':components['cleanroom_adapter']['sha256'],'allowed_operations':['noop']}]
   }
   validate_schema(schemas,registry,'external-runner-config.schema.json',config)
   config_path=staging/'external-runner-config.json';write_once(config_path,(json.dumps(config,indent=2,sort_keys=True)+'\n').encode(),0o444)
   components['external_runner_config']=staged_component(config_path,final/'external-runner-config.json',0o444)

   prove_identity_cannot_traverse(secure_root,agent_uid,agent_gid,'secure key root')
   prove_identity_cannot_traverse(runtime_root,agent_uid,agent_gid,'controller runtime root')
   python_exec=str(final/'venv/bin/python')
   controller_launcher=(f'#!/bin/sh\n'
    'unset AZPR_TRUSTED_GIT AZPR_RUN_SIGNING_PRIVATE_KEY_FILE AZPR_RUN_SIGNING_PUBLIC_KEY_FILE AZPR_RUNTIME_ROOT AZPR_JOURNAL_ANCHOR_COMMAND AZPR_APPROVAL_PUBLIC_KEYRING AZPR_EVIDENCE_PUBLIC_KEYRING AZPR_DEV_INSTALLATION_MANIFEST AZPR_DEV_INSTALLATION_LOCK AZPR_EXPLICIT_TEST_MODE AZPR_TEST_CODEX_BINARY\n'
    'export AZPR_PRODUCTION_MODE=1\n'
    f'exec {python_exec} {final}/controller/controller.py "$@"\n')
   runner_launcher=(f'#!/bin/sh\n'
    'unset AZPR_TRUSTED_GIT AZPR_RUNTIME_ROOT AZPR_JOURNAL_ANCHOR_COMMAND AZPR_DEV_INSTALLATION_MANIFEST AZPR_DEV_INSTALLATION_LOCK AZPR_EXPLICIT_TEST_MODE\n'
    'export AZPR_PRODUCTION_MODE=1\n'
    f'exec {python_exec} {final}/external-runner/capability_runner.py "$@"\n')
   write_once(staging/'azpr-controller',controller_launcher.encode(),0o555);write_once(staging/'azpr-capability-runner',runner_launcher.encode(),0o555)
   components['controller_launcher']=staged_component(staging/'azpr-controller',final/'azpr-controller',0o555)
   components['capability_runner_launcher']=staged_component(staging/'azpr-capability-runner',final/'azpr-capability-runner',0o555)

   private=serialization.load_pem_private_key(read_regular(private_install),password=None)
   if not isinstance(private,Ed25519PrivateKey):raise SystemExit('installation signing private key is not Ed25519')
   directories={
    'runtime_root':{'path':str(runtime_root),'mode':'700'},'external_runner_runtime':{'path':str(external_runner_runtime),'mode':'700'},
    'secure_key_root':{'path':str(secure_root),'mode':'700'},'schema_dir':{'path':str(final/'schemas'),'mode':'555'},
    'agent_handoff_root':{'path':str(agent_handoff_root),'mode':'711'},'agent_cgroup_root':{'path':str(agent_cgroup_root),'mode':'755'}
   }
   manifest=sign(private,{
    'format_version':'2.0','installation_id':installation_id,'installation_phase':installation_phase,'created_at':datetime.now(timezone.utc).isoformat(),'host_id':qualification['authorization']['host_identity']['host_id'],
    'agent_uid':agent_uid,'agent_gid':agent_gid,'qualification_artifact_set_version':QUALIFICATION_ARTIFACT_SET_VERSION,'qualification_trust_binding_sha256':qualification['receipt']['qualification_trust_binding_sha256'],'runtime_signing_key_id':'azpr-controller-runtime',
    'evidence_key_id':'azpr-external-evidence','authorization_journal_id':qualification['authorization_reservation_head']['journal_id'],'authorization_reservation_head_sha256':qualification['authorization_reservation_head']['head_sha256'],'authorization_ledger_sequence':qualification['authorization_reservation_head']['ledger_sequence'],'authorization_sequence':qualification['authorization_reservation_head']['authorization_sequence'],'phase_transition_reservation_head_sha256':qualification.get('phase_reservation_head',{}).get('head_sha256'),'components':components,'directories':directories
   },args.installation_signing_key_id)
   validate_schema(schemas,registry,'trusted-installation.schema.json',manifest)
   manifest_path=staging/'trusted-installation.json';write_once(manifest_path,(json.dumps(manifest,indent=2,sort_keys=True)+'\n').encode(),0o444)
   harden_tree(staging);fsync_dir(staging)

   lock={
    'format_version':'1.0','installation_id':installation_id,'manifest_path':str(final/'trusted-installation.json'),
    'manifest_sha256':sha(staging/'trusted-installation.json'),'authority_public_key_path':str(external['installation_signing_public_key']),
    'authority_public_key_sha256':sha(external['installation_signing_public_key']),'signer_key_id':args.installation_signing_key_id
   }
   lock_bytes=(json.dumps(lock,indent=2,sort_keys=True)+'\n').encode();lock_hash=sha_bytes(lock_bytes)
   final_receipt=sign(private,{
    'format_version':'2.0','installation_id':installation_id,'manifest_sha256':lock['manifest_sha256'],
    'lock_sha256':lock_hash,'controller_launcher_sha256':components['controller_launcher']['sha256'],
    'capability_runner_launcher_sha256':components['capability_runner_launcher']['sha256'],
    'authorization_journal_id':qualification['authorization_reservation_head']['journal_id'],'authorization_reservation_head_sha256':qualification['authorization_reservation_head']['head_sha256'],'authorization_ledger_sequence':qualification['authorization_reservation_head']['ledger_sequence'],'authorization_sequence':qualification['authorization_reservation_head']['authorization_sequence'],'phase_transition_reservation_head_sha256':qualification.get('phase_reservation_head',{}).get('head_sha256'),
    'created_at':datetime.now(timezone.utc).isoformat()
   },args.installation_signing_key_id)
   validate_schema(schemas,registry,'installation-receipt.schema.json',final_receipt)
   ETC.mkdir(parents=True,exist_ok=True);os.chown(ETC,0,0);os.chmod(ETC,0o755)
   RECEIPTS.mkdir(exist_ok=True);os.chown(RECEIPTS,0,0);os.chmod(RECEIPTS,0o755)
   pending=RECEIPTS/f'.{installation_id}.pending.json';receipt_path=RECEIPTS/f'{installation_id}.json'
   if pending.exists() or receipt_path.exists():raise SystemExit('installation receipt collision')
   write_once(pending,(json.dumps(final_receipt,indent=2,sort_keys=True)+'\n').encode(),0o400);os.chown(pending,0,0)
   previous_hash=sha(ACTIVE_LOCK) if ACTIVE_LOCK.exists() else None
   state={
    'format_version':'1.0','installation_id':installation_id,'previous_lock_sha256':previous_hash,
    'new_lock_sha256':lock_hash,'staging_path':str(staging),'generation_path':str(final),
    'secure_path':str(secure_root),'runtime_path':str(runtime_root),'agent_handoff_path':str(agent_handoff_root),'agent_cgroup_path':str(agent_cgroup_root),
    'pending_receipt_path':str(pending),'final_receipt_path':str(receipt_path),
    'created_at':datetime.now(timezone.utc).isoformat()
   }
   atomic_write_json(ACTIVATION_STATE,state,0o600)
   fault_checkpoint('before_generation_activation_rename',final);os.replace(staging,final);fault_checkpoint('after_generation_activation_rename',final);fsync_dir(GENERATIONS)
   fault_checkpoint('before_active_lock_activation',ACTIVE_LOCK);atomic_activate(lock);fault_checkpoint('after_active_lock_activation',ACTIVE_LOCK)
   fault_checkpoint('before_receipt_recovery',receipt_path);recovery_result=recover_activation_state();fault_checkpoint('after_receipt_recovery',receipt_path)
   _complete_authorization(qualification,'CONSUMED',installation_id=installation_id)
   print(json.dumps({'prior_recovery':recovered,'activation_recovery':recovery_result,'installation_receipt':final_receipt,'receipt_path':str(receipt_path),'qualification_authorization_id':qualification['authorization']['authorization_id']},indent=2))
  except BaseException as installation_error:
   try:_complete_authorization(qualification,'FAILED_CONSUMED',failure=repr(installation_error))
   except BaseException:pass
   if ACTIVATION_STATE.exists():recover_activation_state()
   else:
    for directory in (staging,final,secure_root,runtime_root,agent_handoff_root):
     if isinstance(directory,Path) and directory.exists():shutil.rmtree(directory,ignore_errors=True)
    if isinstance(agent_cgroup_root,Path) and agent_cgroup_root.exists():
     try:_remove_empty_cgroup(agent_cgroup_root)
     except BaseException:pass
   raise
 finally:
  bundle.close();global_lock.release()
if __name__=='__main__':main()
