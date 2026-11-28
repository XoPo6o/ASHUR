# ASHUR Pixel Foundry — Universal Pixel-Art Field Manual

**Version:** 1.0  
**Purpose:** a production standard for authored pixel art, procedural generators, AI art direction and visual QA.  
**Scope:** detailed game scenes, characters, architecture, creatures, props, tilesets and UI.  
**North star:** every pixel must have a job. Detail is the result of deliberate shape, light, material and storytelling decisions—not a high count of rectangles or random texture.

This manual synthesizes publicly available lessons and technical discussions. It does not reproduce proprietary course material, paid books, artwork, sprites or palettes. The linked sources remain the authors' work; this document translates general craft principles into rules that ASHUR can implement and test.

---

## 0. The production contract

The renderer must not equate "more operations", "more colors", "larger canvas" or "more noise" with quality.

A finished asset must pass five gates:

1. **Read:** the silhouette, pose and focal hierarchy are clear at native display size.
2. **Form:** light and shadow describe a believable 3D form.
3. **Material:** stone, cloth, metal, skin, wood, glass and foliage do not share one generic texture.
4. **Pixel craft:** edges, curves, clusters, outlines and dithering are intentional.
5. **Scene fit:** scale, perspective, palette, lighting and detail density agree with neighboring assets.

If a gate fails, adding micro-detail is prohibited until the structural problem is fixed.

## 1. Plan before drawing: SPECC+

Every scene or major asset starts with a compact art brief.

- **S — Size:** logical canvas, sprite bounds, pixel grid, intended 1x display size and export scale.
- **P — Perspective:** camera model, horizon, vanishing directions, ground plane and object-facing rules.
- **E — Exposure / light:** key-light direction, fill, bounce, emissive sources, shadow direction and relative intensity.
- **C — Color:** palette families, value hierarchy, hue shifts and contrast budget.
- **C — Composition:** story beat, focal point, silhouette hierarchy, negative space and eye path.
- **+ — Material & scale:** material assignment, surface roughness, texture scale and foreground/midground/background density.

Write these choices into the scene spec. Never rely on an undocumented assumption inside a generator.

### Composition hierarchy

- Thumbnail test first: the scene should read when reduced to a small preview.
- Establish one primary focal subject, one secondary landmark and supporting environment.
- Use large, medium and small shapes; do not give every object equal visual weight.
- Keep the strongest value contrast and sharpest edges near the focal subject.
- Preserve negative space around important silhouettes.
- Use overlap, atmospheric contrast and scale falloff to separate depth planes.
- Detail density should generally rise toward the foreground and focal subject, not remain uniform.

## 2. Pixel grid, resolution and scaling

- Draw on a deliberate logical grid. A larger export is not a substitute for more considered native pixels.
- Choose a base pixel scale for each asset family and keep it consistent in a scene.
- Scale only by integer nearest-neighbour multiples. No blur, bilinear filtering or fractional scaling.
- Do not enlarge a small sprite and pretend it has gained detail. Redraw at the target resolution.
- The intended 1x view is the judge. Zoomed previews are for inspecting clusters, not for deciding readability.
- For dense scenes, prefer several coherent logical scales only when depth or authored style explicitly calls for them; document the exception.
- Do not hard-code one universal canvas maximum. The correct resolution depends on display size, game camera and intended pixel pitch. Enforce a visible pixel grid at actual use size.

## 3. Silhouette and shape construction

Build in this order:

1. gesture / bounding mass;
2. outer silhouette;
3. major internal divisions;
4. planes and volume;
5. material blocks;
6. focal details;
7. restrained texture.

Rules:

- Make the silhouette recognizable in a single flat color.
- Use shape language deliberately: broad stable masses for architecture, tapered rhythm for cloth, angular breaks for stone, controlled curves for organic forms.
- Avoid tangencies where two contours almost touch without clearly overlapping or separating.
- Break repetitive geometry with intentional variation, not random jitter.
- Keep the subject's most characteristic features exaggerated enough to survive at native size.
- For characters, establish head, torso, pelvis, limb direction, hands, feet and costume layers before facial micro-detail.
- For creatures/statues, separate anatomy into readable masses and joints; texture must not hide anatomy.

## 4. Lines, curves and edge control

- Prefer clean pixel staircases with consistent run lengths.
- Common diagonal rhythms (1:1, 1:2, 1:3) are useful starting patterns, not laws for every contour.
- Curves should change their step rhythm gradually; remove accidental doubles, spikes and isolated edge pixels.
- Keep line thickness consistent unless a deliberate taper or perspective change explains it.
- Avoid automatic outlines around every object. Use silhouette outlines, internal contour lines and selective outlines for different jobs.
- Anti-alias only where it improves a specific transition at 1x. Too much AA softens the image and destroys the pixel character.
- Inspect both the whole image and 100% crop. A mathematically tidy edge can still be visually wrong.

## 5. Clusters, texture and pixel economy

A cluster is a connected group of pixels that reads as one intentional shape or value patch.

- Prefer designed clusters over scattered single-pixel noise.
- Every isolated pixel needs a reason: sparkle, eye glint, star, particle, sharp specular or deliberate accent.
- Avoid banding: parallel tone bands that trace the outline and flatten the form.
- Avoid pillow shading: a bright center surrounded by dark rings without regard to the light source.
- Texture must follow the surface form, perspective and material grain.
- Use different cluster sizes: large masses establish form, medium clusters describe planes, tiny clusters provide focal accents.
- Do not distribute detail evenly. Reserve the finest clusters for the focal area.
- Use noise diagnostics as a warning system, not as an aesthetic score: a deliberate star field or metal sparkle can be isolated by design.

### Cluster QA

Report at least:
- isolated pixel count and percentage;
- connected-component size distribution;
- edge staircase irregularities;
- repeated/banded pattern suspicion;
- cluster density by region;
- tiny-cluster concentration outside focal regions.

A warning must include coordinates and a suggested fix. Never auto-delete a pixel solely because it is isolated.

## 6. Palette, value and hue

Build palettes by material families and scene lighting, not by assigning unrelated hex colors to individual primitives.

- Start with a midtone, then design shadow and highlight steps around it.
- Use hue shifting: shadows and highlights can move in hue as well as brightness.
- Maintain a clear value hierarchy between focal subject, supporting objects and background.
- Check grayscale/value separation independently of hue.
- Keep palette small enough to feel coherent, but do not enforce an arbitrary tiny color count on a complex scene.
- Reuse colors across materials when they share lighting; distinguish materials through value structure, edge treatment and texture.
- Use rare saturated/high-value accents as attention markers.
- Palette expansion must be justified by a new material, lighting role or focal need—not by convenience.

### Palette QA

- Build ramps with ordered luminance and intentional hue progression.
- Detect near-duplicate colors and accidental palette drift.
- Measure focal/background contrast.
- Check that shadows do not collapse into one black mass and highlights do not clip into a white blob.
- Offer a color-blind / grayscale preview where useful.

## 7. Lighting and volume

Every scene has a declared key light. Local lights (lanterns, windows, fire, magic) are additional sources, not excuses to ignore the key.

- State direction, softness, color and relative strength of each source.
- Light-facing planes receive the appropriate ramp; occluded planes receive shadow.
- Cast shadows must agree with the source and object-ground relationship.
- Contact shadows anchor objects; ambient occlusion is local and restrained.
- Bounce light should carry color from nearby surfaces and remain weaker than the key unless the scene specifies otherwise.
- Emissive objects need a bright core, controlled falloff and selective reflected light on nearby surfaces.
- Do not use a global glow blur to fake pixel lighting. Use stepped pixel clusters or a dedicated low-resolution light pass.
- Keep lighting layers editable and separate from base material shapes.

## 8. Material language

A material is defined by its shape response, value ramp, edge behavior, texture rhythm and specular response.

| Material | Form and edge | Texture / highlights |
|---|---|---|
| Cut stone / brick | hard planes, chipped corners, bevels | staggered masonry, mortar, sparse cracks, top/left light and bottom/right shade for top-left key |
| Sandstone | broad soft planes, eroded edges | warm hue shifts, pits and strata; low specular |
| Bronze / gold | sharp silhouette, bevelled planes | warm reflected ramps, narrow bright glints, dark creases, patina in recesses |
| Iron | hard edges, cool value ramp | narrow specular streaks, scratches aligned to form |
| Wood | directional plank/grain structure | knots sparingly, seams, end grain, warm/cool plane shifts |
| Cloth | folds radiate from tension points | broad soft clusters, seams, hems, embroidery only at focal scale |
| Leather | rounded straps and creases | muted ramp, edge wear, stitching, low-to-medium sheen |
| Skin | readable planes and anatomy | restrained hue shifts, warm/cool transitions, facial landmarks prioritized |
| Glass | clear silhouette and rim | limited tint, crisp reflections, readable transparency by contrast |
| Water | horizontal / flow-aligned shapes | stepped reflections, dark base, bright broken highlights |
| Foliage | overlapping leaf masses | clustered leaf groups, varied value islands, light on exposed edges |
| Dust / smoke | large soft-edged pixel masses | sparse breakup; never random static |

Do not apply the same noise overlay to every material. The material should remain identifiable without its label.

## 9. Perspective, architecture and environments

- Define a camera convention per scene: side view, top-down, 3/4, isometric, or authored cinematic perspective.
- Establish horizon, ground plane, verticals and vanishing logic.
- Scale objects consistently with depth; distant forms become smaller and less contrasty.
- Architecture is built from structural masses first: foundation, wall plane, openings, supports, roofline, cornice, relief and ornament.
- Repetition must follow a believable construction system: masonry courses, column spacing, arch voussoirs, balcony supports and roof rhythm.
- Add wear where water, feet, impact, weather or age would plausibly cause it.
- Avoid placing decorative reliefs where structural geometry would make them impossible.
- Separate foreground, midground and background through overlap, value, saturation, contrast and detail density.
- Ground contact, cast shadows and occlusion are mandatory for objects sitting on a surface.

For ASHUR's Babylon scene: keep the ziggurat / temple silhouette dominant; use market stalls and Lamassu as framing masses; preserve a readable path through the street; keep distant towers atmospheric; use reliefs and cuneiform as designed architectural ornament, not random glyph wallpaper.

## 10. Character and creature construction

### Character checklist
- Readable pose and gesture at 1x.
- Head/face orientation agrees with body and camera.
- Face has a hierarchy: brow/hood, eye region, nose plane, cheek, mouth/beard where visible.
- Costume has distinct layers: base garment, outer robe/cape, belt, straps, pouch, footwear and fasteners.
- Folds originate from tension, gravity and joints—not arbitrary stripes.
- Hands and feet have clear direction and attachment.
- Shadows separate overlapping limbs and garment layers.
- Animation frames preserve volume, costume landmarks and pixel scale.

### Creature / statue checklist
- Build anatomy from large masses and joints.
- Keep head, muzzle, horns/wings, torso, legs and tail separable in silhouette.
- Use a consistent light on each anatomical plane.
- Carved stone/metal statues need both anatomical form and material treatment.
- Ornament follows anatomy and construction; it must not become surface noise.

## 11. Dithering, anti-aliasing and special effects

- Dithering is a deliberate pattern used to create a transition or material texture—not a default fill.
- Choose pattern scale, direction and coverage intentionally.
- Keep dither subordinate to silhouette and form.
- Avoid checkerboard overuse and uniform noise blankets.
- Anti-alias selectively and only when the native-size result becomes clearer.
- Pixel lighting, fog, bloom and particles must be quantized to the logical grid.
- Every effect needs a falloff model and a maximum footprint so it does not wash out focal edges.

## 12. Animation and sprite consistency

- Define pivot, baseline, bounding box and anchor points per sprite.
- Preserve head size, costume landmarks, palette and light direction across frames.
- Use key poses first, then breakdowns and in-betweens.
- A walk cycle needs readable contact, passing, down and up poses; feet should not slide unintentionally.
- Secondary motion (cape, pouch, hair, banners) follows inertia and lags behind the main body.
- Compare frames as an onion-skin / contact sheet.
- Run silhouette flicker and pixel-cluster consistency checks across frames.

## 13. Typography and UI pixel art

- Typography must be raster/pixel-native or carefully authored for the grid.
- Prioritize Cyrillic coverage and legibility at the actual mobile size.
- Keep stroke thickness, baseline, spacing and glyph proportions consistent.
- Use limited pixel UI palettes and coherent bevel / highlight logic.
- Buttons, frames, icons and panels must share a common pixel scale.
- Avoid decorative outlines, glows or glitch effects that reduce contrast or text readability.

## 14. Reference workflow and ethical use

- Collect references by subject, material, camera, light and mood—not just by game title.
- Study principles and construction; do not trace or reproduce another artist's signature artwork.
- Keep source links, author names, license and access date in the project notes.
- Do not ingest paid books, pirated scans, Patreon-only content or copyrighted sprite sheets as training data.
- A reference image is a guide for analysis, not a texture to be copied.
- Use original ASHUR shapes, palettes and compositions.

## 15. Generator design contract

Each procedural generator should accept explicit parameters for:

- geometry and logical bounds;
- material family and material ramp;
- camera / orientation;
- key-light direction and local light influence;
- detail tier (silhouette, base, polished, hero);
- seed for deterministic variation;
- focal importance / contrast budget;
- optional wear, age and damage;
- layer grouping (base, shadow, light, texture, accent).

Generators should emit semantic layers or tagged primitives. A wall should expose masonry, mortar, bevel light, bevel shadow, damage and focal accents separately. A character should expose silhouette, anatomy, costume, face, shadow, highlight and accessories separately.

Never make procedural randomness responsible for the primary silhouette, face, anatomy or focal ornament. Those must be authored from controlled shape grammar or hand-designed pixel masks. Randomness is for secondary variation only.

## 16. Automated QA: measure craft, not just file validity

The current inspector's counts are useful but insufficient. Add diagnostics in tiers:

### Hard failures
- out-of-bounds geometry;
- invalid palette references;
- non-integer scale / fractional coordinates where disallowed;
- inconsistent sprite pixel pitch;
- missing required scene light or perspective metadata;
- malformed sprite frames / pivots.

### Craft warnings with coordinates
- isolated pixels and accidental noise;
- jaggies / doubles on long contours;
- banding and pillow-shading suspicion;
- excessive anti-aliasing;
- inconsistent light direction;
- palette-ramp ordering / luminance collisions;
- insufficient focal/background separation;
- repeated procedural patterns;
- tangencies and merged silhouettes;
- detail density too uniform;
- material family with no distinct texture or specular response.

### Visual review snapshots
Every substantial scene change must produce:
- native-size 1x;
- nearest-neighbour 3x or 4x;
- grayscale/value preview;
- palette swatch and ramp sheet;
- focal crop (traveler / Lamassu / temple);
- silhouette-only pass;
- layer contact sheet.

Automated QA cannot certify beauty. It can catch known failure modes and provide evidence for human review.

## 17. Mandatory review gate: the three critics

Every major art commit receives three separate reviews. These are internal review roles, not external people or independent services.

**1. Art director**
- Does the image tell one clear story?
- Is the focal hierarchy obvious?
- Are composition, depth and palette coherent?
- Is there enough negative space?

**2. Pixel-art specialist**
- Are silhouettes, curves and clusters clean?
- Do materials read differently?
- Is the pixel scale consistent?
- Are shading, dithering and outlines controlled?

**3. Technical visual QA**
- Does the scene render deterministically?
- Are bounds, palettes, layers and sprite anchors valid?
- Does it read at native size and mobile viewport?
- Are tests and visual snapshots attached?

Each critic returns: severity (blocker/major/minor), location, evidence, proposed correction. Resolve blockers and majors before the next art stage. Do not create a commit merely to show activity.

## 18. Recommended implementation order for Pixel Foundry

1. **Art-bible schema:** SPECC+, light rig, material library, focal map, depth planes and detail tiers.
2. **Palette engine:** hue-shift ramps, value analysis, material palettes and contrast budget.
3. **Cluster/edge QA:** isolated pixels, jaggies, banding, AA and contour diagnostics.
4. **Material generators:** masonry, sandstone, bronze, wood, cloth, leather, skin, glass and foliage as separate semantic layers.
5. **Authored sprite masks:** face, hands, anatomy, Lamassu head/body, temple ornament and other focal silhouettes.
6. **Lighting pass:** directional pixel shadows, contact shadows, bounce and local emissive lights.
7. **Depth/composition tools:** atmospheric falloff, scale-by-depth, overlap checks and detail-density maps.
8. **Animation QA:** pivots, onion-skin, silhouette flicker and frame consistency.
9. **Visual regression gallery:** native-size snapshots and side-by-side comparison after each change.

### Definition of done

A feature is complete only when:
- it has a documented artistic purpose;
- it has a deterministic example scene;
- it has unit tests for geometry and constraints;
- it has a rendered visual snapshot;
- it has passed the three-critic review;
- it improves readability, form, material or story—not merely operation count.

---

## 19. Source library (free/public learning resources)

These are selected starting points, not an exhaustive list of every pixel-art resource on the internet. Availability and terms can change; check the original page before reuse.

1. **Lospec — Pixel Art Tutorials**  
   https://lospec.com/pixel-art-tutorials/pixel-arts  
   Curated index with hundreds of tutorials, including Pixel Logic (Michael Azzi), Pedro Medeiros' shading / process / animation lessons, Luke Sadface's palette guide and Slynyrd's modular techniques.

2. **Helm — Pixelation Knowledge Repository**  
   https://lospec.com/pixel-art-tutorials/pixelation-knowledge-repository-by-helm  
   Advanced discussion of clusters, banding and dithering. Useful as a technical anti-pattern reference.

3. **Pedro Medeiros — Pixel Art Process and Walk Cycle**  
   https://lospec.com/pixel-art-tutorials/pixel-art-process-by-pedro-medeiros  
   https://lospec.com/pixel-art-tutorials/pixel-arts  
   Process thinking, background treatment, shading and character animation.

4. **Pixel Art School — Free Lessons**  
   https://pixelart.school/learn  
   Practical interactive lessons covering lines, curves, palette, lighting, materials, tilesets, characters and animation.

5. **Pixel Art School — SPECC planning method**  
   https://pixelart.school/learn/pixel-art-specc  
   A useful pre-drawing checklist for size, perspective, color/light and composition.

6. **Pixel Art School — Common mistakes**  
   https://pixelart.school/learn/pixel-art-terms  
   Clear diagnostics for doubles, jaggies, pillow shading, banding, over-AA, noise, mixed pixel sizes, selective outlines and hue shifting.

7. **Pixel Art School — Brick material walkthrough**  
   https://pixelart.school/learn/pixel-art-bricks  
   A concrete, reproducible workflow for masonry: mortar, staggered bricks, bevel light/shadow and restrained highlights.

8. **Naikomy — Pixel Art Knowledge Base**  
   https://naikomy.art/pages/kb-pixel-art  
   Resource index with Russian-language material, Saint11's Pixel Grimoire, MortMort, Luis Zuno, GDQuest and hue-shifting lessons.

9. **AdamCYounis — Pixel Art Class**  
   https://www.youtube.com/@AdamCYounis  
   Free public lessons and demonstrations. Study form construction, references, selective outlines, palette decisions and material rendering.

10. **MortMort**  
    https://www.youtube.com/@MortMort  
    Free public video lessons on pixel-art workflows, sprites and animation.

11. **GDQuest — Pixel Art Drawing Techniques**  
    https://www.gdquest.com/  
    Search the GDQuest pixel-art drawing techniques lesson for structured technique demonstrations.

12. **Saint11 — Pixel Grimoire**  
    https://twitter.com/saint11  
    Eight-part visual tutorial series; use as a study reference and follow the author's original links.

13. **Literature to consult through legitimate access**  
    - Michael Azzi & Jenna Broun, *Pixel Logic: A Guide to Pixel Art*.
    - Daniel Silber, *Pixel Art for Game Developers*.  
    These are books, not assumed free downloads. This manual does not reproduce their text.

---

## 20. How ASHUR should use this manual

This file is the source of truth for the renderer and art director. The short README rules are only a summary. Every new generator, art-bible schema change and quality gate should point back to the relevant section here.

**Do not interpret this manual as a request to make every image photorealistic.** The goal is authored, readable, stylistically coherent pixel art. Detail is earned by form, material, lighting and composition.
