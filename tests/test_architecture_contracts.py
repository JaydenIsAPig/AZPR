import ast
import dataclasses
import sys
import unittest
from pathlib import Path

from az_permit_radar.application import commands, queries, repositories
from az_permit_radar.domain import (
    Address,
    ClassificationResult,
    CustomerAccount,
    CustomerFilter,
    CustomerTradePreference,
    ImportBatch,
    Jurisdiction,
    LeadState,
    NotificationAttempt,
    NotificationPreference,
    Opportunity,
    OpportunityMatch,
    ParcelReference,
    Permit,
    ProjectClassification,
    ReviewTask,
    ServiceTerritory,
    Source,
    SourceArtifact,
    SourceRecord,
    TradeTag,
)


class ArchitectureContractTests(unittest.TestCase):
    def test_required_domain_concepts_are_concrete_dataclasses(self) -> None:
        concepts = (
            Jurisdiction,
            Source,
            SourceArtifact,
            ImportBatch,
            SourceRecord,
            Permit,
            Address,
            ParcelReference,
            ProjectClassification,
            TradeTag,
            ClassificationResult,
            Opportunity,
            CustomerAccount,
            CustomerTradePreference,
            ServiceTerritory,
            CustomerFilter,
            OpportunityMatch,
            NotificationPreference,
            NotificationAttempt,
            ReviewTask,
        )
        self.assertTrue(all(dataclasses.is_dataclass(concept) for concept in concepts))
        self.assertTrue(issubclass(LeadState, str))

    def test_no_ambiguous_generic_domain_model_names_exist(self) -> None:
        forbidden = {"Data", "Record", "Item", "Lead"}
        exported = {name for name in dir(__import__("az_permit_radar.domain", fromlist=["*"]))}
        self.assertFalse(forbidden & exported)

    def test_cqrs_and_repository_contracts_import_without_infrastructure(self) -> None:
        self.assertTrue(hasattr(commands, "CreatePermit"))
        self.assertTrue(hasattr(queries, "FindOpportunityMatchesForCustomer"))
        self.assertTrue(hasattr(repositories, "PermitRepository"))

    def test_domain_and_application_contracts_have_no_external_dependencies(self) -> None:
        package_root = Path(__file__).parents[1] / "src" / "az_permit_radar"
        violations: list[str] = []
        for layer in ("domain", "application"):
            for path in (package_root / layer).glob("*.py"):
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            root = alias.name.split(".", 1)[0]
                            if root not in sys.stdlib_module_names:
                                violations.append(f"{path.name}: {alias.name}")
                    elif isinstance(node, ast.ImportFrom) and node.level == 0:
                        module = node.module or ""
                        root = module.split(".", 1)[0]
                        if root not in sys.stdlib_module_names and not module.startswith(
                            "az_permit_radar.domain"
                        ):
                            violations.append(f"{path.name}: {module}")
        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
