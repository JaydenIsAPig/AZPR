#!/usr/bin/env python3
"""Build a complete synthetic-but-cryptographically-valid v8 verifier fixture.

TEST ONLY. This fixture proves workflow correctness; it is not real host or
supply-chain qualification evidence and must never be used for installation.
"""
from __future__ import annotations
import argparse,base64,hashlib,json,os,runpy,stat,sys,zipfile
from datetime import datetime,timezone,timedelta
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
ROOT=Path(__file__).resolve().parents[1]
NS=runpy.run_path(str(ROOT/'operator-tools/verify_v8_cleanroom_prerequisites.py'),run_name='fixture_import')
SPECS=NS['ARTIFACT_SPECS'];REPORT_ROLES=NS['REPORT_ROLES']
def canon(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def h(raw):return hashlib.sha256(raw).hexdigest()
def hp(p):return h(p.read_bytes())
def write(path,data,mode=0o444):
 path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data if isinstance(data,bytes) else (json.dumps(data,indent=2,sort_keys=True)+'\n').encode());path.chmod(mode);return path
def keypair(root,name):
 k=Ed25519PrivateKey.generate();pr=write(root/f'{name}.private.pem',k.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()),0o600);pu=write(root/f'{name}.public.pem',k.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo),0o444);return k,pr,pu
def row(k,key_id,signer_id,roles):return {'key_id':key_id,'signer_id':signer_id,'roles':roles,'public_key_pem':k.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo).decode(),'revoked_at':None}
def sign_one(k,v):return base64.b64encode(k.sign(canon(v))).decode()
def multisig(v,signers):
 out=dict(v);out['signatures']=[{'key_id':kid,'ed25519':sign_one(k,v)} for kid,k in signers];return out
def make_docx(path):
 with zipfile.ZipFile(path,'w') as z:
  z.writestr('[Content_Types].xml','<Types/>');z.writestr('word/document.xml','<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Fixture only</w:t></w:r></w:p></w:body></w:document>')
 path.chmod(0o444);return path
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',required=True);a=ap.parse_args();root=Path(a.output).absolute();root.mkdir(parents=True,exist_ok=True);root.chmod(0o755)
 now=datetime.now(timezone.utc);issued=now.isoformat();expires=(now+timedelta(days=2)).isoformat();H='a'*64;host='fixture-host-v8';image='sha256:'+'c'*64
 keys={};pairs={}
 for name in ('runtime','evidence','installation','qualification-receipt','bundle','mirror'):
  keys[name],pairs[name+'-priv'],pairs[name+'-pub']=keypair(root,name)
 role_names=['installation-authorizer','security-approver','revocation-authority','isolation-qualifier','anchor-qualifier','key-custody-qualifier','installer-fault-qualifier','build-qualifier','host-security-qualifier','build-operator','external-evidence']
 for role in role_names:keys[role],_,pairs[role+'-pub']=keypair(root,role)
 qrows=[row(keys[r],r+'-key',r+'-signer',[r]) for r in role_names if r not in ('build-operator','external-evidence')]
 qring=write(root/'qualification-keyring.json',{'format_version':'1.0','keys':qrows})
 approval=write(root/'approval-keyring.json',{'format_version':'1.0','keys':[row(keys['build-operator'],'build-operator-key','build-operator-signer',['build-operator']),row(keys['security-approver'],'approval-security-key','approval-security-signer',['security-approver'])]})
 evidence_ring=write(root/'evidence-keyring.json',{'format_version':'1.0','keys':[row(keys['external-evidence'],'external-evidence-key','external-evidence-signer',['external-evidence'])]})
 rev_unsigned={'format_version':'1.0','list_id':'fixture-revocation-list','sequence':1,'issued_at':issued,'expires_at':expires,'revoked_key_ids':[],'previous_list_sha256':None}
 rev=write(root/'qualification-revocations.json',multisig(rev_unsigned,[('revocation-authority-key',keys['revocation-authority']),('security-approver-key',keys['security-approver'])]))
 quota={'format_version':'1.0','profile_id':'fixture-quota-v8','filesystem_type':'tmpfs','mount_options':['nodev','nosuid','noexec','mode=0700'],'max_bytes':67108864,'max_inodes':4096,'max_entries':4096,'max_file_bytes':8388608,'max_depth':32,'max_path_length':1024,'cleanup_max_entries':8192,'cleanup_timeout_seconds':10}
 quota_p=write(root/'handoff-quota.json',quota)
 gate_raw=(ROOT/'trusted-controller/process_gate.py').read_bytes()
 profile={'format_version':'1.0','profile_id':'fixture-execution-v8','host_id':host,'agent_uid':65534,'agent_gid':65534,'supplementary_groups':[],'cgroup_root':'/sys/fs/cgroup/azpr/fixture','cgroup_kill_required':True,'pid_namespace_required':True,'mount_namespace_required':True,'network_namespace_mode':'DENY_ALL','capabilities_sha256':'1'*64,'mount_profile_sha256':'2'*64,'quota_profile_sha256':hp(quota_p),'lsm_profile_sha256':'3'*64,'cgroup_profile_sha256':'4'*64,'namespace_profile_sha256':'5'*64,'acl_profile_sha256':'6'*64,'process_gate_sha256':h(gate_raw),'pids_max':64,'memory_max_bytes':268435456,'cpu_max':'100000 100000','process_empty_timeout_seconds':10,'created_at':issued,'expires_at':expires}
 profile_p=write(root/'agent-execution-profile.json',profile)
 # Candidate archive and internal manifest.
 payload=b'fixture payload\n';entries={'payload.txt':h(payload),'trusted-controller/process_gate.py':h(gate_raw)}
 manifest={'format_version':'1.0','algorithm':'SHA-256','bundle_name':'AZPR-v8-fixture','bundle_type':'implementation','expected_inventory_count':len(entries),'excludes':['SHA256SUMS.json'],'entries':entries};mraw=(json.dumps(manifest,indent=2,sort_keys=True)+'\n').encode();bundle=root/'AZPR-v8-fixture.zip'
 with zipfile.ZipFile(bundle,'w',zipfile.ZIP_DEFLATED) as z:z.writestr('AZPR-v8-fixture/payload.txt',payload);z.writestr('AZPR-v8-fixture/trusted-controller/process_gate.py',gate_raw);z.writestr('AZPR-v8-fixture/SHA256SUMS.json',mraw)
 bundle.chmod(0o444);archive_hash=hp(bundle);manifest_hash=h(mraw);total=len(payload)+len(gate_raw)+len(mraw)
 batt_u={'format_version':'2.0','bundle_name':'AZPR-v8-fixture','bundle_archive_sha256':archive_hash,'bundle_manifest_sha256':manifest_hash,'bundle_file_count':3,'bundle_total_bytes':total,'created_at':issued,'signer_key_id':'bundle-key'};batt=dict(batt_u);batt['signature']=sign_one(keys['bundle'],batt_u);batt_p=write(root/'bundle-attestation.json',batt)
 # Executables with deterministic identity output.
 execs={}
 for name in ('git_binary','python_binary','codex_binary','container_engine','anchor_helper'):
  text='#!/bin/sh\n';text+='echo anchor-fixture-v8\n' if name=='anchor_helper' else f'echo {name}-fixture-v8\n';execs[name]=write(root/(name+'.sh'),text.encode(),0o555)
 policy=make_docx(root/'master.docx');requirements=write(root/'requirements.in',b'demo==1.0\n');wheel_hash='7'*64;lock=write(root/'requirements.lock',f'demo==1.0 --hash=sha256:{wheel_hash}\n'.encode());docker=write(root/'Dockerfile',b'FROM scratch\n')
 files=[{'path':'wheels/demo-1.0-py3-none-any.whl','sha256':wheel_hash,'size':123}];inv_hash=h(canon(files));inv={'format_version':'1.0','mirror_name':'fixture-mirror','inventory_sha256':inv_hash,'file_count':1,'total_bytes':123,'files':files};inv_p=write(root/'mirror-inventory.json',inv)
 matt_u={'format_version':'1.0','mirror_name':'fixture-mirror','inventory_sha256':inv_hash,'file_count':1,'total_bytes':123,'created_at':issued,'signer_key_id':'mirror-key'};matt=dict(matt_u);matt['signature']=sign_one(keys['mirror'],matt_u);matt_p=write(root/'mirror-attestation.json',matt)
 wheels=[{'filename':'demo-1.0-py3-none-any.whl','sha256':wheel_hash,'name':'demo','version':'1.0','size':123}];wheel_set=h(canon(wheels))
 provenance={'format_version':'2.0','created_at':issued,'requirements_input_sha256':hp(requirements),'dependency_lock_sha256':hp(lock),'mirror':{'name':'fixture-mirror','inventory_sha256':inv_hash,'attestation_sha256':hp(matt_p),'public_key_sha256':hp(pairs['mirror-pub']),'signer_key_id':'mirror-key','file_count':1},'builder':{'python_path':str(execs['python_binary']),'python_sha256':hp(execs['python_binary']),'python_version':'fixture','pip_version':'fixture'},'resolution_passes':[{'index':1,'command':['fixture'],'wheel_set_sha256':wheel_set},{'index':2,'command':['fixture'],'wheel_set_sha256':wheel_set}],'wheels':wheels,'reproducible':True};prov_p=write(root/'build-provenance.json',provenance)
 sbom={'bomFormat':'CycloneDX','specVersion':'1.5','version':1,'components':[{'type':'library','name':'demo','version':'1.0','hashes':[{'alg':'SHA-256','content':wheel_hash}],'properties':[{'name':'azpr:wheel','value':'demo-1.0-py3-none-any.whl'}]}]};sbom_p=write(root/'sbom.json',sbom)
 att_u={'format_version':'1.0','attestation_id':'fixture-validation-image','image_reference':'registry.invalid/fixture@'+image,'image_digest':image,'dockerfile_sha256':hp(docker),'sbom_sha256':hp(sbom_p),'build_provenance_sha256':hp(prov_p),'created_at':issued};image_att=multisig(att_u,[('build-operator-key',keys['build-operator']),('approval-security-key',keys['security-approver'])]);image_att_p=write(root/'image-attestation.json',image_att)
 registry_u={'format_version':'1.0','image_digest':image,'registry':'registry.invalid','observed_digest':image,'proof_sha256':'8'*64,'issued_at':issued,'expires_at':expires,'signer_key_id':'build-qualifier-key','signer_role':'build-qualifier'};registry=dict(registry_u);registry['signature']=sign_one(keys['build-qualifier'],registry_u);registry_p=write(root/'registry-proof.json',registry)
 # Base artifact map before reports.
 paths={
 'bundle_zip':bundle,'bundle_attestation':batt_p,'bundle_signing_public_key':pairs['bundle-pub'],'runtime_private_key':pairs['runtime-priv'],'runtime_public_key':pairs['runtime-pub'],'evidence_private_key':pairs['evidence-priv'],'evidence_public_key':pairs['evidence-pub'],'installation_signing_private_key':pairs['installation-priv'],'installation_signing_public_key':pairs['installation-pub'],'qualification_receipt_signing_private_key':pairs['qualification-receipt-priv'],'qualification_receipt_signing_public_key':pairs['qualification-receipt-pub'],'qualification_authorization_keyring':qring,'qualification_revocation_list':rev,'approval_keyring':approval,'evidence_keyring':evidence_ring,
 **execs,'governing_policy_source':policy,'requirements_input':requirements,'dependency_lock':lock,'dependency_mirror_inventory':inv_p,'dependency_mirror_attestation':matt_p,'dependency_mirror_public_key':pairs['mirror-pub'],'sbom':sbom_p,'build_provenance':prov_p,'validation_dockerfile':docker,'validation_image_attestation':image_att_p,'validation_registry_proof':registry_p,'agent_execution_profile':profile_p,'handoff_quota_profile':quota_p}
 base_bindings={n:hp(p) for n,p in paths.items()}
 quota_limits={'bytes':quota['max_bytes'],'inodes':quota['max_inodes'],'entries':quota['max_entries'],'max_file_bytes':quota['max_file_bytes'],'max_depth':quota['max_depth'],'max_path_length':quota['max_path_length'],'cleanup_timeout_seconds':quota['cleanup_timeout_seconds']}
 measurements={
 'CODEX_ISOLATION_QUALIFICATION':{'cgroup_v2':True,'pid_namespace':True,'mount_namespace':True,'agent_uid':65534,'agent_gid':65534,'supplementary_groups':[],'capabilities_sha256':profile['capabilities_sha256'],'lsm_profile_sha256':profile['lsm_profile_sha256'],'mount_profile_sha256':profile['mount_profile_sha256'],'quota_profile_sha256':hp(quota_p),'process_tree_tests':{x:True for x in ['background','double-fork','setsid','orphan','ignored-signal']},'secret_denial_tests':{x:True for x in ['keys','journals','other-runs']},'quota_limits':quota_limits},
 'REMOTE_ANCHOR_QUALIFICATION':{'anchor_endpoint_id':'fixture-anchor','challenge_nonce':'fixture-challenge','challenge_response_sha256':'9'*64,'rollback_test_passed':True,'restore_test_passed':True},
 'KEY_CUSTODY_QUALIFICATION':{'hardware_or_brokered':True,'agent_read_denied':True,'rotation_test_passed':True,'revocation_test_passed':True,'compromise_recovery_test_passed':True},
 'INSTALLER_FAULT_MATRIX_QUALIFICATION':{'fault_points_tested':12,'all_fault_cases_passed':True,'no_partial_state':True,'recovery_deterministic':True},
 'SUPPLY_CHAIN_REBUILD_QUALIFICATION':{'resolution_pass_count':2,'wheel_set_sha256':wheel_set,'sbom_sha256':hp(sbom_p),'build_provenance_sha256':hp(prov_p),'reproducible':True,'registry_proof_sha256':hp(registry_p)},
 'DEDICATED_HOST_POLICY_QUALIFICATION':{'dedicated_host':True,'cgroup_v2':True,'pid_namespace':True,'mount_namespace':True,'measured_boot_policy_sha256':'a'*64,'os_policy_sha256':'b'*64,'cgroup_profile_sha256':profile['cgroup_profile_sha256'],'mount_profile_sha256':profile['mount_profile_sha256'],'quota_profile_sha256':hp(quota_p),'lsm_profile_sha256':profile['lsm_profile_sha256'],'quota_limits':quota_limits},
 }
 for name,(kind,role) in REPORT_ROLES.items():
  raw=write(root/(name+'.evidence'),(name+' immutable evidence\n').encode());rawrow={'evidence_id':name+'-raw','kind':kind.lower().replace('_','-'),'path':str(raw),'sha256':hp(raw),'size':raw.stat().st_size}
  signer=keys[role];kid=role+'-key';u={'format_version':'2.0','report_id':name+'-fixture','report_kind':kind,'status':'PASS','safe_for_unattended_execution_now':False,'issued_at':issued,'expires_at':expires,'host_id':host,'candidate_archive_sha256':archive_hash,'bundle_manifest_sha256':manifest_hash,'validation_image_digest':image,'artifact_bindings':dict(base_bindings),'measurements':measurements[kind],'raw_evidence':[rawrow],'signer_key_id':kid,'signer_role':role};r=dict(u);r['signature']=sign_one(signer,u);paths[name]=write(root/(name+'.json'),r)
 artifacts={}
 for n,(role,typ) in SPECS.items():
  p=paths[n];artifacts[n]={'path':str(p),'sha256':hp(p),'role':role,'type':typ}
 inputs={'format_version':'3.0','safe_for_unattended_execution_now':False,'candidate_archive_sha256':archive_hash,'bundle_manifest_sha256':manifest_hash,'host_id':host,'agent_uid':65534,'agent_gid':65534,'validation_image_digest':image,'receipt_signing_key_id':'qualification-receipt-key','artifacts':artifacts}
 input_path=write(root/'qualification-inputs.json',inputs);print(json.dumps({'inputs':str(input_path),'receipt':str(root/'qualification-receipt.json'),'artifact_count':len(artifacts)},indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
