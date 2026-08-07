#!/usr/bin/env python3
"""Trusted AZPR operation registration and atomic immutable evidence ingestion.

The operation registration, evidence index, and lifecycle event are committed in
one authoritative signed SQLite store. Content-addressed objects are written
before the transaction and are safely reusable after interruption when bytes
match the expected digest.
"""
from __future__ import annotations
import json, os, sqlite3, stat
from pathlib import Path
from typing import Any, Iterable
import secure_runtime as sr

MAX_EVIDENCE_BYTES=2*1024*1024
MAX_REGISTRATION_BYTES=512*1024
class EvidenceError(sr.SecurityError): pass

def _read_bytes_once(path:Path,limit:int,label:str)->bytes:
    sr.no_symlink_ancestors(path,allow_missing_leaf=False)
    flags=os.O_RDONLY|getattr(os,'O_NOFOLLOW',0); fd=os.open(path,flags)
    try:
        before=os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or before.st_size>limit: raise EvidenceError(f'{label} is unsafe or too large')
        chunks=[]; total=0
        while True:
            chunk=os.read(fd,min(65536,limit-total+1))
            if not chunk:break
            chunks.append(chunk); total+=len(chunk)
            if total>limit: raise EvidenceError(f'{label} exceeds size limit')
        after=os.fstat(fd)
        if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns): raise EvidenceError(f'{label} changed during read')
        current=os.lstat(path)
        if stat.S_ISLNK(current.st_mode) or (current.st_dev,current.st_ino)!=(after.st_dev,after.st_ino): raise EvidenceError(f'{label} pathname changed during read')
        return b''.join(chunks)
    finally:os.close(fd)

def _read_json_once(path:Path,limit:int,label:str)->dict[str,Any]:
    try:value=json.loads(_read_bytes_once(path,limit,label).decode('utf-8'))
    except EvidenceError:raise
    except Exception as exc:raise EvidenceError(f'{label} is invalid JSON') from exc
    if not isinstance(value,dict):raise EvidenceError(f'{label} must be a JSON object')
    return value

def _target_hash(value:Any)->str:return sr.sha256_bytes(sr.canonical_json_bytes(value))

def _write_or_verify_object(path:Path,data:bytes)->None:
    try:sr.secure_write_bytes(path,data,create_once=True)
    except FileExistsError:
        existing=_read_bytes_once(path,MAX_EVIDENCE_BYTES+1,'existing evidence object')
        if existing!=data:raise EvidenceError('content-addressed evidence object collision')

class OperationRegistry:
    """One authoritative transactional operation/evidence lifecycle registry."""
    def __init__(self,root:Path,*,schema_path:Path,journal_private_key:Path|None,journal_public_key:Path,journal_key_id:str):
        self.root=root; sr.secure_mkdir(root); self.schema_path=schema_path
        self.store=sr.DurableEventStore(root/'operation-events.sqlite3',private_key=journal_private_key,public_key=journal_public_key,key_id=journal_key_id,store_id='operation-evidence-registry')
        self.db=self.store.path
        c=self.store._connect()
        try:
            c.execute("CREATE TABLE IF NOT EXISTS operation_registration(registration_id TEXT PRIMARY KEY,nonce TEXT NOT NULL UNIQUE,document_json TEXT NOT NULL,status TEXT NOT NULL CHECK(status IN ('REGISTERED','EVIDENCE_ATTACHED','EXPIRED','CANCELLED')),evidence_id TEXT UNIQUE)")
            c.execute('CREATE TABLE IF NOT EXISTS evidence(evidence_id TEXT PRIMARY KEY,registration_id TEXT NOT NULL UNIQUE,content_sha256 TEXT NOT NULL UNIQUE,envelope_json TEXT NOT NULL,FOREIGN KEY(registration_id) REFERENCES operation_registration(registration_id))')
        finally:c.close()
    def register(self,document:dict[str,Any],*,run_id:str)->dict[str,Any]:
        sr.validate_json(document,self.schema_path,label='operation registration')
        rid=str(document['registration_id']);nonce=str(document['capability_nonce']);raw=json.dumps(document,sort_keys=True,separators=(',',':'))
        def insert(c):
            try:c.execute("INSERT INTO operation_registration(registration_id,nonce,document_json,status,evidence_id) VALUES(?,?,?,'REGISTERED',NULL)",(rid,nonce,raw))
            except sqlite3.IntegrityError as exc:raise EvidenceError('operation registration ID or nonce already exists') from exc
        record=self.store.append_with('OPERATION_REGISTERED',{'registration_id':rid,'capability_nonce':nonce,'document_sha256':sr.sha256_bytes(raw.encode())},run_id=run_id,transaction_callback=insert)
        return {'registration_id':rid,'capability_nonce':nonce,'document_sha256':sr.sha256_bytes(raw.encode()),'registry_sequence':record['sequence']}
    def get(self,registration_id:str)->dict[str,Any]:
        self.store.recover();c=self.store._connect()
        try:row=c.execute('SELECT document_json,status,evidence_id FROM operation_registration WHERE registration_id=?',(registration_id,)).fetchone()
        finally:c.close()
        if row is None:raise EvidenceError('operation registration is absent')
        doc=json.loads(row[0]);doc['_registry_status']=row[1];doc['_evidence_id']=row[2];return doc
    def registrations(self)->list[dict[str,Any]]:
        self.store.recover();c=self.store._connect()
        try:rows=c.execute('SELECT document_json,status,evidence_id FROM operation_registration ORDER BY registration_id').fetchall()
        finally:c.close()
        out=[]
        for raw,status,evidence_id in rows:
            doc=json.loads(raw);doc['_registry_status']=status;doc['_evidence_id']=evidence_id;out.append(doc)
        return out
    def existing_evidence(self,registration_id:str)->dict[str,Any]|None:
        self.store.recover();c=self.store._connect()
        try:row=c.execute('SELECT envelope_json FROM evidence WHERE registration_id=?',(registration_id,)).fetchone()
        finally:c.close()
        return json.loads(row[0]) if row else None
    def attach_evidence_atomic(self,registration_id:str,envelope:dict[str,Any],*,run_id:str)->dict[str,Any]:
        evidence_id=str(envelope['evidence_id']);content_sha256=str(envelope['content_sha256']);raw=json.dumps(envelope,sort_keys=True,separators=(',',':'))
        def update(c):
            row=c.execute('SELECT status,evidence_id FROM operation_registration WHERE registration_id=?',(registration_id,)).fetchone()
            if row is None:raise EvidenceError('operation registration is absent')
            if row[0]=='EVIDENCE_ATTACHED':
                existing=c.execute('SELECT envelope_json FROM evidence WHERE registration_id=?',(registration_id,)).fetchone()
                if existing and json.loads(existing[0])==envelope:return
                raise EvidenceError('operation already has different evidence')
            if row[0]!='REGISTERED':raise EvidenceError('operation is not open')
            try:
                c.execute('INSERT INTO evidence(evidence_id,registration_id,content_sha256,envelope_json) VALUES(?,?,?,?)',(evidence_id,registration_id,content_sha256,raw))
                c.execute("UPDATE operation_registration SET status='EVIDENCE_ATTACHED',evidence_id=? WHERE registration_id=? AND status='REGISTERED'",(evidence_id,registration_id))
                if c.execute('SELECT changes()').fetchone()[0]!=1:raise EvidenceError('operation attachment lost a concurrent race')
            except sqlite3.IntegrityError as exc:raise EvidenceError('evidence replay or collision') from exc
        return self.store.append_with('OPERATION_EVIDENCE_ATTACHED',envelope,run_id=run_id,transaction_callback=update)
    def evidence_envelopes(self,evidence_ids:Iterable[str])->list[dict[str,Any]]:
        self.store.recover();c=self.store._connect();found={}
        try:
            for eid in evidence_ids:
                row=c.execute('SELECT envelope_json FROM evidence WHERE evidence_id=?',(eid,)).fetchone()
                if row:found[eid]=json.loads(row[0])
        finally:c.close()
        missing=[x for x in evidence_ids if x not in found]
        if missing:raise EvidenceError(f'required verified evidence IDs are missing: {missing}')
        return [found[x] for x in evidence_ids]

class EvidenceRegistry:
    def __init__(self,root:Path,*,schema_path:Path,keyring_path:Path,journal_private_key:Path|None,journal_public_key:Path,journal_key_id:str,operation_registry:OperationRegistry|None=None):
        if operation_registry is None:raise EvidenceError('an authoritative operation registry is mandatory')
        self.root=root;self.objects=root/'objects';self.schema_path=schema_path;self.keyring_path=keyring_path;self.operation_registry=operation_registry
        sr.secure_mkdir(self.objects);self.store=operation_registry.store;self.journal=self.store
    def _verify_signature(self,payload,required_roles):
        key_id=payload.get('signer_key_id');signature=payload.get('signature');keyring=sr.load_public_keyring(self.keyring_path);record=keyring.get(key_id) if isinstance(key_id,str) else None
        if record is None or not isinstance(signature,str):raise EvidenceError('evidence signer is not trusted')
        unsigned=dict(payload);unsigned.pop('signature',None)
        if not sr.ed25519_verify(record.public_key,unsigned,signature):raise EvidenceError('evidence signature verification failed')
        if not set(required_roles).issubset(record.roles):raise EvidenceError('evidence signer lacks required role')
        return record
    def ingest(self,path:Path,*,expected:dict[str,str]|None=None,required_roles:Iterable[str],registered_nonces:set[str]|None=None,run_id:str,registration_id:str|None=None)->dict[str,Any]:
        payload=_read_json_once(path,MAX_EVIDENCE_BYTES,'evidence input');sr.validate_json(payload,self.schema_path,label='external evidence');signer=self._verify_signature(payload,required_roles)
        rid=registration_id or payload.get('operation_registration_id')
        if not isinstance(rid,str):raise EvidenceError('trusted operation registration is required')
        reg=self.operation_registry.get(rid)
        bindings={'operation_registration_id':rid,'stage_id':reg['stage_id'],'evidence_for_stage_id':reg['evidence_for_stage_id'],'environment':reg['environment'],'repository_id':reg['repository_id'],'source_commit':reg['source_commit'],'source_tree':reg['source_tree'],'plan_sha256':reg['plan_sha256'],'capability_manifest_sha256':reg['capability_manifest_sha256'],'target_attestation_sha256':reg['target_attestation_sha256'],'target_sha256':reg['target_sha256'],'operations_sha256':reg['operations_sha256'],'capability_nonce':reg['capability_nonce'],'controller_policy_identity_sha256':reg['controller_policy_identity_sha256']}
        for field,value in bindings.items():
            if payload.get(field)!=value:raise EvidenceError(f'evidence {field} is not bound to the registered operation')
        now=sr.parse_utc(sr.utc_now(),'now');expires=sr.parse_utc(reg['expires_at'],'registration.expires_at');completed=sr.parse_utc(payload['completed_at'],'evidence.completed_at')
        if expires<=now or completed>expires:raise EvidenceError('evidence or registration is stale')
        if _target_hash(payload.get('target'))!=payload.get('target_sha256'):raise EvidenceError('evidence target content does not match target_sha256')
        if payload.get('overall_status')!='APPLY_COMPLETE':raise EvidenceError('only completed apply evidence can satisfy an audit')
        if any(isinstance(x,dict) and x.get('status') in {'FAILED','ROLLED_BACK'} for x in payload.get('adapter_results',[])):raise EvidenceError('failed or rolled-back evidence cannot satisfy an audit')
        canonical=sr.canonical_json_bytes(payload);content_hash=sr.sha256_bytes(canonical)
        envelope={'evidence_id':payload['evidence_id'],'content_sha256':content_hash,'operation_registration_id':rid,'stage_id':payload['stage_id'],'environment':payload['environment'],'source_commit':payload['source_commit'],'source_tree':payload['source_tree'],'overall_status':payload['overall_status'],'plan_sha256':payload['plan_sha256'],'capability_manifest_sha256':payload['capability_manifest_sha256'],'target_attestation_sha256':payload['target_attestation_sha256'],'target_sha256':payload['target_sha256'],'operations_sha256':payload['operations_sha256'],'capability_nonce_sha256':sr.sha256_bytes(payload['capability_nonce'].encode()),'completed_at':payload['completed_at'],'signer_id':signer.signer_id}
        if reg.get('_registry_status')=='EVIDENCE_ATTACHED':
            existing=self.operation_registry.existing_evidence(rid)
            if existing==envelope:return dict(existing,registry_sequence=self.store.head()['sequence'],idempotent_recovery=True)
            raise EvidenceError('operation already has different evidence')
        if reg.get('_registry_status')!='REGISTERED':raise EvidenceError('operation registration is not open')
        _write_or_verify_object(self.objects/f'{content_hash}.json',canonical+b'\n')
        record=self.operation_registry.attach_evidence_atomic(rid,envelope,run_id=run_id)
        return dict(envelope,registry_sequence=record['sequence'])
    def envelopes(self,evidence_ids:Iterable[str])->list[dict[str,Any]]:
        return self.operation_registry.evidence_envelopes(evidence_ids)
