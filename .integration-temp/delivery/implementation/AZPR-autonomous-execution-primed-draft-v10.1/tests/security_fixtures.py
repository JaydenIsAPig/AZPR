from __future__ import annotations
import base64, json, os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def keypair(directory: Path, name: str):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    private=Ed25519PrivateKey.generate(); priv=directory/f'{name}.private.pem'; pub=directory/f'{name}.public.pem'
    priv.write_bytes(private.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
    pub.write_bytes(private.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo))
    os.chmod(priv,0o600); os.chmod(pub,0o644); return priv,pub,private


def signed_multi(sr, payload: dict[str,Any], key_id: str, private) -> dict[str,Any]:
    value=json.loads(json.dumps(payload)); value.setdefault('signatures',[])
    unsigned=sr.unsigned_document(value)
    value['signatures'].append({'key_id':key_id,'ed25519':base64.b64encode(private.sign(sr.canonical_json_bytes(unsigned))).decode('ascii')})
    return value


def decision() -> dict[str,Any]:
    return {'account_id':'acct','project_id':'proj','region':'us-west','resources':['service/api'],'database_targets':[],
      'network_destinations':[],'recipient_cohort':{'cohort_id':None,'recipient_count':0,'recipient_hash':None},
      'limits':{'cost_ceiling_usd':0,'rate_per_minute':0,'max_operations':1},
      'activation_window':{'starts_at':None,'ends_at':None},
      'backup_rollback':{'backup_id':'b1','rollback_plan_sha256':'1'*64,'kill_switch':'disable'},'evidence_outputs':['evidence.json']}


def external_documents(sr, *, adapter_hash: str, op_key, sec_key, att_key, runtime_private_path: Path, runtime_key_id: str='runtime', operation_status: str='APPLIED'):
    now=datetime.now(timezone.utc); target={'account_id':'acct','project_id':'proj','region':'us-west','resources':['service/api']}
    action={'adapter':'mock','operation':'noop','parameters':{'value':1}}
    target_hash=sr.sha256_bytes(sr.canonical_json_bytes(target)); operations_hash=sr.sha256_bytes(sr.canonical_json_bytes([action]))
    plan={'format_version':'1.0','plan_id':'plan-12345','stage_id':'033','created_from_commit':'a'*40,'created_from_tree':'b'*40,
      'repository_id':'azpr-test-repository','environment':'staging','target':target,'target_sha256':target_hash,'operations_sha256':operations_hash,
      'actions':[action],'constraints':decision(),'rollback':{'precondition':'failure','steps':['disable'],'success_criteria':['disabled']},'evidence_requirements':['signed apply evidence']}
    drift='d'*64
    att={'format_version':'1.0','attestation_id':'attest-123','observed_at':now.isoformat(),'expires_at':(now+timedelta(minutes=10)).isoformat(),
      'target':target,'drift_sha256':drift,'adapter_hashes':{'mock':adapter_hash},'signatures':[]}
    att=signed_multi(sr,att,'att',att_key); att_hash=sr.sha256_bytes(sr.canonical_json_bytes(att)); plan_hash=sr.sha256_bytes(sr.canonical_json_bytes(plan))
    rid='opreg-'+'c'*40; nonce='n'*24; policy='e'*64
    manifest={'format_version':'1.0','manifest_id':'manifest-123','operation_registration_id':rid,'stage_id':'033',
      'source_commit':'a'*40,'source_tree':'b'*40,'controller_policy_identity_sha256':policy,
      'plan_sha256':plan_hash,'target_attestation_sha256':att_hash,'environment':'staging','target':target,'target_sha256':target_hash,
      'operations_sha256':operations_hash,'actions':[{'adapter':'mock','operation':'noop','parameters_sha256':sr.sha256_bytes(sr.canonical_json_bytes({'value':1}))}],
      'constraints':decision(),'nonce':nonce,'issued_at':(now-timedelta(minutes=1)).isoformat(),'expires_at':(now+timedelta(minutes=10)).isoformat(),'signatures':[]}
    manifest=signed_multi(sr,manifest,'op',op_key); manifest=signed_multi(sr,manifest,'sec',sec_key); manifest_hash=sr.sha256_bytes(sr.canonical_json_bytes(manifest))
    ticket={'format_version':'1.0','registration_id':rid,'stage_id':'033','evidence_for_stage_id':'034','environment':'staging',
      'repository_id':'azpr-test-repository','source_commit':'a'*40,'source_tree':'b'*40,'plan_sha256':plan_hash,
      'capability_manifest_sha256':manifest_hash,'target_attestation_sha256':att_hash,'target_sha256':target_hash,
      'operations_sha256':operations_hash,'capability_nonce':nonce,'issued_at':now.isoformat(),'expires_at':(now+timedelta(minutes=10)).isoformat(),
      'expected_evidence_role':'external-evidence','controller_policy_identity_sha256':policy}
    ticket=sr.sign_manifest(ticket,private_key_path=runtime_private_path,key_id=runtime_key_id)
    return {'now':now,'target':target,'drift':drift,'plan':plan,'attestation':att,'manifest':manifest,'ticket':ticket,'operation_status':operation_status}


def write_external_fixture(sr, pack: Path, root: Path, *, apply_status='APPLIED') -> dict[str,Any]:
    op_priv,op_pub,op_key=keypair(root,'op'); sec_priv,sec_pub,sec_key=keypair(root,'sec'); att_priv,att_pub,att_key=keypair(root,'att')
    evidence_priv,evidence_pub,_=keypair(root,'evidence'); runtime_priv,runtime_pub,_=keypair(root,'runtime')
    keyring={'format_version':'1.0','keys':[
      {'key_id':'op','signer_id':'alice','roles':['operator'],'public_key_pem':op_pub.read_text()},
      {'key_id':'sec','signer_id':'bob','roles':['security-approver'],'public_key_pem':sec_pub.read_text()},
      {'key_id':'att','signer_id':'carol','roles':['target-attestor'],'public_key_pem':att_pub.read_text()}]}
    keyring_path=root/'keyring.json'; keyring_path.write_text(json.dumps(keyring)); os.chmod(keyring_path,0o600)
    adapter=root/'mock_adapter.py'; drift='d'*64
    adapter.write_text('#!/usr/bin/env python3\nimport json,sys\nmode=sys.argv[1]; p=json.load(sys.stdin)\n'
      f'\nif mode=="probe": print(json.dumps({{"target":p["target"],"drift_sha256":"{drift}","safe_to_apply":True}}))\n'
      f'elif mode=="apply": print(json.dumps({{"status":"{apply_status}","operation":p["operation"]}}))\n'
      'else: print(json.dumps({"status":"ROLLED_BACK","operation":p["operation"]}))\n')
    os.chmod(adapter,0o755); adapter_hash=sr.sha256_file(adapter)
    docs=external_documents(sr,adapter_hash=adapter_hash,op_key=op_key,sec_key=sec_key,att_key=att_key,runtime_private_path=runtime_priv)
    config={'format_version':'1.0','approval_keyring_path':str(keyring_path),'evidence_private_key_path':str(evidence_priv),
      'evidence_public_key_path':str(evidence_pub),'evidence_key_id':'evidence','nonce_ledger_root':str(root/'ledger'),
      'controller_runtime_public_key_path':str(runtime_pub),'controller_runtime_key_id':'runtime',
      'adapters':[{'name':'mock','path':str(adapter),'sha256':adapter_hash,'allowed_operations':['noop']}]}
    for name,key in [('plan.json','plan'),('manifest.json','manifest'),('attestation.json','attestation'),('ticket.json','ticket')]:
        document=root/name; document.write_text(json.dumps(docs[key])); os.chmod(document,0o600)
    (root/'config.json').write_text(json.dumps(config)); os.chmod(root/'config.json',0o600)
    schema_dir=pack/'repository-overlay'/'automation'/'schemas'; runner=pack/'external-capability-runner'/'capability_runner.py'
    installation={'format_version':'1.0','config_path':str(root/'config.json'),'config_sha256':sr.sha256_file(root/'config.json'),
      'schema_dir':str(schema_dir),'schema_hashes':{p.name:sr.sha256_file(p) for p in schema_dir.glob('*.json')},'launcher_sha256':sr.sha256_file(runner)}
    (root/'installation.json').write_text(json.dumps(installation)); os.chmod(root/'installation.json',0o600)
    return {**docs,'config':config,'evidence_private':evidence_priv,'evidence_public':evidence_pub,'runtime_private':runtime_priv,'runtime_public':runtime_pub,
      'keyring_path':keyring_path,'adapter':adapter,'adapter_hash':adapter_hash,'installation_path':root/'installation.json','runner':runner}
