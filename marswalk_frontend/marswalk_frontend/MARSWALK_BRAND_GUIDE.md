# MARSWALK — Brand & UI Reference

**Reference baseline:** original MARSWALK planetary field-map frontend, prototype v0.3  
**Source reviewed:** `marswalk_frontend/styles.css`, `index.html`, and `README.md`  
**Purpose:** reusable visual reference for future MARSWALK pages, tools, and prototypes.

> This guide describes the original field-map identity. It does not use the later cinematic home-page experiments as its visual baseline.

---

## 1. Brand identity

- **Name:** MARSWALK
- **Product description in the original app:** “A field atlas for Mars.”
- **Product character:** a restrained scientific mapping tool; editorial rather than promotional; practical, calm, and data-led.
- **Visual idea:** warm paper-like surfaces and muted field colours paired with a deep space map canvas.

### Brand principles

1. **The map is the main event.** Interface elements should support exploration without competing with the planetary view.
2. **Use restraint.** Prefer a few clear controls, thin dividers, and purposeful information over stacks of cards and decorative effects.
3. **Make scientific information legible.** Keep layer names, units, coordinates, source names, coverage limits, and attribution clear.
4. **Use real planetary data imagery.** Do not replace scientific imagery with cartoon planets or decorative pseudo-data.
5. **Distinguish evidence from interpretation.** Label measured observations, derived analyses, and predictions separately.

---

## 2. Core colour palette

These are the exact CSS custom-property values in the original `styles.css`.

| Token | HEX | Intended use |
|---|---|---|
| `--paper` | `#F1EEE5` | Main light panel surface; warm ivory |
| `--paper-deep` | `#E6E2D8` | Deeper paper surface / secondary light surface |
| `--ink` | `#252923` | Primary text on light surfaces |
| `--muted` | `#777C73` | Secondary text |
| `--soft` | `#A3A69C` | Quiet metadata and tertiary text |
| `--line` | `#D9D7CF` | Light-surface separators |
| `--green` | `#536B5B` | Primary action and main interface accent |
| `--green-dark` | `#405647` | Darker green accent / active states |
| `--rust` | `#BD7959` | Mars/terrain accent; warm highlight |
| `--space` | `#05090D` | Main map canvas / deep-space background |

### Supporting colours found in the stylesheet

These are used in individual components rather than defined as global tokens.

| HEX | Existing role / pattern |
|---|---|
| `#D2A184` | The italic “M” inside the circular brand mark |
| `#91A794` | Keyboard-focus outline |
| `#B79A68` | Neutral / waiting map-status indicator |
| `#8EA98F` | Live / success status indicator |
| `#C57F6C` | Error status indicator |
| `#F4F0E5` | Bright text on dark controls |
| `#30372F` | Panel heading text |
| `#3A4239` | Layer and place primary text |
| `#858B80` | Secondary panel labels |

### Colour-use rules

- Use **`#05090D`** for the full-screen map environment.
- Use **`#F1EEE5`** for floating panels and light information surfaces.
- Use **`#252923`** for text on light surfaces.
- Use **`#536B5B`** for the main action colour; use `#405647` for darker green emphasis.
- Use **`#BD7959`** sparingly for warm Mars-related emphasis, not as a full-screen background.
- Keep status colours semantic: green for live/success, amber for waiting/neutral, muted red for errors.
- Avoid adding unrelated bright accent colours (especially neon purple, pink, or electric blue).

---

## 3. Typography

### Font families

| Role | Font stack from the original CSS | Use |
|---|---|---|
| Interface sans-serif | `Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif` | Navigation, controls, labels, body text, buttons |
| Editorial serif | `Georgia, "Times New Roman", serif` | Panel headings, map readout, coordinate labels, metric figures, occasional emphasis |

**Implementation note:** `Inter` is named in the CSS stack, but the original `index.html` does not load Inter from a web font or local font file. A browser without Inter installed will use its next available system fallback. For consistent rendering across devices, load or bundle Inter in a future implementation; keep Georgia as the serif pairing.

### Type hierarchy observed in the original interface

| Element | Original styling / scale |
|---|---|
| Brand wordmark | 12px, weight 650, uppercase, letter spacing `.085em` |
| Panel title | Georgia, 24px, weight 400, line-height 1.05 |
| Dialog title | Georgia, 27px, weight 400 |
| Map readout | Georgia, 12px |
| Main panel / card labels | Usually 10–11px, medium weight |
| Supporting descriptions | Usually 9–10px |
| Metadata / credits | 7–9px |
| Route metric | Georgia, 20px, weight 400 |

### Typography rules for future screens

- Use Inter (or its system fallback) for functional UI.
- Use Georgia for occasional editorial headings and selected scientific readouts; do not make every heading serif.
- Prefer regular or medium weights. Reserve heavier weights for short labels and important values.
- Use uppercase and letter spacing only for compact eyebrows, status labels, or the wordmark—not for paragraphs.
- Keep small metadata concise. Important instructions and scientific explanations must remain comfortably readable; do not force all future body copy into 9px text just because the map controls are compact.

---

## 4. Wordmark and brand mark

The original interface uses a simple text-and-symbol lockup:

- A **circular outlined mark** containing an italic serif capital **M**.
- Mark size: **25 × 25px** in the original map header.
- Mark outline: `rgba(241, 238, 229, 0.45)`.
- Mark letter colour: `#D2A184`.
- Mark letter: Georgia, 14px, italic.
- Wordmark: **MARSWALK**, uppercase, Inter/system sans, 12px, weight 650, letter spacing `.085em`.
- Wordmark and mark are placed side by side with a 9px gap.

Keep the wordmark simple. Do not add a complex mascot, gradient emblem, bevel, or 3D logo treatment.

---

## 5. Layout and component language

### Overall composition

- Full-viewport, map-first canvas.
- Floating controls sit over the map rather than occupying permanent dashboard columns.
- Panels open only when requested and use a warm light surface for contrast against the dark map.
- Preserve negative space around the map and keep the control count low.

### Controls

| Component | Original measurement / treatment |
|---|---|
| Floating icon button | 39 × 39px, circular |
| Floating icon stroke | 1.55px, rounded line caps and joins |
| Panel corner radius | 7px |
| Small action / input radius | 4–5px |
| Close control | 27 × 27px, circular, transparent |
| Layer swatch | 36 × 30px, 3px radius |
| Panel heading padding | 19px 20px 14px |
| Panel content padding | 15px 20px 19px |

### Borders and surfaces

- Prefer thin, low-contrast borders over thick outlines.
- Light-panel dividers use subdued olive-grey lines, commonly around 11–16% opacity.
- Floating panels use warm ivory (`#F1EEE5`) with slight translucency and restrained blur.
- Shadows are used to lift panels from the map, not as a decorative effect.
- Buttons are compact, mostly rectangular with 4px corners; icon controls are circular.

### Icons

- Use simple outline icons with consistent stroke weight.
- Keep icons transparent/no-fill where possible.
- On the dark canvas, use a warm off-white icon colour with enough contrast to remain visible.
- Tooltips should provide the label; avoid adding a text label beside every icon.

---

## 6. Motion and interaction

- Keep transitions short and functional (the original panel transition is approximately 160ms).
- Use subtle hover and active states; avoid springy, playful, or attention-seeking animations.
- The map should remain the visual focus; controls should not animate unless the interaction benefits from it.
- Preserve clear focus states for keyboard users (original focus outline: `#91A794`).

---

## 7. Voice and content style

The original product language is concise and scientific, with plain labels such as “Layers”, “Data catalogue”, “Places”, “Traverse”, “Distance”, and “Waypoints”.

Use:
- Direct, descriptive labels.
- Real dataset and instrument names.
- Units beside numerical measurements.
- Source attribution close to the displayed data.
- Explicit notes about coverage and limitations.

Avoid:
- Inflated marketing claims.
- Calling a route “safe” unless a validated safety model supports that claim.
- Presenting local rover measurements as global or live conditions.
- Generic AI-style filler copy and decorative statistics.

---

## 8. Do / don't checklist

### Do

- Keep the map dominant.
- Pair warm paper panels with the deep-space canvas.
- Use muted olive green and restrained terracotta.
- Use Inter/system sans for UI and Georgia for editorial contrast.
- Use thin borders, small radii, and deliberate spacing.
- Keep source names, credits, units, and caveats visible.

### Don't

- Add purple-pink gradients, neon glows, or glass panels everywhere.
- Fill the screen with cards or permanently open sidebars.
- Use oversized promotional typography inside the scientific map UI.
- Mix many unrelated accent colours.
- Use cartoon planets or fabricated map textures in place of real Mars data.
- Hide uncertainty, data gaps, or source limitations.

---

## 9. Reusable CSS tokens

Copy this block into the `:root` section of future MARSWALK stylesheets.

```css
:root {
  color-scheme: dark;

  /* Core surfaces */
  --paper: #f1eee5;
  --paper-deep: #e6e2d8;
  --space: #05090d;

  /* Text */
  --ink: #252923;
  --muted: #777c73;
  --soft: #a3a69c;
  --line: #d9d7cf;

  /* Brand accents */
  --green: #536b5b;
  --green-dark: #405647;
  --rust: #bd7959;

  /* Functional states */
  --focus: #91a794;
  --status-neutral: #b79a68;
  --status-success: #8ea98f;
  --status-error: #c57f6c;
  --brand-mark: #d2a184;

  /* Typography */
  --sans: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
  --serif: Georgia, "Times New Roman", serif;
}
```

---

## 10. Source and scope notes

- This guide was extracted from the original MARSWALK field-map frontend's `styles.css` and checked against its `index.html` and `README.md`.
- Core palette values and font stacks above are exact values from the source CSS.
- The “brand principles”, content rules, and future-screen guidance are design-system recommendations based on how the original interface is structured; they are not separate assets or formal rules embedded in the code.
- This guide is for the **field-map application identity**. The later experimental cinematic home page is a separate presentation concept and should inherit this palette and typography rather than replace them.
