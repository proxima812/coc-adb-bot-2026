#!/usr/bin/env python3
# /// script
# dependencies = [
#     "click>=8.1.0",
#     "jinja2>=3.0.0",
# ]
# ///

"""
ADB Bot Generator

Generate bot skeleton from template with game-specific patterns for ADB Auto Player.

Usage:
    uv run adb_bot_generator.py --game-name "My Game" --template daily-quest
    uv run adb_bot_generator.py --game-name "Arena Bot" --template arena --json
    uv run adb_bot_generator.py --game-name "Fishing Bot" --template fishing --output-file custom_bot.py
    uv run adb_bot_generator.py --game-name "Custom" --template base --dry-run

Exit Codes:
    0 - Success (bot generated)
    1 - Invalid input (missing required parameters)
    2 - Template not found error
    3 - Validation error (generated bot invalid syntax)
"""

import ast
import json
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

import click
from jinja2 import Environment, FileSystemLoader, TemplateNotFound


# ============================================================================
# Configuration
# ============================================================================

TEMPLATES_DIR = Path(__file__).parent / "templates" / "bots"

TEMPLATE_TYPES = {
    "base": "Base bot template with core structure",
    "daily-quest": "Daily quest automation bot",
    "arena": "Arena/PvP battle bot",
    "fishing": "Fishing minigame bot",
    "dungeon": "Dungeon crawler bot",
    "farming": "Resource farming bot",
    "guild": "Guild activities bot",
}

DEFAULT_IMPORTS = [
    "import logging",
    "from time import sleep",
    "",
    "from adb_auto_player.decorators import register_command",
    "from adb_auto_player.exceptions import GameTimeoutError",
    "from adb_auto_player.models.decorators import GUIMetadata",
    "from adb_auto_player.models.geometry import Point",
]


# ============================================================================
# Custom Exceptions
# ============================================================================

class TemplateNotFoundError(Exception):
    """Raised when template file is not found."""
    pass


class InvalidSyntaxError(Exception):
    """Raised when generated bot has invalid Python syntax."""
    pass


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class BotMetadata:
    """Bot generation metadata."""
    game_name: str
    template_type: str
    class_name: str
    module_name: str
    generated_at: str
    imports: List[str]
    methods: List[str]
    file_size: int
    line_count: int


@dataclass
class ValidationResult:
    """Bot validation results."""
    syntax_valid: bool
    has_required_methods: bool
    has_docstrings: bool
    line_count: int
    size_check: str
    errors: List[str]


@dataclass
class GenerationResult:
    """Complete bot generation result."""
    success: bool
    bot_file: str
    metadata: Dict[str, Any]
    validation: Dict[str, Any]
    next_steps: List[str]


# ============================================================================
# Template Processing
# ============================================================================

class BotTemplateGenerator:
    """Generate bot skeletons from templates with Jinja2 rendering."""

    def __init__(
        self,
        game_name: str,
        template_type: str,
        output_file: Optional[str] = None
    ):
        self.game_name = game_name
        self.template_type = template_type
        self.output_file = output_file
        self.class_name = self._generate_class_name(game_name)
        self.module_name = self._generate_module_name(game_name)

        # Initialize Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def _generate_class_name(self, game_name: str) -> str:
        """Generate PascalCase class name from game name."""
        # Remove special characters and split by spaces/underscores
        words = game_name.replace('-', ' ').replace('_', ' ').split()
        # Capitalize each word
        return ''.join(word.capitalize() for word in words) + 'Mixin'

    def _generate_module_name(self, game_name: str) -> str:
        """Generate snake_case module name from game name."""
        # Convert to lowercase and replace spaces/hyphens with underscores
        name = game_name.lower()
        name = name.replace(' ', '_').replace('-', '_')
        # Remove consecutive underscores
        while '__' in name:
            name = name.replace('__', '_')
        return name.strip('_')

    def load_template(self) -> str:
        """Load Jinja2 template file."""
        template_file = f"{self.template_type}.py.j2"

        try:
            template = self.env.get_template(template_file)
            return template
        except TemplateNotFound:
            raise TemplateNotFoundError(
                f"Template '{template_file}' not found in {TEMPLATES_DIR}"
            )

    def get_template_context(self) -> Dict[str, Any]:
        """Build template context with all variables."""
        return {
            'game_name': self.game_name,
            'class_name': self.class_name,
            'module_name': self.module_name,
            'template_type': self.template_type,
            'generated_at': datetime.now().isoformat(),
            'imports': DEFAULT_IMPORTS,
            'year': datetime.now().year,
        }

    def generate_bot(self) -> str:
        """Generate bot code from template."""
        template = self.load_template()
        context = self.get_template_context()

        # Render template
        bot_code = template.render(**context)

        return bot_code

    def validate_bot(self, bot_code: str) -> ValidationResult:
        """Validate generated bot code."""
        errors = []
        syntax_valid = False
        has_required_methods = False
        has_docstrings = False

        # Check Python syntax
        try:
            tree = ast.parse(bot_code)
            syntax_valid = True

            # Check for required methods
            classes = [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
            if classes:
                class_node = classes[0]
                methods = [node.name for node in class_node.body if isinstance(node, ast.FunctionDef)]

                # Check for at least one public method
                has_required_methods = any(not method.startswith('_') for method in methods)

                # Check for docstrings
                has_docstrings = any(
                    ast.get_docstring(node) is not None
                    for node in class_node.body
                    if isinstance(node, ast.FunctionDef)
                )
            else:
                errors.append("No class definition found")

        except SyntaxError as e:
            syntax_valid = False
            errors.append(f"Syntax error at line {e.lineno}: {e.msg}")

        # Check line count
        lines = bot_code.split('\n')
        line_count = len(lines)

        if line_count < 50:
            size_check = f"{line_count} lines (too small - may be incomplete)"
        elif line_count <= 300:
            size_check = f"{line_count} lines (within target 280-300)"
        else:
            size_check = f"{line_count} lines (exceeds 300 - consider splitting)"

        return ValidationResult(
            syntax_valid=syntax_valid,
            has_required_methods=has_required_methods,
            has_docstrings=has_docstrings,
            line_count=line_count,
            size_check=size_check,
            errors=errors
        )

    def save_bot(self, bot_code: str, output_path: Path) -> BotMetadata:
        """Save bot code to file."""
        # Create parent directory if needed
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Write bot code
        output_path.write_text(bot_code)

        # Extract metadata
        lines = bot_code.split('\n')
        imports = [line for line in lines if line.startswith('import ') or line.startswith('from ')]

        # Extract method names
        try:
            tree = ast.parse(bot_code)
            classes = [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
            methods = []
            if classes:
                class_node = classes[0]
                methods = [
                    node.name
                    for node in class_node.body
                    if isinstance(node, ast.FunctionDef)
                ]
        except SyntaxError:
            methods = []

        return BotMetadata(
            game_name=self.game_name,
            template_type=self.template_type,
            class_name=self.class_name,
            module_name=self.module_name,
            generated_at=datetime.now().isoformat(),
            imports=imports,
            methods=methods,
            file_size=len(bot_code),
            line_count=len(lines)
        )

    def get_output_path(self, output_dir: Path) -> Path:
        """Determine output file path."""
        if self.output_file:
            return output_dir / self.output_file
        else:
            return output_dir / f"{self.module_name}.py"

    def get_next_steps(self, output_path: Path) -> List[str]:
        """Generate contextual next steps."""
        steps = [
            f"Review generated bot at {output_path}",
            "Implement helper methods marked with 'TODO'",
            "Add template images to templates/ directory",
            "Test bot with device connection",
            "Update GUI metadata (category, label)",
            "Add comprehensive docstrings",
            "Register bot in game's __init__.py",
        ]

        if self.template_type == "daily-quest":
            steps.append("Implement quest completion detection")
        elif self.template_type == "arena":
            steps.append("Configure opponent selection strategy")
        elif self.template_type == "fishing":
            steps.append("Implement fishing timing algorithm")

        return steps


# ============================================================================
# CLI
# ============================================================================

@click.command()
@click.option(
    '--game-name',
    required=True,
    help='Name of the game/bot (e.g., "My Game", "Arena Bot")'
)
@click.option(
    '--template',
    type=click.Choice(list(TEMPLATE_TYPES.keys())),
    default='base',
    help='Template type to use for generation'
)
@click.option(
    '--output-file',
    help='Output filename (default: auto-generated from game name)'
)
@click.option(
    '--output-dir',
    type=click.Path(),
    default='.',
    help='Output directory (default: current directory)'
)
@click.option(
    '--json',
    'output_json',
    is_flag=True,
    help='Output results in JSON format'
)
@click.option(
    '--dry-run',
    is_flag=True,
    help='Generate but do not save to file'
)
def main(
    game_name: str,
    template: str,
    output_file: Optional[str],
    output_dir: str,
    output_json: bool,
    dry_run: bool
):
    """
    Generate bot skeleton from template with game-specific patterns.

    Examples:
        uv run adb_bot_generator.py --game-name "My Game" --template daily-quest
        uv run adb_bot_generator.py --game-name "Arena Bot" --template arena --json
        uv run adb_bot_generator.py --game-name "Fishing Bot" --template fishing --output-file custom_bot.py
    """
    try:
        # Initialize generator
        generator = BotTemplateGenerator(game_name, template, output_file)

        # Generate bot code
        bot_code = generator.generate_bot()

        # Validate bot
        validation = generator.validate_bot(bot_code)

        if not validation.syntax_valid:
            raise InvalidSyntaxError(
                f"Generated bot has invalid syntax: {', '.join(validation.errors)}"
            )

        # Determine output path
        output_path = generator.get_output_path(Path(output_dir))

        # Save bot (unless dry run)
        if not dry_run:
            metadata = generator.save_bot(bot_code, output_path)
        else:
            # Create metadata without saving
            lines = bot_code.split('\n')
            imports = [line for line in lines if line.startswith('import ') or line.startswith('from ')]
            metadata = BotMetadata(
                game_name=game_name,
                template_type=template,
                class_name=generator.class_name,
                module_name=generator.module_name,
                generated_at=datetime.now().isoformat(),
                imports=imports,
                methods=[],
                file_size=len(bot_code),
                line_count=len(lines)
            )

        # Get next steps
        next_steps = generator.get_next_steps(output_path)

        # Build result
        result = GenerationResult(
            success=True,
            bot_file=str(output_path),
            metadata=asdict(metadata),
            validation=asdict(validation),
            next_steps=next_steps
        )

        # Output results
        if output_json:
            click.echo(json.dumps(asdict(result), indent=2))
        else:
            click.echo("\n" + "=" * 70)
            click.echo(f"ADB Bot Generator: {template.upper()}")
            click.echo("=" * 70)
            click.echo(f"\nGame Name: {game_name}")
            click.echo(f"Class Name: {generator.class_name}")
            click.echo(f"Module Name: {generator.module_name}")
            click.echo(f"Template: {template}")
            click.echo(f"Output: {output_path}")
            click.echo(f"Mode: {'DRY RUN' if dry_run else 'SAVED'}")

            click.echo(f"\nValidation:")
            click.echo(f"  Syntax: {'✅' if validation.syntax_valid else '❌'}")
            click.echo(f"  Required Methods: {'✅' if validation.has_required_methods else '❌'}")
            click.echo(f"  Docstrings: {'✅' if validation.has_docstrings else '❌'}")
            click.echo(f"  Size: {validation.size_check}")

            if validation.errors:
                click.echo(f"\nErrors:")
                for error in validation.errors:
                    click.echo(f"  ❌ {error}")

            click.echo(f"\nNext Steps:")
            for i, step in enumerate(next_steps, 1):
                click.echo(f"  {i}. {step}")

            click.echo("=" * 70)

        sys.exit(0)

    except TemplateNotFoundError as e:
        error_msg = str(e)
        if output_json:
            click.echo(json.dumps({
                "success": False,
                "error": error_msg,
                "exit_code": 2
            }, indent=2))
        else:
            click.echo(f"\n❌ Error: {error_msg}", err=True)
            click.echo(f"\nAvailable templates:", err=True)
            for tpl, desc in TEMPLATE_TYPES.items():
                click.echo(f"  - {tpl}: {desc}", err=True)
        sys.exit(2)

    except InvalidSyntaxError as e:
        error_msg = str(e)
        if output_json:
            click.echo(json.dumps({
                "success": False,
                "error": error_msg,
                "exit_code": 3
            }, indent=2))
        else:
            click.echo(f"\n❌ Error: {error_msg}", err=True)
        sys.exit(3)

    except Exception as e:
        error_msg = f"Bot generation failed: {str(e)}"
        if output_json:
            click.echo(json.dumps({
                "success": False,
                "error": error_msg,
                "exit_code": 1
            }, indent=2))
        else:
            click.echo(f"\n❌ Error: {error_msg}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
