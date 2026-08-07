import hashlib
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "check_v10_1_prompt_stage_pack.py"
SPEC = importlib.util.spec_from_file_location("prompt_stage_pack", SCRIPT)
assert SPEC and SPEC.loader
prompt_stage_pack = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prompt_stage_pack)


class V101PromptStagePackTests(unittest.TestCase):
    pack = ROOT / "automation" / "integration" / "v10.1" / "prompt-stages"

    def copied_root(self, directory: str) -> Path:
        root = Path(directory)
        destination = root / prompt_stage_pack.PACK_RELATIVE
        destination.parent.mkdir(parents=True)
        shutil.copytree(self.pack, destination)
        return root

    @staticmethod
    def refresh_hash(root: Path, filename: str) -> None:
        pack = root / prompt_stage_pack.PACK_RELATIVE
        hashes_path = pack / "SHA256SUMS.json"
        hashes = json.loads(hashes_path.read_text(encoding="utf-8"))
        hashes["files"][filename] = hashlib.sha256((pack / filename).read_bytes()).hexdigest()
        hashes_path.write_text(json.dumps(hashes, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def test_current_pack_is_valid_and_inert(self) -> None:
        self.assertEqual(prompt_stage_pack.validate_pack(ROOT), [])

    def test_changed_prompt_byte_fails_hash_binding(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copied_root(directory)
            prompt = root / prompt_stage_pack.PACK_RELATIVE / "00-preflight-authority-and-inputs.md"
            prompt.write_text(prompt.read_text(encoding="utf-8") + "\nchanged\n", encoding="utf-8")
            errors = prompt_stage_pack.validate_pack(root)
        self.assertTrue(any("byte hash mismatch" in error for error in errors))

    def test_reordered_stage_chain_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copied_root(directory)
            pack = root / prompt_stage_pack.PACK_RELATIVE
            manifest_path = pack / "stage-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["stages"][0], manifest["stages"][1] = manifest["stages"][1], manifest["stages"][0]
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            self.refresh_hash(root, "stage-manifest.json")
            errors = prompt_stage_pack.validate_pack(root)
        self.assertTrue(any("stage sequence" in error or "manifest" in error for error in errors))

    def test_h2_external_write_authority_cannot_be_widened(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copied_root(directory)
            pack = root / prompt_stage_pack.PACK_RELATIVE
            manifest_path = pack / "stage-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["stages"][5]["external_write"] = True
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            self.refresh_hash(root, "stage-manifest.json")
            errors = prompt_stage_pack.validate_pack(root)
        self.assertTrue(any("INT-05" in error and "external_write" in error for error in errors))

    def test_required_stop_conditions_cannot_be_removed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copied_root(directory)
            pack = root / prompt_stage_pack.PACK_RELATIVE
            prompt_path = pack / "03-h1-materialize-approved-repository-mapping.md"
            prompt_path.write_text(
                prompt_path.read_text(encoding="utf-8").replace("# Stop conditions", "# Paused cases"),
                encoding="utf-8",
            )
            self.refresh_hash(root, prompt_path.name)
            errors = prompt_stage_pack.validate_pack(root)
        self.assertTrue(any("missing required section # Stop conditions" in error for error in errors))

    def test_agent_cannot_be_allowed_to_create_human_approval(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copied_root(directory)
            pack = root / prompt_stage_pack.PACK_RELATIVE
            manifest_path = pack / "stage-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["execution_policy"]["human_approval_may_be_created_by_agent"] = True
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            self.refresh_hash(root, "stage-manifest.json")
            errors = prompt_stage_pack.validate_pack(root)
        self.assertTrue(any("execution policy" in error for error in errors))

    def test_first_audit_index_bootstrap_cannot_be_removed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copied_root(directory)
            pack = root / prompt_stage_pack.PACK_RELATIVE
            prompt_path = pack / "04-h1-repository-integration-audit.md"
            prompt_path.write_text(
                prompt_path.read_text(encoding="utf-8").replace(
                    "commit the report and index together",
                    "record audit output",
                ),
                encoding="utf-8",
            )
            self.refresh_hash(root, prompt_path.name)
            errors = prompt_stage_pack.validate_pack(root)
        self.assertTrue(any("first-audit bootstrap" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
