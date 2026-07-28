# Third-Party Notices

The PPTX Generator DevPost delivery package does not redistribute external
CAPTW/pngtopptx Skill source, Node modules, Python environments, browser
binaries, font binaries, Microsoft Office binaries, or Tesseract/Cairo
binaries. Those components remain prepared-machine prerequisites.

The runtime dependency versions and hashes are recorded in
`requirements/devpost-release.lock.txt`; their respective upstream licenses
continue to apply. The release package contains repository-authored synthetic
fixture documents and platform-generated visual references whose provenance is
recorded in `examples/deckcompiler_demo/phase4/generation_provenance.json`.

The setup wrapper downloads the pinned external SkillSet from the canonical
`CAPTW/pngtopptx` repository into the user's external Skill root. The upstream
project is licensed under the MIT License; its license and notices continue to
apply. No external Skill source is committed to this repository or copied into
the delivery ZIP.

Microsoft PowerPoint is used through an installed COM interface and is not
redistributed. Playwright controls an installed Chrome for Testing binary; the
browser binary is not included. The external CAPTW/pngtopptx SkillSet is
validated by a read-only pin and is not copied into the repository or delivery
package.

## External Python reconstruction dependency closure

DeckCompiler installs the following additional lock-owned distributions for the
canonical external reconstruction and visual-QA entrypoints. Wheels are used at
runtime but are not copied into the delivery ZIP. Exact versions and artifact
SHA-256 values are bound in
`examples/deckcompiler_demo/phase7/contract/external_python_runtime_dependency_manifest.json`.

| Distribution | Version | License classification |
|---|---:|---|
| ImageIO | 2.37.2 | BSD-2-Clause |
| lazy_loader | 0.4 | BSD-3-Clause |
| NetworkX | 3.6.1 | BSD-3-Clause |
| NumPy | 2.2.6 | BSD-3-Clause; bundled third-party notices also apply |
| opencv-python-headless | 4.12.0.88 | MIT wrapper; Apache-2.0 OpenCV and bundled third-party notices also apply |
| packaging | 25.0 | Apache-2.0 OR BSD-2-Clause |
| scikit-image | 0.26.0 | BSD-3-Clause; bundled third-party notices also apply |
| SciPy | 1.17.0 | BSD-3-Clause; bundled third-party notices also apply |
| tifffile | 2026.1.14 | BSD-3-Clause |

License classifications and evidence hashes above were taken from the selected
wheel `METADATA` and bundled license files. The project does not claim these
packages or their source as Build Week work.
