# UI/UX Audit: DiaBeates Design & AI-Generated Tells

## 1. Decorative Visual Gimmicks & Animations
- **Rotating Conic-Gradient Borders**: `.animated-border-card` and `.scan-light-card` with rotating pseudo-elements (`conic-gradient`), creating artificial high-tech glow on card edges.
- **Glassmorphism & Backdrop Blurs**: Excessive `backdrop-blur-md`, `rgba(255,255,255,0.18)` semi-transparent surfaces on cards, modals, and tooltips.
- **Floating Ambient Orbs**: Four blurred spherical div layers (`floating-orb-1`, `floating-orb-2`, `floating-orb-3`, `floating-glow`) positioned with 3xl blur in the hero section.
- **Full-Screen Page Transition Overlay**: Blocking transition overlay with breathing/pulsing logo (`logoBreath`, `logoGlowPulse`, `pageReveal`) triggered on all link clicks via `startTransition`.
- **Ambient Background Video**: Video background (`medical_workers.mp4`) looping behind page content.
- **Vibrant Electric Cyan & Gradient Backgrounds**: Heavy use of electric cyan (`#03bdcd`, `#37f6f2`), gradients (`gradient-primary`, `gradient-hero`, `gradient-card`, `text-gradient`), and high-saturation badge pills.

## 2. Layout & Structural Clichés
- **Centered Hero with Dual CTAs**: Floating 3xl rounded hero box with centered text and competing primary/secondary action buttons.
- **Identical 4-Card Complication Grid**: Four repetitive dark-teal rounded cards with identical layout and decorative icons on `home.html`.
- **3-Column Generic Icon Feature Grid**: Cliché 3-card feature columns with icon containers and buzzword titles.
- **Circular SVG Gauge Dials**: Large circular progress rings in `result.html` representing probabilities, which obscure precise clinical risk comparison.
- **Uniform Large Pill Radii & Deep Shadows**: Ubiquitous `rounded-3xl`, `rounded-2xl`, and heavy multi-layered box-shadows (`shadow-[0_25px_...], shadow-xl`).

## 3. Typography & Styling Tells
- **SaaS Font Stack**: `Outfit` / `Plus Jakarta Sans` / `Inter` loaded from Google Fonts instead of an editorial clinical typography system.
- **Ubiquitous Decorative Icons**: Gratuitous SVG icons beside every title, statistic, card, and button.

## 4. Buzzword & Templated Marketing Copy
- Marketing phrases: *"Predict Diabetes Complications With Real Clinical Data"*, *"Dual-Engine Architecture"*, *"Patient Empowerment"*, *"Zero Medical Jargon"*, *"Actionable Explainability"*, *"Understand your risk before complications advance"*.
- Exclamation marks, hyperbole, and repetitive tech startup phrasing.

---

## Remediation Plan
1. **Self-Host Typography**: Embed WOFF2 fonts for Newsreader (500/600), IBM Plex Sans (400/500/600), and IBM Plex Mono (400/500/600) with tabular figures.
2. **Clinical Editorial Tokens**: Switch to CSS variables for warm paper (`#f6f4ef`), surface (`#fbfaf7`), crisp ink (`#14202b`), muted ink (`#566270`), hairline rules (`#d9d4c9`), deep navy (`#063154`), and restrained teal (`#025f67`).
3. **Structured Editorial Layouts**:
   - Replace hero with asymmetric serif editorial layout and a single clear action.
   - Replace 4-card complication grid with a ruled, structured reference table.
   - Replace circular gauges with a linear ruled clinical scale with explicit 30% and 60% threshold markers.
   - Strip all background animations, conic gradients, orbs, video loops, and transition overlays.
   - Constrain corner radii strictly to 2px/4px, remove shadows, and rely on 1px hairline borders.
4. **Plain-Spoken Clinical Copy**: Replace startup slogans with calm, precise, informative clinical descriptions and direct action-oriented buttons.
