# visual assets

Two small SVG pairs give the notebook a consistent visual language:

| Pair | Use |
| :--- | :--- |
| [sketchbook-light.svg](sketchbook-light.svg) / [sketchbook-dark.svg](sketchbook-dark.svg) | The wordmark and branching-question illustration. |
| [thinking-loop-light.svg](thinking-loop-light.svg) / [thinking-loop-dark.svg](thinking-loop-dark.svg) | Ask, explore, challenge, distill, and revisit. |

The SVG files are the editable sources. There is no generator, remote image service, JavaScript, animation, embedded font, or raster dependency. Text uses system font fallbacks. Do not commit local render previews.

Each pair shares geometry and typography, with a different palette. Keep both variants in sync. The README selects a theme through a `picture` element and provides a light fallback. Important content also appears as Markdown or descriptive alt text.

To change an illustration, edit the SVG directly, run the repository checks, and inspect both versions at full width and at a narrow README width. Structural validation is not a substitute for looking at the result.

[Back to sketchbook](../README.md)
