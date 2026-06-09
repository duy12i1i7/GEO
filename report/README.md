# Report Artifacts

- `main.tex`: English LaTeX source of the GEO survey and proposal.
- `main_vi.tex`: Vietnamese LaTeX source of the same report.
- `main_isprsjprs.tex`: paper-style English manuscript for venue-oriented writing.
- `thesis_vi.tex`: Vietnamese graduation-thesis style draft built from the GEO project.
- `THESIS_PLAN_VI.md`: completion plan and checklist for turning the project into a full thesis.
- `references.bib`: bibliography with 40+ references, dominated by recent Q1-oriented journal papers plus benchmark-specific additions.
- `main.pdf`: compiled English report.
- `main_vi.pdf`: compiled Vietnamese report.
- `main_isprsjprs.pdf`: compiled paper-style manuscript.
- `thesis_vi.pdf`: compiled Vietnamese thesis-style draft.

Build commands:

```bash
cd /Users/udy/GEO-repo/report
latexmk -xelatex -bibtex -interaction=nonstopmode -halt-on-error main.tex
latexmk -xelatex -bibtex -interaction=nonstopmode -halt-on-error main_vi.tex
latexmk -xelatex -bibtex -interaction=nonstopmode -halt-on-error main_isprsjprs.tex
latexmk -xelatex -bibtex -interaction=nonstopmode -halt-on-error thesis_vi.tex
```
