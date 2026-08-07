#!/usr/bin/env python3
"""Pinned AZPR installation trust-root loader.

Production mode uses fixed root-owned paths only. Caller-provided paths and
security-key environment variables are ignored. Development/test overrides are
accepted only when AZPR_PRODUCTION_MODE is not enabled.
"""
from __future__ import annotations
import hashlib, json, os, stat, base64
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature

PRODUCTION_LOCK = Path('/etc/azpr/trusted-installation.lock.json')
MAX_MANIFEST_BYTES = 1024 * 1024
REQUIRED_PRODUCTION_COMPONENTS = {
    'anchor_helper',
    'approval_keyring',
    'build_provenance',
    'build_python_binary',
    'bundle_attestation',
    'bundle_manifest',
    'bundle_signing_public_key',
    'capability_runner_launcher',
    'cleanroom_adapter',
    'codex_binary',
    'container_engine',
    'controller',
    'controller_launcher',
    'dependency_lock',
    'dependency_mirror_attestation',
    'dependency_mirror_inventory',
    'dependency_mirror_public_key',
    'evidence_keyring',
    'evidence_private_key',
    'evidence_public_key',
    'evidence_registry',
    'external_runner',
    'external_runner_config',
    'external_secure_runtime',
    'external_trusted_installation',
    'git_binary',
    'governing_policy_source',
    'installation_signing_public_key',
    'python_binary',
    'requirements_input',
    'python_runtime_manifest',
    'runtime_private_key',
    'runtime_public_key',
    'sbom',
    'supply_chain_identity',
    'secure_runtime',
    'trusted_installation',
    'validation_dockerfile',
    'validation_image_attestation',
    'validation_runner',
    'validation_trusted_installation',
    'process_gate',
    'external_process_gate',
    'agent_execution_profile',
    'handoff_quota_profile',
    'mount_binary',
    'umount_binary',
}

class InstallationError(RuntimeError): pass

def production_mode() -> bool:
    return os.environ.get('AZPR_PRODUCTION_MODE') == '1'

def _sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for c in iter(lambda:f.read(1024*1024), b''): h.update(c)
    return h.hexdigest()

def _safe_regular(path: Path, *, root_owned: bool) -> os.stat_result:
    cur=path.absolute()
    for p in [cur,*cur.parents]:
        st=os.lstat(p)
        if stat.S_ISLNK(st.st_mode): raise InstallationError(f'symlinked trusted path: {p}')
        if st.st_mode & 0o022: raise InstallationError(f'writable trusted path: {p}')
        if root_owned and st.st_uid != 0: raise InstallationError(f'production trusted path is not root-owned: {p}')
        if p == p.parent: break
    st=os.stat(cur)
    if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
        raise InstallationError(f'trusted file must be a single-link regular file: {cur}')
    return st

def _read_bytes_once(path: Path, *, root_owned: bool, limit: int = MAX_MANIFEST_BYTES) -> bytes:
    before=_safe_regular(path, root_owned=root_owned)
    if before.st_size > limit: raise InstallationError('trusted file exceeds size limit')
    flags=os.O_RDONLY|getattr(os,'O_NOFOLLOW',0); fd=os.open(path,flags)
    try:
        opened=os.fstat(fd)
        if (before.st_dev,before.st_ino)!=(opened.st_dev,opened.st_ino): raise InstallationError('trusted file identity changed before open')
        data=bytearray()
        while True:
            chunk=os.read(fd,65536)
            if not chunk: break
            data.extend(chunk)
            if len(data)>limit: raise InstallationError('trusted file exceeds size limit')
        after=os.fstat(fd)
        if (opened.st_dev,opened.st_ino,opened.st_size,opened.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns):
            raise InstallationError('trusted file changed during read')
        current=os.lstat(path)
        if stat.S_ISLNK(current.st_mode) or (current.st_dev,current.st_ino)!=(after.st_dev,after.st_ino):
            raise InstallationError('trusted file pathname changed during read')
        return bytes(data)
    finally: os.close(fd)

def _read_json(path: Path, *, root_owned: bool) -> dict[str,Any]:
    try: value=json.loads(_read_bytes_once(path,root_owned=root_owned).decode('utf-8'))
    except InstallationError: raise
    except Exception as exc: raise InstallationError(f'invalid installation JSON: {path}') from exc
    if not isinstance(value,dict): raise InstallationError('installation JSON must be an object')
    return value

@dataclass(frozen=True)
class TrustedInstallation:
    manifest_path: Path
    manifest_sha256: str
    data: dict[str,Any]
    production: bool
    def component(self,name:str)->Path:
        item=self.data.get('components',{}).get(name)
        if not isinstance(item,dict) or not isinstance(item.get('path'),str):
            raise InstallationError(f'missing installed component: {name}')
        path=Path(item['path']).absolute()
        st=_safe_regular(path,root_owned=self.production)
        expected=item.get('sha256')
        if not isinstance(expected,str) or _sha256(path)!=expected:
            raise InstallationError(f'installed component hash mismatch: {name}')
        expected_mode=item.get('mode')
        if isinstance(expected_mode,str) and (st.st_mode & 0o777) != int(expected_mode,8):
            raise InstallationError(f'installed component mode mismatch: {name}')
        return path
    def directory(self,name:str)->Path:
        item=self.data.get('directories',{}).get(name)
        if not isinstance(item,dict) or not isinstance(item.get('path'),str):
            raise InstallationError(f'missing installed directory: {name}')
        path=Path(item['path']).absolute(); st=os.lstat(path)
        if stat.S_ISLNK(st.st_mode) or not stat.S_ISDIR(st.st_mode): raise InstallationError(f'unsafe installed directory: {name}')
        if st.st_mode & 0o022: raise InstallationError(f'writable installed directory: {name}')
        if self.production and st.st_uid != 0 and name != 'runtime_root': raise InstallationError(f'installed directory is not root-owned: {name}')
        return path
    def agent_identity(self)->tuple[int,int]:
        uid=self.data.get('agent_uid');gid=self.data.get('agent_gid')
        if not isinstance(uid,int) or not isinstance(gid,int) or uid<=0 or gid<=0:
            raise InstallationError('installed agent identity must be explicit non-root UID/GID')
        return uid,gid
    def verify_agent_isolation(self)->None:
        # Exact UID/GID open denial is performed by the single-threaded root installer.
        # Runtime rechecks immutable metadata and rejects ACL-based permission drift.
        if not self.production:return
        for name in ('runtime_private_key','evidence_private_key'):
            path=self.component(name); st=os.stat(path); mode=st.st_mode&0o777
            if st.st_uid!=0 or st.st_gid!=0 or mode not in (0o400,0o600):
                raise InstallationError(f'private key metadata is not secret-only: {name}')
            try:acl_names=set(os.listxattr(path,follow_symlinks=False))
            except (AttributeError,OSError):acl_names=set()
            if {'system.posix_acl_access','system.posix_acl_default'} & acl_names:
                raise InstallationError(f'private key has an unexpected POSIX ACL: {name}')
        for name in ('secure_key_root','runtime_root'):
            path=self.directory(name);st=os.stat(path)
            if st.st_uid!=0 or st.st_gid!=0 or (st.st_mode&0o777)!=0o700:
                raise InstallationError(f'controller directory metadata drift: {name}')
        handoff=self.directory('agent_handoff_root');st=os.stat(handoff)
        if st.st_uid!=0 or st.st_gid!=0 or (st.st_mode&0o777)!=0o711:
            raise InstallationError('agent handoff root metadata drift')
    def identity_hashes(self)->dict[str,str]:
        out={'installation_manifest':self.manifest_sha256}
        for name,item in sorted(self.data.get('components',{}).items()):
            if isinstance(item,dict) and isinstance(item.get('sha256'),str): out[f'installation:{name}']=item['sha256']
        return out
    def verify_python_runtime(self)->None:
        manifest_path=self.component('python_runtime_manifest')
        value=_read_json(manifest_path,root_owned=self.production)
        root_value=value.get('root'); files=value.get('files'); expected_tree=value.get('tree_sha256')
        if not isinstance(root_value,str) or not isinstance(files,list) or not files or len(files)>50000 or not isinstance(expected_tree,str):
            raise InstallationError('invalid Python runtime manifest')
        root=Path(root_value).absolute(); st=os.lstat(root)
        if stat.S_ISLNK(st.st_mode) or not stat.S_ISDIR(st.st_mode) or st.st_mode&0o022 or (self.production and st.st_uid!=0):
            raise InstallationError('unsafe trusted Python runtime root')
        canonical=[]
        for item in files:
            if not isinstance(item,dict) or set(item)!={'path','sha256','mode'}:raise InstallationError('invalid Python runtime manifest entry')
            rel=item.get('path')
            if not isinstance(rel,str) or not rel or rel.startswith('/') or '..' in Path(rel).parts:raise InstallationError('unsafe Python runtime manifest path')
            path=root/rel; info=_safe_regular(path,root_owned=self.production)
            if _sha256(path)!=item.get('sha256') or format(info.st_mode&0o777,'o')!=item.get('mode'):raise InstallationError(f'Python runtime file mismatch: {rel}')
            canonical.append(item)
        tree=hashlib.sha256(json.dumps(canonical,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
        if tree!=expected_tree:raise InstallationError('Python runtime tree hash mismatch')

def load_installation() -> TrustedInstallation:
    prod=production_mode()
    if prod:
        lock_path=PRODUCTION_LOCK
        lock=_read_json(lock_path,root_owned=True)
        manifest_value=lock.get('manifest_path')
        if not isinstance(manifest_value,str) or not manifest_value.startswith('/opt/azpr/generations/'):
            raise InstallationError('production lock does not select a versioned installation manifest')
        manifest_path=Path(manifest_value).absolute()
    else:
        manifest_path=Path(os.environ.get('AZPR_DEV_INSTALLATION_MANIFEST','/nonexistent/azpr-development-manifest.json')).absolute()
        lock_path=Path(os.environ.get('AZPR_DEV_INSTALLATION_LOCK','/nonexistent/azpr-development-lock.json')).absolute()
        lock=_read_json(lock_path,root_owned=False)
    manifest=_read_json(manifest_path,root_owned=prod)
    actual=_sha256(manifest_path)
    if lock.get('manifest_path') != str(manifest_path) or lock.get('manifest_sha256') != actual:
        raise InstallationError('installation lock does not pin the active manifest')
    if manifest.get('format_version') not in {'1.0','2.0'} or manifest.get('installation_id') != lock.get('installation_id'):
        raise InstallationError('installation identity mismatch')
    components=manifest.get('components')
    if not isinstance(components,dict):raise InstallationError('installation components are missing')
    phase=manifest.get('installation_phase')
    if phase not in {'QUALIFICATION_ONLY','POLICY_ACTIVATED'}:raise InstallationError('installation phase is invalid')
    if prod:
        if manifest.get('format_version')!='2.0':raise InstallationError('production requires v9 transaction-bound installation manifest')
        for field in ('authorization_journal_id','authorization_reservation_head_sha256','authorization_ledger_sequence','authorization_sequence','phase_transition_reservation_head_sha256'):
            if field not in manifest:raise InstallationError(f'production installation lacks v9 authorization binding: {field}')
        missing=sorted(REQUIRED_PRODUCTION_COMPONENTS-set(components))
        if missing:raise InstallationError(f'production installation is incomplete: {missing}')
        if phase!='POLICY_ACTIVATED':raise InstallationError('trusted controller/external execution is blocked until an independently approved canonical policy is activated')
        policy_required={'canonical_policy','canonical_policy_record','canonical_policy_section_map','canonical_policy_source_manifest'}
        missing_policy=sorted(policy_required-set(components))
        if missing_policy:raise InstallationError(f'policy-activated installation is incomplete: {missing_policy}')
    authority_path=Path(str(lock.get('authority_public_key_path',''))).absolute()
    if not authority_path.is_file() or _sha256(authority_path)!=lock.get('authority_public_key_sha256'):
        raise InstallationError('installation authority key is not pinned by the lock')
    _safe_regular(authority_path,root_owned=prod)
    signature=manifest.get('signature'); key_id=manifest.get('signer_key_id')
    if not isinstance(signature,str) or key_id!=lock.get('signer_key_id'):
        raise InstallationError('installation manifest signature metadata mismatch')
    unsigned=dict(manifest); unsigned.pop('signature',None)
    try:
        key=serialization.load_pem_public_key(_read_bytes_once(authority_path,root_owned=prod,limit=64*1024))
        if not isinstance(key,Ed25519PublicKey): raise InstallationError('installation authority key is not Ed25519')
        key.verify(base64.b64decode(signature,validate=True),json.dumps(unsigned,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode())
    except (InvalidSignature,ValueError,TypeError) as exc:
        raise InstallationError('installation manifest signature verification failed') from exc
    installation=TrustedInstallation(manifest_path,actual,manifest,prod)
    if prod:
        installation.verify_python_runtime(); installation.verify_agent_isolation()
    return installation
