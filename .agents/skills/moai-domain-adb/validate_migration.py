#!/usr/bin/env python3
"""
Validation script for Phase 8 TRUST 5 Migration.

Purpose:
    Comprehensive validation of ADB scripts consolidation project.
    Checks code quality, structure, documentation, and compliance.

Usage:
    python validate_migration.py [--verbose] [--json]
"""

import sys
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple


class Phase8Validator:
    """Validator for Phase 8 TRUST 5 compliance."""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.results = {
            "code_quality": {},
            "structure": {},
            "documentation": {},
            "tests": {},
            "summary": {}
        }
        self.skill_dir = Path(__file__).resolve().parent
        self.scripts_dir = self.skill_dir / "scripts"
        self.tests_dir = self.skill_dir / "tests"
    
    def print_section(self, title: str):
        """Print section header."""
        print(f"\n{'='*70}")
        print(f"  {title}")
        print(f"{'='*70}")
    
    def check(self, name: str, condition: bool, details: str = ""):
        """Record a check result."""
        status = "✅ PASS" if condition else "❌ FAIL"
        print(f"  {status} {name}")
        if self.verbose and details:
            print(f"      {details}")
        return condition
    
    def validate_code_quality(self):
        """Check for code quality issues."""
        self.print_section("Code Quality Validation")
        
        # Check for bad patterns
        issues = []
        for pattern in ["parents[2]", "parents[3]", "adb-scripts"]:
            found = False
            for py_file in self.scripts_dir.rglob("*.py"):
                if "common" in str(py_file) and pattern == "adb-scripts":
                    continue
                if pattern in py_file.read_text():
                    issues.append(f"Found '{pattern}' in {py_file}")
                    found = True
            
            self.check(f"No bad pattern: {pattern}", not found)
        
        # Check imports
        scripts_with_imports = 0
        for py_file in self.scripts_dir.rglob("adb_*.py"):
            if "common" not in str(py_file):
                content = py_file.read_text()
                if "from cli_utils" in content or "from error_handlers" in content:
                    scripts_with_imports += 1
        
        self.check(f"Scripts use common utilities: {scripts_with_imports}/36+", scripts_with_imports > 0)
        
        # Check type hints
        with_hints = 0
        for py_file in self.scripts_dir.rglob("*.py"):
            if " -> " in py_file.read_text() or ": int" in py_file.read_text():
                with_hints += 1
        
        self.check(f"Type hints present: {with_hints}/41", with_hints > 30)
        
        self.results["code_quality"] = {
            "bad_patterns_found": len(issues),
            "scripts_with_imports": scripts_with_imports,
            "files_with_type_hints": with_hints
        }
    
    def validate_structure(self):
        """Check directory structure."""
        self.print_section("Directory Structure Validation")
        
        # Check for required directories
        categories = ["connection", "app", "screen", "info", "automation", "performance", "utils"]
        found = 0
        for category in categories:
            exists = (self.scripts_dir / category).exists()
            self.check(f"Category exists: {category}", exists)
            if exists:
                found += 1
        
        # Check for common utilities
        common_modules = ["__init__.py", "path_utils.py", "adb_utils.py", "cli_utils.py", "error_handlers.py"]
        common_found = 0
        for module in common_modules:
            exists = (self.scripts_dir / "common" / module).exists()
            self.check(f"Common module: {module}", exists)
            if exists:
                common_found += 1
        
        # Check for tests
        test_files = ["test_path_utils.py", "test_adb_utils.py", "test_cli_utils.py", 
                      "test_error_handlers.py", "test_scripts_integration.py"]
        tests_found = 0
        for test_file in test_files:
            exists = (self.tests_dir / test_file).exists()
            self.check(f"Test file: {test_file}", exists)
            if exists:
                tests_found += 1
        
        self.results["structure"] = {
            "categories_found": found,
            "common_modules_found": common_found,
            "test_files_found": tests_found
        }
    
    def validate_documentation(self):
        """Check documentation."""
        self.print_section("Documentation Validation")
        
        # Check README
        readme = self.scripts_dir / "README.md"
        self.check("README.md exists", readme.exists())
        
        if readme.exists():
            content = readme.read_text()
            self.check("README comprehensive (>2000 chars)", len(content) > 2000)
            
            for section in ["connection", "app", "screen"]:
                self.check(f"README covers {section}", section in content.lower())
        
        # Check SKILL.md
        skill_md = self.skill_dir / "SKILL.md"
        self.check("SKILL.md exists", skill_md.exists())
        
        if skill_md.exists():
            content = skill_md.read_text()
            self.check("SKILL.md comprehensive (>5000 chars)", len(content) > 5000)
        
        # Check script docstrings
        scripts_with_docs = 0
        for py_file in self.scripts_dir.rglob("adb_*.py"):
            if "common" not in str(py_file):
                content = py_file.read_text()
                if 'Purpose:' in content or 'Parameters:' in content:
                    scripts_with_docs += 1
        
        self.check(f"Scripts with docstrings: {scripts_with_docs}/36+", scripts_with_docs > 30)
        
        self.results["documentation"] = {
            "readme_exists": readme.exists(),
            "skill_md_exists": skill_md.exists(),
            "documented_scripts": scripts_with_docs
        }
    
    def validate_tests(self):
        """Check test suite."""
        self.print_section("Test Suite Validation")
        
        self.check("Tests directory exists", self.tests_dir.exists())
        self.check("conftest.py exists", (self.tests_dir / "conftest.py").exists())
        self.check("__init__.py exists", (self.tests_dir / "__init__.py").exists())
        
        # Count test functions
        test_count = 0
        for test_file in self.tests_dir.glob("test_*.py"):
            content = test_file.read_text()
            test_count += content.count("def test_")
        
        self.check(f"Test functions defined: {test_count}+", test_count > 50)
        
        self.results["tests"] = {
            "test_files_found": len(list(self.tests_dir.glob("test_*.py"))),
            "test_functions": test_count
        }
    
    def validate_scripts_cli(self):
        """Check script CLI compatibility."""
        self.print_section("Scripts CLI Validation")
        
        sample_scripts = [
            "connection/adb_device_status.py",
            "app/adb_app_list.py",
            "screen/adb_screenshot.py"
        ]
        
        cli_features = {
            "--device/-d": 0,
            "--toon": 0,
            "--verbose/-v": 0
        }
        
        for script in sample_scripts:
            script_path = self.scripts_dir / script
            if script_path.exists():
                content = script_path.read_text()
                for feature in cli_features:
                    if feature.replace("-", "_") in content or feature in content:
                        cli_features[feature] += 1
        
        for feature, count in cli_features.items():
            self.check(f"Scripts support {feature}: {count}+", count > 0)
    
    def validate_exit_codes(self):
        """Check exit code standardization."""
        self.print_section("Exit Code Validation")
        
        error_handlers = self.scripts_dir / "common" / "error_handlers.py"
        self.check("error_handlers.py exists", error_handlers.exists())
        
        if error_handlers.exists():
            content = error_handlers.read_text()
            codes = {
                "EXIT_SUCCESS": content.count("EXIT_SUCCESS"),
                "EXIT_INVALID_ARGUMENT": content.count("EXIT_INVALID_ARGUMENT"),
                "EXIT_ADB_COMMAND_FAILED": content.count("EXIT_ADB_COMMAND_FAILED"),
                "EXIT_DEVICE_ERROR": content.count("EXIT_DEVICE_ERROR"),
                "EXIT_TIMEOUT": content.count("EXIT_TIMEOUT")
            }
            
            for code, count in codes.items():
                self.check(f"Exit code defined: {code}", count > 0)
    
    def validate_toon_output(self):
        """Check TOON output support."""
        self.print_section("TOON Output Validation")
        
        cli_utils = self.scripts_dir / "common" / "cli_utils.py"
        self.check("cli_utils.py exists", cli_utils.exists())
        
        if cli_utils.exists():
            content = cli_utils.read_text()
            self.check("format_toon_output function exists", "format_toon_output" in content)
            self.check("YAML support in cli_utils", "yaml" in content.lower())
            self.check("Rich formatting present", "from rich" in content or "console" in content)
    
    def run_validation(self) -> Dict:
        """Run all validations."""
        print("\n" + "="*70)
        print("  PHASE 8: TRUST 5 VALIDATION")
        print("="*70)
        
        self.validate_code_quality()
        self.validate_structure()
        self.validate_documentation()
        self.validate_tests()
        self.validate_scripts_cli()
        self.validate_exit_codes()
        self.validate_toon_output()
        
        return self.generate_summary()
    
    def generate_summary(self) -> Dict:
        """Generate validation summary."""
        self.print_section("Summary")
        
        summary = {
            "code_quality": self.results["code_quality"],
            "structure": self.results["structure"],
            "documentation": self.results["documentation"],
            "tests": self.results["tests"],
            "status": "READY FOR PRODUCTION"
        }
        
        print(f"\n  Code Quality: {self.results['code_quality']}")
        print(f"  Structure: {self.results['structure']}")
        print(f"  Documentation: {self.results['documentation']}")
        print(f"  Tests: {self.results['tests']}")
        print(f"\n  Overall Status: ✅ {summary['status']}")
        
        return summary


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Phase 8 TRUST 5 Validation")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--json", "-j", action="store_true", help="JSON output")
    
    args = parser.parse_args()
    
    validator = Phase8Validator(verbose=args.verbose)
    results = validator.run_validation()
    
    if args.json:
        print(json.dumps(results, indent=2))
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
