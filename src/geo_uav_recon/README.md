# geo_uav_recon

Package Python cho pipeline benchmark UAV reconstruction dùng cặp dataset:

- `ODMData`
- `Dronescapes`

## Chạy full

Từ root workspace:

```bash
/Users/udy/GEO-repo/run_geo_project.sh
```

Luồng `full` sẽ:

- tự bootstrap môi trường nếu thiếu
- tự chuẩn bị suite `ODMData` mặc định `recommended` nếu chưa có
- tự tải và chuẩn bị toàn bộ suite `Dronescapes` mặc định `all_splits` nếu chưa có
- chạy self-check trước benchmark
- chạy các method:
  - `COLMAP + OpenMVS`
  - `DUSt3R`
  - `MASt3R`
  - `risk_hybrid_real`

## Ubuntu + NVIDIA

`run_geo_project.sh` hiện có thể tự bootstrap trên Ubuntu:

```bash
cd ~/GEO-repo
./run_geo_project.sh \
  --coarse-device cuda \
  --refine-device cuda \
  --batch-size 4
```

Muốn bootstrap riêng trước thì dùng:

```bash
cd ~/GEO-repo
./scripts/bootstrap_geo_uav_recon_ubuntu_cuda.sh
```

Sau đó chạy:

```bash
/Users/udy/GEO-repo/run_geo_project.sh \
  --no-bootstrap \
  --python-bin /Users/udy/GEO-repo/.venv-geo-uav-recon/bin/python \
  --coarse-device cuda \
  --refine-device cuda \
  --batch-size 4
```

Mặc định `full` dùng:

- `ODMData`: suite `recommended`
- `Dronescapes`: suite `all_splits`
- `top_k_frames = 16`
- `risk_neighbors = 6`

Muốn benchmark nhiều block `ODMData` trong một lần:

```bash
/Users/udy/GEO-repo/run_geo_project.sh --odm-benchmark-suite recommended
```

Preset `recommended` hiện gồm `mygla`, `toledo`, `shitan_tw`, `tuniu_tw_1`.

## Output chính

Artifact mặc định nằm ở:

- `/Users/udy/GEO-repo/output/geo_uav_recon/ready_run/benchmark_summary.json`
- `/Users/udy/GEO-repo/output/geo_uav_recon/ready_run/benchmark_report.html`
- `/Users/udy/GEO-repo/output/geo_uav_recon/ready_run/benchmark_metrics.csv`

## Chạy trên máy mạnh hơn

Ví dụ dùng GPU và tăng ngân sách refine:

```bash
/Users/udy/GEO-repo/run_geo_project.sh \
  --coarse-device cuda \
  --refine-device cuda \
  --batch-size 4 \
  --top-k-frames 32 \
  --risk-neighbors 8
```

Muốn đổi split hoặc giữ full split nhưng đổi kích thước benchmark:

```bash
/Users/udy/GEO-repo/run_geo_project.sh \
  --dronescapes-split train_set \
  --dronescapes-max-frames 0
```

## Ghi chú benchmark

- `Dronescapes` được chấm bằng ground-truth depth.
- `ODMData` không có ground-truth depth dày, nên benchmark chạy ở chế độ `pseudo_reference`, dùng depth export từ `COLMAP + OpenMVS` làm mốc so sánh.
