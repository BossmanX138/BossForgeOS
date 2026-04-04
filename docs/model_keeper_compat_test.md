# Model-Keeper Compatibility Test

This script verifies that the model_keeper compatibility layer responds to status_ping and appears in the state view.

## Usage

1. Run the following command:

    bforge model-keeper status

2. Expected output:

- The command emits a status_ping to model_keeper.
- The state for model_keeper is printed, showing status 'alive' and the compatibility profile.

## Example Output

```
model_keeper state:
{
  "service": "model_keeper",
  "ok": true,
  "status": "alive",
  "profile": {
    "id": "model_keeper",
    "name": "Model Keeper (Compat)",
    "version": "0.1.0",
    "description": "Compatibility layer for model_keeper in BossForgeOS."
  }
}
```

If you see this, the compatibility layer is functioning as required by the delegated work queue.
