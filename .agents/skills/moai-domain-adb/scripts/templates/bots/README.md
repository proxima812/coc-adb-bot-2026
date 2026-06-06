# ADB Bot Templates

Jinja2 templates for generating game bot skeletons with the ADB Bot Generator.

## Available Templates

### 1. **base.py.j2**
Basic bot template with core structure.
- Main entry point
- Initialization logic
- Helper method stubs
- State tracking
- Cleanup logic

**Use for**: Custom bots, unique game modes

### 2. **arena.py.j2**
PvP/Arena battle automation.
- Arena navigation
- Opponent selection
- Battle execution
- Reward collection
- Bonus attempt handling

**Use for**: Arena, PvP, competitive battles

### 3. **daily-quest.py.j2**
Daily quest/mission automation.
- Quest menu navigation
- Quest type detection
- Objective completion
- Reward claiming
- Multiple quest types support

**Use for**: Daily quests, missions, objectives

### 4. **fishing.py.j2**
Fishing minigame automation.
- Fishing location navigation
- Cast timing
- Bite detection
- Hook mechanics
- Reeling pattern
- Bait management

**Use for**: Fishing, timing-based minigames

### 5. **dungeon.py.j2**
Dungeon crawler automation.
- Floor progression
- Room navigation
- Enemy battles
- Treasure collection
- Boss battles

**Use for**: Dungeons, towers, labyrinth

### 6. **farming.py.j2**
Resource farming automation.
- Stage selection
- Energy management
- Quick clear/sweep
- Auto-battle
- Efficiency tracking

**Use for**: Material farming, exp grinding

### 7. **guild.py.j2**
Guild activities automation.
- Guild donations
- Guild boss battles
- Guild quests
- Reward collection

**Use for**: Guild/clan activities, social features

## Template Variables

All templates support these Jinja2 variables:

- `{{ game_name }}` - Display name of the bot
- `{{ class_name }}` - PascalCase class name (auto-generated)
- `{{ module_name }}` - snake_case module name (auto-generated)
- `{{ template_type }}` - Template type used
- `{{ generated_at }}` - ISO timestamp of generation
- `{{ imports }}` - List of import statements
- `{{ year }}` - Current year

## Usage

Generate a bot using `adb_bot_generator.py`:

```bash
# Basic bot
uv run adb_bot_generator.py --game-name "My Game" --template base

# Arena bot with JSON output
uv run adb_bot_generator.py --game-name "Arena Bot" --template arena --json

# Daily quest bot with custom filename
uv run adb_bot_generator.py --game-name "Dailies" --template daily-quest --output-file my_dailies.py

# Fishing bot dry run (preview only)
uv run adb_bot_generator.py --game-name "Auto Fisher" --template fishing --dry-run
```

## Customization Guide

### 1. Add New Template

Create a new `.j2` file in this directory:

```python
# my_template.py.j2
"""{{ game_name }} Custom Bot.

Generated: {{ generated_at }}
"""

{{ imports | join('\n') }}
from adb_auto_player.games.afk_journey.base import AFKJourneyBase

class {{ class_name }}(AFKJourneyBase):
    """{{ game_name }} automation bot."""

    # Your template code here
```

### 2. Update Generator

Add template to `TEMPLATE_TYPES` in `adb_bot_generator.py`:

```python
TEMPLATE_TYPES = {
    # ...
    "my_template": "My custom template description",
}
```

### 3. Test Template

```bash
uv run adb_bot_generator.py --game-name "Test" --template my_template --dry-run
```

## Template Best Practices

1. **TODO Comments**: Mark customization points with `# TODO:`
2. **Docstrings**: Every method should have a docstring
3. **Type Hints**: Use type hints for parameters and returns
4. **Error Handling**: Wrap risky operations in try/except
5. **Logging**: Use appropriate log levels (info, debug, warning, error)
6. **Constants**: Define game-specific constants at class level
7. **Helper Methods**: Prefix private methods with `_`
8. **Sections**: Use comment separators for organization

## Generated Bot Structure

All bots follow this structure:

```python
# 1. Module docstring
# 2. Imports
# 3. Class definition
# 4. Main command method (@register_command)
# 5. Section 1: Navigation/Setup
# 6. Section 2: Main Logic
# 7. Section 3: Helper Methods
# 8. Section 4: State Management
```

## Validation

Generated bots are automatically validated for:

- ✅ Valid Python syntax
- ✅ Class definition present
- ✅ Public methods (not just helpers)
- ✅ Docstrings present
- ✅ Line count (target 280-300)

## Support

For issues or questions:
- Review generated bot's TODO comments
- Check ADB Auto Player documentation
- Reference existing game bots in `src-tauri/src-python/adb_auto_player/games/`

---

**Version**: 1.0.0
**Last Updated**: 2025-12-01
