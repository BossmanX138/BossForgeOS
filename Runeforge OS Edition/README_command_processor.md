# WindowsWorld Command Processor

The command processor (`command_processor.py`) ties modular Windows automation scripts into a closed control loop.

## Table of Contents

- [How It Works](#how-it-works)
- [Files](#files)
- [Voice-First Usage](#voice-first-usage)
- [Supported Voice Intents](#supported-voice-intents)
- [Direct Agent Voice Routing](#direct-agent-voice-routing)
- [Next Steps](#next-steps)

## How It Works

- **Observation:** Calls scripts like `system_info.py` and `window_management.py` to gather current state.
- **User Goal:** Prompts for task or goal.
- **Action Decision:** Currently accepts a JSON action from the user (can be replaced with model logic).
- **Action Execution:** Calls the modular script mapped by the action schema.
- **Loop:** Repeats observation, action, and logging until complete or stopped.
- **Logging:** Stores each step in JSONL episode logs for replay and debugging.

## Files

- `command_processor.py`: Main command-processing loop.
- `action_schema.json`: Allowed actions and parameters.
- `observation_format.json`: Example observation structure.
- `audio_dictation.py`: Voice command interpreter and executor.
- `file_lock.py`: Command-code lock state for protected file access.
- `permission_lease.py`: Timed and indefinite action grants.

## Voice-First Usage

- Activation moniker is required: `Runeforge` (shorthand `runforge` accepted).
- Parse spoken text without executing:
  - `python "Runeforge OS Edition/audio_dictation.py" --text "Runeforge, lock file \"C:/AgentSandbox/Downloads/tool.zip\""`
- Execute voice command text directly:
  - `python "Runeforge OS Edition/audio_dictation.py" --text "Runeforge lock file \"C:/AgentSandbox/Downloads/tool.zip\"" --execute --command-code YOUR_CODE`
- Listen from microphone once and execute:
  - `python "Runeforge OS Edition/audio_dictation.py" --execute --command-code YOUR_CODE`

## Supported Voice Intents

- `lock file "PATH"`
- `unlock file "PATH"`
- `unblock file "PATH"`
- `list file locks`
- `open app APP_OR_COMMAND`
- `close app PROCESS_NAME`
- `open file "PATH"`
- `list folder "PATH"`
- `open website URL`
- `set volume to N`
- `mute volume`
- `play SONG_OR_ALBUM_OR_ARTIST`

## Direct Agent Voice Routing

- `codemage`
- `runeforge talk to me`
- `BossForge register voice alias emberforge to agent custom_agent`
- `BossForge record alias for agent custom_agent` (then speak alias phrase on next capture)

## Next Steps

- Integrate model-based action selection.
- Expand observation and action coverage.
- Add stronger error handling, safety, and high-risk confirmations.

This is the core command-processing layer: safe, modular, and extensible OS control.
