from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import zipfile
from pathlib import Path

PACK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACK / "trusted-controller"))
import secure_runtime as sr

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def git(root: Path, *args: str) -> str:
    proc = subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True,
                          env={**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0"})
    return proc.stdout.strip()


def init_repo(root: Path) -> None:
    git(root, "init", "-q")
    git(root, "config", "user.email", "security@example.invalid")
    git(root, "config", "user.name", "AZPR Test")
    (root / "tracked.txt").write_text("base\n")
    git(root, "add", "tracked.txt")
    git(root, "commit", "-qm", "base")


def make_docx(path: Path, body_xml: str, extra: dict[str, str] | None = None) -> bytes:
    document = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>{body_xml}<w:sectPr/></w:body></w:document>'''
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types xmlns='http://schemas.openxmlformats.org/package/2006/content-types'/>")
        archive.writestr("word/document.xml", document)
        for name, value in (extra or {}).items():
            archive.writestr(name, value)
    return path.read_bytes()


class V7PreAutonomousClosureTests(unittest.TestCase):
    def test_nonroot_agent_surface_is_writable_and_controller_roots_remain_denied(self):
        if os.geteuid() == 0:
            with tempfile.TemporaryDirectory(dir='/tmp', prefix='azpr-v7-agent-handoff-test-') as td:
                root=Path(td);root.chmod(0o711);handoff=root/'handoff';handoff.mkdir(mode=0o711)
                protected=root/'protected.key';protected.write_text('secret');protected.chmod(0o400)
                output=root/'controller-result.json'
                result=subprocess.run([sys.executable,str(PACK/'operator-tools/exercise_agent_handoff.py'),'--handoff-root',str(handoff),'--agent-uid','65534','--agent-gid','65534','--protected-path',str(protected),'--controller-output',str(output)],capture_output=True,text=True)
                self.assertEqual(result.returncode,0,result.stderr);self.assertTrue(json.loads(output.read_text())['protected_denied']);self.assertEqual(stat.S_IMODE(output.stat().st_mode),0o600);self.assertEqual(list(handoff.iterdir()),[])
            return
        source=(PACK/'operator-tools/exercise_agent_handoff.py').read_text()
        for token in ("root is required for identity transition","--reuid","--regid","--clear-groups","--no-new-privs","protected_denied"):
            self.assertIn(token,source)
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);run=root/'run';home=run/'home';tmp=run/'tmp';outdir=run/'output';cache=run/'cache';work=run/'work'
            for d in (run,home,tmp,outdir,cache,work):d.mkdir();d.chmod(0o700)
            output=outdir/'result.json';output.write_text(json.dumps({'status':'PASS','protected_denied':True}));output.chmod(0o600)
            surface=sr.AgentRunSurface(root,run,home,tmp,outdir,output,cache,work,os.geteuid(),os.getegid(),sr._quota_profile(),False,False)
            imported=root/'controller-result.json';value=json.loads(sr.import_agent_result(surface,imported));self.assertTrue(value['protected_denied']);self.assertEqual(stat.S_IMODE(imported.stat().st_mode),0o600)
        with self.assertRaises(sr.SecurityError):sr.create_agent_run_surface(Path('/tmp'),agent_uid=65534,agent_gid=65534)

    def test_agent_result_symlink_and_hardlink_are_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);run=root/'run';home=run/'home';tmp=run/'tmp';outdir=run/'output';cache=run/'cache';work=run/'work'
            for d in (run,home,tmp,outdir,cache,work):d.mkdir();d.chmod(0o700)
            output=outdir/'result.json';surface=sr.AgentRunSurface(root,run,home,tmp,outdir,output,cache,work,os.geteuid(),os.getegid(),sr._quota_profile(),False,False)
            victim=root/'victim';victim.write_text('{}');victim.chmod(0o600)
            os.symlink(victim,output)
            with self.assertRaises(sr.SecurityError):sr.import_agent_result(surface,root/'out.json')
            output.unlink();os.link(victim,output)
            with self.assertRaises(sr.SecurityError):sr.import_agent_result(surface,root/'out2.json')

    def test_git_grafts_replace_refs_and_submodules_fail_preflight(self):
        for variant in ("graft", "replace", "submodule"):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as td:
                root=Path(td);init_repo(root)
                if variant == "graft":
                    (root/'.git/info/grafts').write_text(git(root,'rev-parse','HEAD')+'\n')
                elif variant == "replace":
                    p=root/'.git/refs/replace';p.mkdir(parents=True);(p/('a'*40)).write_text('b'*40+'\n')
                else:
                    (root/'.gitmodules').write_text('[submodule "x"]\npath=x\nurl=local\n')
                with self.assertRaises(sr.SecurityError):sr.repository_topology_preflight(root,[])

    def test_topology_preflight_is_before_nonce_and_branch_side_effects(self):
        source=(PACK/'trusted-controller/controller.py').read_text()
        start=source.index('def execute_action(');end=source.index('\ndef ',start+20);block=source[start:end]
        preflight=block.index('repository_topology_preflight')
        self.assertLess(preflight,block.index('nonce_ledger(root).consume'))
        self.assertLess(preflight,block.index('git(root, "switch", "-c"'))
        self.assertLess(preflight,block.index('write_stage_artifact_ledger'))

    def test_identity_ledger_cleanup_removes_only_stage_created_paths(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);init_repo(root)
            baseline=sr.worktree_identity_inventory(root)
            (root/'tracked.txt').write_text('mutated\n')
            (root/'new').mkdir();(root/'new/file.txt').write_text('agent')
            git(root,'reset','--hard','HEAD')
            result=sr.cleanup_worktree_to_baseline(root,baseline)
            self.assertIn('new/file.txt',result['removed_paths']);self.assertFalse((root/'new').exists())
            self.assertEqual(sr.worktree_identity_inventory(root)['semantic_sha256'],baseline['semantic_sha256'])

    def test_docx_renderer_preserves_tabs_and_explicit_breaks(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'policy.docx'
            raw=make_docx(p,"<w:p><w:r><w:t>A</w:t><w:tab/><w:t>B</w:t><w:br/><w:t>C</w:t></w:r></w:p>")
            manifest,canonical,section=sr.derive_docx_lossless_policy(raw,p.name)
            self.assertEqual(canonical,b'A\tB\nC\n')
            self.assertEqual(manifest['feature_inventory']['tabs'],1)
            self.assertEqual(manifest['feature_inventory']['breaks'],1)
            self.assertEqual(section['format_version'],'4.0')

    def test_docx_unsupported_normative_containers_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'table.docx';raw=make_docx(p,"<w:tbl><w:tr><w:tc><w:p><w:r><w:t>Normative</w:t></w:r></w:p></w:tc></w:tr></w:tbl>")
            with self.assertRaises(sr.SecurityError):sr.derive_docx_lossless_policy(raw,p.name)

    def _qualification_fixture(self, root: Path) -> tuple[Path, Path]:
        # Preserve the exact v7 legacy fixture independently of the v8 39-artifact template.
        legacy_path=PACK/'operator-tools/verify_v7_cleanroom_prerequisites.py'
        legacy_spec=importlib.util.spec_from_file_location('azpr_v7_legacy_cleanroom',legacy_path)
        legacy=importlib.util.module_from_spec(legacy_spec);legacy_spec.loader.exec_module(legacy)
        artifacts={name:{'path':'/REPLACE','sha256':'0'*64,'role':role,'type':kind}
                   for name,(role,kind) in legacy.ARTIFACT_SPECS.items()}
        template={'format_version':'2.0','safe_for_unattended_execution_now':False,
                  'agent_uid':65534,'agent_gid':65534,
                  'validation_image_digest':'sha256:'+'b'*64,
                  'installation_signing_key_id':'installation-fixture-key','artifacts':artifacts}
        paths={}
        pairs={}
        for label,private_name,public_name in (
            ('runtime','runtime_private_key','runtime_public_key'),
            ('evidence','evidence_private_key','evidence_public_key'),
            ('installation','installation_signing_private_key','installation_signing_public_key'),
        ):
            private=Ed25519PrivateKey.generate();pub=private.public_key()
            priv=root/f'{label}.private.pem';pubp=root/f'{label}.public.pem'
            priv.write_bytes(private.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()));priv.chmod(0o600)
            pubp.write_bytes(pub.public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo));pubp.chmod(0o444)
            pairs[private_name]=priv;pairs[public_name]=pubp
        for name,entry in artifacts.items():
            if name in pairs:path=pairs[name]
            elif entry['type']=='public_key':
                key=Ed25519PrivateKey.generate().public_key();path=root/f'{name}.pem';path.write_bytes(key.public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo));path.chmod(0o444)
            elif entry['type']=='executable':
                path=root/f'{name}.sh';path.write_text('#!/bin/sh\nexit 0\n');path.chmod(0o555)
            elif entry['type']=='qualification_report':
                kinds={
                 'codex_isolation_qualification_report':'CODEX_ISOLATION_QUALIFICATION','remote_anchor_qualification_report':'REMOTE_ANCHOR_QUALIFICATION','key_custody_qualification_report':'KEY_CUSTODY_QUALIFICATION','installer_fault_matrix_report':'INSTALLER_FAULT_MATRIX_QUALIFICATION','supply_chain_rebuild_report':'SUPPLY_CHAIN_REBUILD_QUALIFICATION','dedicated_host_policy':'DEDICATED_HOST_POLICY_QUALIFICATION'}
                path=root/f'{name}.json';path.write_text(json.dumps({'format_version':'1.0','report_kind':kinds[name],'status':'PASS','safe_for_unattended_execution_now':False,'artifact_bindings':{'fixture':'a'*64}}));path.chmod(0o444)
            elif name in ('approval_keyring','evidence_keyring'):
                path=root/f'{name}.json';path.write_text(json.dumps({'format_version':'1.0','keys':[{'key_id':'fixture-key','signer_id':'fixture-signer','roles':['security-approver'],'public_key_pem':'fixture'}]}));path.chmod(0o444)
            elif entry['type']=='json':
                path=root/f'{name}.json';path.write_text(json.dumps({'fixture':name}));path.chmod(0o444)
            else:
                path=root/f'{name}.bin';path.write_bytes((name+'\n').encode());path.chmod(0o444)
            paths[name]=path;entry['path']=str(path);entry['sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
        template['agent_uid']=65534;template['agent_gid']=65534;template['validation_image_digest']='sha256:'+'b'*64;template['installation_signing_key_id']='installation-fixture-key'
        manifest=root/'inputs.json';manifest.write_text(json.dumps(template,indent=2));manifest.chmod(0o444)
        return manifest,root/'receipt.json'

    def test_cleanroom_gate_rejects_empty_partial_unknown_and_alias_manifests(self):
        tool=PACK/'operator-tools/verify_v7_cleanroom_prerequisites.py'
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);manifest,receipt=self._qualification_fixture(root);value=json.loads(manifest.read_text())
            if os.geteuid()==0:
                complete=subprocess.run([sys.executable,str(tool),'--inputs',str(manifest),'--receipt-output',str(receipt)],capture_output=True,text=True)
                self.assertEqual(complete.returncode,0,complete.stderr);self.assertTrue(receipt.exists())
                for label,mutate in (('empty',lambda v:v.__setitem__('artifacts',{})),('missing',lambda v:v['artifacts'].pop('codex_binary')),('unknown',lambda v:v['artifacts'].__setitem__('unknown',dict(v['artifacts']['bundle_zip']))),('alias',lambda v:v['artifacts'].__setitem__('sbom',dict(v['artifacts']['build_provenance'])))):
                    with self.subTest(label=label):
                        candidate=json.loads(json.dumps(value));mutate(candidate);q=root/f'{label}.json';q.write_text(json.dumps(candidate));q.chmod(0o444)
                        result=subprocess.run([sys.executable,str(tool),'--inputs',str(q),'--receipt-output',str(root/f'{label}.receipt')],capture_output=True,text=True);self.assertNotEqual(result.returncode,0)
                return
            spec=importlib.util.spec_from_file_location('v7_cleanroom_nonroot',tool);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            def fake_inspect(name,entry):
                path=Path(entry['path']);identity=(hash(str(path)) & 0x7fffffff,hash(str(path)) & 0x7fffffff)
                return ({'path':str(path),'sha256':entry['sha256'],'size':max(1,path.stat().st_size),'mode':0o444,'uid':0,'gid':0,'role':entry['role'],'type':entry['type']},identity)
            def execute(candidate,out):
                manifest.chmod(0o600);manifest.write_text(json.dumps(candidate));manifest.chmod(0o444)
                with mock.patch.object(module.os,'geteuid',return_value=0),mock.patch.object(module,'inspect_artifact',side_effect=fake_inspect),mock.patch.object(module,'verify_key_pair'),mock.patch.object(sys,'argv',['verify','--inputs',str(manifest),'--receipt-output',str(out)]):
                    module.main()
            execute(value,receipt);self.assertTrue(receipt.exists())
            for label,mutate in (('empty',lambda v:v.__setitem__('artifacts',{})),('missing',lambda v:v['artifacts'].pop('codex_binary')),('unknown',lambda v:v['artifacts'].__setitem__('unknown',dict(v['artifacts']['bundle_zip']))),('alias',lambda v:v['artifacts'].__setitem__('sbom',dict(v['artifacts']['build_provenance'])))):
                with self.subTest(label=label):
                    candidate=json.loads(json.dumps(value));mutate(candidate)
                    with self.assertRaises(SystemExit):execute(candidate,root/f'{label}.receipt')
            source=tool.read_text();self.assertIn('clean-room prerequisite verification must run as root',source);self.assertIn('artifact path alias detected',source)

    def test_v6_incomplete_cleanroom_checker_is_retired(self):
        result=subprocess.run([sys.executable,str(PACK/'operator-tools/verify_v6_cleanroom_prerequisites.py')],capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0);self.assertIn('retired',result.stderr+result.stdout)


if __name__ == '__main__':
    unittest.main()
