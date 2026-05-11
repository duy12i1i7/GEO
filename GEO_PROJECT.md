# GEO Project

This workspace still contains the original `hawkbot` ROS2 codebase, but the UAV reconstruction
research project is now self-contained in the following paths:

- package: `/Users/udy/hawkbot/src/hawkbot_uav_usegeo`
- scripts: `/Users/udy/hawkbot/scripts`
- report: `/Users/udy/hawkbot/report`
- real-data outputs: `/Users/udy/hawkbot/output/hawkbot_uav_usegeo`

## What the project does

The project studies one concrete question:

`Can UAV reconstruction quality be preserved while spending expensive refinement only on risky frames?`

To answer that, the codebase now uses a pragmatic two-dataset setup:

- `Dronescapes`
  - quantitative benchmark with paired RGB/depth frames
- `ODMData`
  - real UAV photogrammetry image blocks for runtime and qualitative reconstruction comparison

This pairing is practical because `Dronescapes` provides evaluation targets, while `ODMData`
behaves like a realistic photogrammetry workload that `COLMAP + OpenMVS`, `DUSt3R`, `MASt3R`,
and the risk-guided hybrid method can all process directly.

## Main entrypoints

### One-command run

```bash
/Users/udy/hawkbot/run_geo_project.sh
```

Default behavior:

- runs in `full` mode by default
- uses the prepared full environment if available
- otherwise bootstraps it automatically
- runs the package self-checks before any benchmark
- prepares `ODMData` and the full selected `Dronescapes` split under `/Users/udy/hawkbot/data/hawkbot_uav_usegeo`
- validates that both real datasets are available before benchmarking
- runs the benchmark end to end
- writes the final HTML/JSON/CSV artifacts under `/Users/udy/hawkbot/output/hawkbot_uav_usegeo/ready_run/`

By default the script prepares the official `ODMData` sample `mygla`, because it is a small real
UAV block that the official `ODMData` index labels as a good starter dataset.

Optional overrides:

```bash
/Users/udy/hawkbot/run_geo_project.sh --odm-sample-name toledo
```

```bash
/Users/udy/hawkbot/run_geo_project.sh --odm-archive-path /path/to/odm_sample.zip
```

```bash
/Users/udy/hawkbot/run_geo_project.sh --odm-root /path/to/prepared_odmdata
```

Lightweight real-data path:

```bash
/Users/udy/hawkbot/run_geo_project.sh --mode quick
```

`quick` only prepares `Dronescapes` and skips the `COLMAP + OpenMVS` baseline.

Default full-download location for `Dronescapes`:

- `/Users/udy/hawkbot/data/hawkbot_uav_usegeo/dronescapes_full_test_set_annotated_only`

Example for a stronger machine with GPU:

```bash
/Users/udy/hawkbot/run_geo_project.sh \
  --coarse-device cuda \
  --refine-device cuda \
  --batch-size 4 \
  --top-k-frames 32 \
  --risk-neighbors 8
```

### Proposal pipeline

```bash
/Users/udy/hawkbot/scripts/run_risk_hybrid_pipeline.sh \
  --dataset-kind odmdata \
  --dataset-root /path/to/odmdata_sample \
  --output-dir /tmp/odm_risk_hybrid \
  --python-bin /Users/udy/hawkbot/.micromamba/envs/uav-usegeo-full/bin/python
```

### Real benchmark orchestration

```bash
/Users/udy/hawkbot/scripts/run_real_uav_benchmark.sh \
  --odm-output-root /tmp/odmdata_mygla \
  --dronescapes-output-root /tmp/dronescapes_subset \
  --python-bin /Users/udy/hawkbot/.micromamba/envs/uav-usegeo-full/bin/python
```

### Benchmark from config

```bash
PYTHONPATH=/Users/udy/hawkbot/src/hawkbot_uav_usegeo \
python3 -m hawkbot_uav_usegeo.cli benchmark \
  --config /Users/udy/hawkbot/output/hawkbot_uav_usegeo/ready_run/benchmark_real.json \
  --output-dir /Users/udy/hawkbot/output/hawkbot_uav_usegeo/ready_run
```

## Key outputs

After a run, the main artifacts are:

- `/Users/udy/hawkbot/output/hawkbot_uav_usegeo/ready_run/benchmark_summary.json`
- `/Users/udy/hawkbot/output/hawkbot_uav_usegeo/ready_run/benchmark_report.html`
- `/Users/udy/hawkbot/output/hawkbot_uav_usegeo/ready_run/benchmark_metrics.csv`

## Read next

- package guide: `/Users/udy/hawkbot/src/hawkbot_uav_usegeo/README.md`
- survey/report: `/Users/udy/hawkbot/report/main_vi.pdf`
