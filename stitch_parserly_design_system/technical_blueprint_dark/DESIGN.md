---
name: Technical Blueprint Dark
colors:
  surface: '#131314'
  surface-dim: '#131314'
  surface-bright: '#3a393a'
  surface-container-lowest: '#0e0e0f'
  surface-container-low: '#1c1b1c'
  surface-container: '#201f20'
  surface-container-high: '#2a2a2b'
  surface-container-highest: '#353436'
  on-surface: '#e5e2e3'
  on-surface-variant: '#bacbb6'
  inverse-surface: '#e5e2e3'
  inverse-on-surface: '#313031'
  outline: '#859582'
  outline-variant: '#3c4b3b'
  surface-tint: '#13e45d'
  primary: '#f5fff0'
  on-primary: '#003911'
  primary-container: '#45ff73'
  on-primary-container: '#007229'
  inverse-primary: '#006e27'
  secondary: '#c5c0ff'
  on-secondary: '#2600a1'
  secondary-container: '#3e23ce'
  on-secondary-container: '#b6b0ff'
  tertiary: '#f0fff8'
  on-tertiary: '#00382c'
  tertiary-container: '#55f8d2'
  on-tertiary-container: '#00705b'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#6bff84'
  primary-fixed-dim: '#13e45d'
  on-primary-fixed: '#002107'
  on-primary-fixed-variant: '#00531c'
  secondary-fixed: '#e4dfff'
  secondary-fixed-dim: '#c5c0ff'
  on-secondary-fixed: '#140067'
  on-secondary-fixed-variant: '#3b1fcb'
  tertiary-fixed: '#59fcd5'
  tertiary-fixed-dim: '#2fdfba'
  on-tertiary-fixed: '#002019'
  on-tertiary-fixed-variant: '#005141'
  background: '#131314'
  on-background: '#e5e2e3'
  surface-variant: '#353436'
  neon-acid: '#45FF73'
  electric-violet: '#6D5DFC'
  drafting-paper: '#F4F1EA'
  slate-graphite: '#1B1B1D'
  technical-line: '#3E3948'
  warning-amber: '#F0B347'
  critical-coral: '#FF684F'
typography:
  display-xl:
    fontFamily: Bahnschrift
    fontSize: 48px
    fontWeight: '600'
    lineHeight: '1.0'
    letterSpacing: -0.02em
  display-lg:
    fontFamily: Bahnschrift
    fontSize: 36px
    fontWeight: '600'
    lineHeight: '1.1'
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Bahnschrift
    fontSize: 24px
    fontWeight: '600'
    lineHeight: '1.3'
    letterSpacing: '0'
  body-base:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.5'
  body-sm:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: '1.4'
  body-bold:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '600'
    lineHeight: '1.4'
  label-caps:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '700'
    lineHeight: '1.2'
    letterSpacing: 0.05em
  code-mono:
    fontFamily: jetbrainsMono
    fontSize: 12px
    fontWeight: '400'
    lineHeight: '1.6'
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  unit: 4px
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 32px
  gutter: 28px
  container-max: 1280px
---

## Brand & Style

The visual identity of this design system is rooted in the aesthetic of a high-tech, industrial HUD (Heads-Up Display). It evokes a sense of tactical precision, professional utility, and speed. The interface is characterized by a "blueprint" atmosphere, utilizing mathematical grid patterns and volumetric light cones to create depth within a deep, dark-mode environment. 

The design style is a hybrid of **Minimalism** and **Corporate Modern**, infused with **high-contrast neon accents**. It prioritizes extreme geometric discipline over organic shapes. Every element is designed to feel like a piece of high-precision electronic instrumentation, using sharp borderlines and subtle glowing effects to signal interactivity and system status. The emotional response is one of reliability, technical authority, and modern efficiency.

## Colors

The palette is built on a "Soot Night" foundation, using layered dark grays and purples to establish surface hierarchy. 

- **Primary (Neon Acid Green):** Used for critical calls to action, active states, and successful verifications. It represents energy and system "go" signals.
- **Secondary (Electric Violet):** Provides brand grounding and volumetric depth through radial background gradients and glowing shadows.
- **Neutral:** A range of soot blacks and slate grays that mimic technical drafting ink and graphite surfaces.
- **Typography:** Primary text uses "Drafting Paper" off-white to reduce eye strain compared to pure white, while maintaining high contrast.
- **Semantic Accents:** Amber is reserved for warnings, and Coral is used for critical alerts or high-priority recommendations.

## Typography

The typographic system uses a functional pairing to balance industrial character with high readability.

- **Headlines:** Use **Bahnschrift** (or a similar DIN-inspired geometric sans-serif). These levels should feature tight tracking and line-heights to maintain a solid visual "block" characteristic of technical drawings.
- **Body & Labels:** Use **Inter** for its exceptional clarity on screens. Body text requires slightly relaxed line-heights to ensure long-form analysis is legible against the dark background.
- **Technical Data:** **JetBrains Mono** is used for any code snippets, API strings, or metadata to reinforce the developer-centric, technical atmosphere.
- **Mobile Scaling:** For mobile devices, `display-xl` and `display-lg` should scale down by 20% to prevent overflow while maintaining weight.

## Layout & Spacing

The layout is governed by a strict **8px baseline grid** (with a 4px sub-unit for fine adjustments). 

- **Grid System:** A 12-column fluid grid is used for the main content area, with a maximum width of 1280px. Gutters are fixed at 28px (`gap-7`) to provide distinct breathing room between high-density data panels.
- **Structure:** Content should be grouped into cards or panels that align with the background blueprint grid (76px cells).
- **Responsive Adaptations:** 
  - **Desktop:** Multi-column layouts (e.g., 60/40 splits for analysis reports).
  - **Tablet:** 12-column layouts reflow to stacked vertical groups or single columns with 24px margins.
  - **Mobile:** Margins shrink to 16px. All interactive targets (buttons/inputs) maintain a minimum height of 48px to satisfy touch ergonomics.

## Elevation & Depth

Hierarchy is established through **Tonal Layering** and **High-Contrast Outlines** rather than traditional shadows.

- **Surface Tiers:** The root background is the darkest (`#0B0B0C`). Elevated cards use `#1B1B1D`. Nested widgets or secondary controls use `#28262D`.
- **Borders:** Every container utilizes a razor-thin (1px) hairline border (`#3E3948`). In active or focused states, these borders transition to the neon primary color with a subtle outer glow.
- **Visual Depth:** Atmospheric depth is achieved via semi-transparent radial gradients of Electric Violet and Neon Green in the background, creating the illusion of backlighting behind the "blueprint" grid.
- **Backdrop Blurs:** Modals and overlays must use a `backdrop-blur-md` (8px-12px) with a 75% opacity dark mask to isolate focus without losing the context of the underlying grid.

## Shapes

The shape language is "Soft-Geometric." To maintain the technical blueprint aesthetic, avoid large radii. 

- **Standard Corners:** Most UI components (cards, inputs, buttons) use a `0.375rem` (6px) radius. This provides just enough softening to feel modern without losing the "engineered" precision of the layout.
- **Small Elements:** Tooltips and tags use `0.25rem`.
- **Exceptions:** Status indicators or avatars may use full pill shapes (rounded-full) to provide a visual counterpoint to the otherwise rigid grid.

## Components

- **Primary Buttons:** High-voltage neon background (`#45FF73`) with ink-black text. On hover, they should "glow" brighter and shift slightly upward (-2px) to simulate a physical spring-loaded switch.
- **Inputs:** Styled as deep-black wells (`#0B0B0C`) with a slate-purple border. Focused states trigger a dual-layer halo: a 2px dark gap followed by a 5px neon green glow.
- **Dropzones:** Use a double-pixel dashed border and a 36px blueprint grid background. Drag-over states should flood the container with a 10% opacity green tint.
- **Cards/Panels:** These are the primary organizational units. They must have a hairline border and a slightly elevated gray background (`#1B1B1D`). 
- **Score Meters:** Use conic gradients for circular progress, paired with massive Bahnschrift numerals to emphasize data-driven results.
- **Priority Badges:** High-contrast semantic colors (Coral, Amber, Green) used as low-opacity backgrounds with high-opacity text and icons for categorizing analysis results.