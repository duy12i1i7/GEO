# Report Artifacts

- `main.tex`: English LaTeX source of the reduced single-dataset survey and proposal.
- `main_vi.tex`: Vietnamese LaTeX source of the same report.
- `references.bib`: bibliography with 40+ references, dominated by recent Q1-oriented journal papers plus a few benchmark-specific additions.
- `main.pdf`: compiled report.
- `main_vi.pdf`: compiled Vietnamese report.

Build commands:

```bash
cd /Users/udy/hawkbot/report
latexmk -xelatex -bibtex -interaction=nonstopmode -halt-on-error main.tex
latexmk -xelatex -bibtex -interaction=nonstopmode -halt-on-error main_vi.tex
```
