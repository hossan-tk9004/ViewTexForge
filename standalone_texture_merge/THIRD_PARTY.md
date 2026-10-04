# ViewTexForge v0.2.1

`blender_geometry.py` adapts the RENDER dependency graph collector in
`view_tex_forge/contract_capture.py` and the render invocation in
`view_tex_forge/contract_raster.py`, from ViewTexForge v0.2.1.
Inspected source: `D:/RD/BlenderAddons/ViewTexForge/view_tex_forge/`.
The evaluator and handler lifecycle are retained. The adapter selects the
requested UV layer and omits camera snapshots, UUID writes and geometry digests.
It does not modify or require an installed ViewTexForge add-on.

MIT License

Copyright (c) 2026 giken-hos

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
