# Bundled Inter fonts

Shipped in this folder (OFL license, from https://github.com/rsms/inter):

  - `Inter-Regular.ttf`
  - `Inter-Bold.ttf`

`renderer.py` base64-embeds them into each render so local dev and CI match.
If either file is missing, the renderer falls back to the system font stack
(`"Inter", "Helvetica Neue", Arial`).
