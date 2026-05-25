# Diagrams

Source files for the four diagrams referenced from the README and
architecture docs. Each diagram is also exported as a PNG into
`docs/images/` so the README renders without GitHub having to support
the source format.

## Files

| File                              | Purpose                                                          |
|-----------------------------------|------------------------------------------------------------------|
| `system-architecture.mmd`         | Hero diagram: components and how they connect                    |
| `ingestion-flow.mmd`              | Sequence: upload → parse → chunk → embed → index                 |
| `query-flow.mmd`                  | Sequence: question → retrieve → fuse → generate → stream + cite  |
| `deployment-topology.mmd`         | AWS production deployment shape                                  |

The Mermaid sources are committed for editability; the PNGs in
`docs/images/` are what the README references. Re-render with:

```bash
# Mermaid CLI (npm)
npm install -g @mermaid-js/mermaid-cli
mmdc -i docs/diagrams/system-architecture.mmd -o docs/images/system-architecture.png -w 1600 -b transparent
```

Or open the `.mmd` files in <https://mermaid.live/> for an interactive
editor.

## When to use Excalidraw instead

Mermaid is good for boxes-and-arrows. The README's hero diagram looks
more polished as a hand-styled Excalidraw export. To replace
`docs/images/system-architecture.png` with an Excalidraw version:

1. Open <https://excalidraw.com/>
2. Recreate the layout from `system-architecture.mmd` (use the same
   labels and arrow directions)
3. Export as PNG with a transparent background and 2x scaling
4. Save to `docs/images/system-architecture.png` (replace existing)
