# CLI Plugins

BossForgeOS supports drop-in CLI plugins for bforge.

## Plugin Locations

- Repo plugins: .\plugins\cli
- User plugins: %USERPROFILE%\BossCrafts\cli\plugins

If both locations contain plugin files with the same path identity, the first loaded instance wins.

## Plugin Contract

Each plugin file must expose:

- register(subparsers)

Inside register, add one or more argparse subcommands.

## Example

See sample plugin:

- .\plugins\cli\forge_echo.py

Run:

- python -m core.bforge forge-echo "hello"
- python -m core.bforge plugins
