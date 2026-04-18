# IconForge Vector-Ready Pack

This pack translates the Control Hall and IconForge concept into implementation-ready specs.

## Source Of Truth
- assets/icons/iconforge_production_sheet.json
- assets/ui/bossforge_theme_tokens.json

## Rendering Constraints
- Stroke width: 1.75 px
- Stroke caps: round
- System icons: circular frame
- File types: rounded-square frame
- Folder icons: folder silhouette frame
- Layer model:
  1. Static geometry
  2. Glow layer
  3. Motion layer (optional)

## Export Targets
- SVG master for each icon id
- ICO variants for Windows sizes: 16, 24, 32, 48, 64, 128, 256
- PNG fallback for docs/previews

## Windows Consumption Targets
- Tray icon states
- Folder icon overlays
- File extension associations
- Application shell overrides

## Notes
- Keep no-fill line-art baseline for idle states.
- Active/alert states may add glow, gradient, or accent fills.
- BossGate travel state should use blue-gold accent blend while retaining goldline geometry.
