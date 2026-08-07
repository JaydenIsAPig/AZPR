from __future__ import annotations
import json,re,unittest
from pathlib import Path
PACK=Path(__file__).resolve().parents[1]
SCHEMAS=PACK/'repository-overlay/automation/schemas'

class AutonomousPrimingControlTests(unittest.TestCase):
    def test_unapproved_condensed_policy_is_quarantined(self):
        self.assertFalse((PACK/'repository-overlay/automation/policy/AZPR-master-operating-prompt.md').exists())
        warning=(PACK/'policy-tools/UNAPPROVED-legacy-condensed-master-prompt.md').read_text()
        self.assertIn('DO NOT USE AS GOVERNING POLICY',warning)
        self.assertTrue((PACK/'repository-overlay/automation/policy/README.md').exists())

    def test_roadmap_generation_is_post_prompt004_signed_gate(self):
        source=(PACK/'trusted-controller/controller.py').read_text()
        for token in ('verify_roadmap_regeneration_authorization','roadmap-regeneration','--prompt-004-decision','--security-test-report'):
            self.assertIn(token,source)
        schema=json.loads((SCHEMAS/'roadmap-regeneration-authorization.schema.json').read_text())
        self.assertEqual(schema['properties']['prompt_004_status']['const'],'COMPLETED_APPROVED_RECONCILED')
        self.assertGreaterEqual(schema['properties']['signatures']['minItems'],2)

    def test_operation_registry_is_authoritative_and_ticket_is_recoverable(self):
        controller=(PACK/'trusted-controller/controller.py').read_text()
        registry=(PACK/'trusted-controller/evidence_registry.py').read_text()
        self.assertIn('operation_registry(root).registrations()',controller)
        self.assertIn('def cmd_export_operation_ticket',controller)
        self.assertIn('export-operation-ticket',controller)
        self.assertIn('def registrations(self)',registry)

    def test_installation_requires_policy_supply_chain_and_runtime_roots(self):
        loader=(PACK/'trusted-controller/trusted_installation.py').read_text()
        installer=(PACK/'trusted-installation/install.py').read_text()
        required=('canonical_policy','canonical_policy_record','canonical_policy_section_map','dependency_lock','sbom','build_provenance','validation_image_attestation','python_runtime_manifest','anchor_helper','evidence_keyring')
        for token in required:
            self.assertIn(repr(token),loader)
            self.assertIn(token,installer)
        self.assertIn('--require-hashes',installer)
        self.assertIn("'-m','venv','--copies'",installer)
        self.assertIn('verify_python_runtime',loader)

    def test_installer_requires_distinct_policy_and_build_signer_roles(self):
        source=(PACK/'trusted-installation/install.py').read_text()
        self.assertIn("['policy-owner','security-approver']",source)
        self.assertIn("['build-operator','security-approver']",source)
        self.assertIn('canonical policy record input hashes do not match',source)

    def test_every_json_schema_is_bounded_and_strict(self):
        issues=[]
        def walk(value,path):
            if isinstance(value,dict):
                typ=value.get('type');types=set(typ) if isinstance(typ,list) else {typ} if isinstance(typ,str) else set()
                if 'string' in types and not any(k in value for k in ('maxLength','const','enum','pattern')):issues.append(path+' unbounded string')
                if 'array' in types and 'maxItems' not in value:issues.append(path+' unbounded array')
                if 'object' in types and value.get('additionalProperties') is not False and 'maxProperties' not in value:issues.append(path+' unbounded object')
                for key,item in value.items():walk(item,path+'/'+str(key))
            elif isinstance(value,list):
                for i,item in enumerate(value):walk(item,path+'/'+str(i))
        for schema_path in SCHEMAS.glob('*.json'):
            walk(json.loads(schema_path.read_text()),schema_path.name)
        self.assertEqual(issues,[])

    def test_result_schema_approval_and_external_plan_are_strict(self):
        schema=json.loads((SCHEMAS/'result.schema.json').read_text())
        text=json.dumps(schema)
        self.assertIn('deployment-plan.schema.json',text)
        self.assertRegex(text,r'"approval"')
        approval=schema['properties']['approval']
        self.assertIn('oneOf',approval)
        nonnull=[x for x in approval['oneOf'] if x.get('type')=='object'][0]
        self.assertFalse(nonnull['additionalProperties'])

    def test_no_stale_external_runner_launcher_or_fake_lock(self):
        self.assertFalse((PACK/'external-capability-runner/installed_launcher.py').exists())
        self.assertFalse((PACK/'requirements-security.lock').exists())
        self.assertTrue((PACK/'requirements-security.in').exists())
        self.assertTrue((PACK/'operator-tools/build_supply_chain_bundle.py').exists())

if __name__=='__main__':unittest.main(verbosity=2)
