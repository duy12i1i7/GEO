# hawkbot_uav_usegeo

Package Python cho pipeline benchmark UAV reconstruction dùng cặp dataset:

- `ODMData`
- `Dronescapes`

## Chạy full

Từ root workspace:

```bash
/Users/udy/hawkbot/run_geo_project.sh
```

Luồng `full` sẽ:

- tự bootstrap môi trường nếu thiếu
- tự chuẩn bị `ODMData` sample `mygla` nếu chưa có
- tự tải và chuẩn bị toàn bộ split `Dronescapes` đã chọn nếu chưa có
- chạy self-check trước benchmark
- chạy các method:
  - `COLMAP + OpenMVS`
  - `DUSt3R`
  - `MASt3R`
  - `risk_hybrid_real`

Mặc định `full` dùng:

- `ODMData`: sample `mygla`
- `Dronescapes`: full split `test_set_annotated_only`
- `top_k_frames = 16`
- `risk_neighbors = 6`

## Output chính

Artifact mặc định nằm ở:

- `/Users/udy/hawkbot/output/hawkbot_uav_usegeo/ready_run/benchmark_summary.json`
- `/Users/udy/hawkbot/output/hawkbot_uav_usegeo/ready_run/benchmark_report.html`
- `/Users/udy/hawkbot/output/hawkbot_uav_usegeo/ready_run/benchmark_metrics.csv`

## Chạy trên máy mạnh hơn

Ví dụ dùng GPU và tăng ngân sách refine:

```bash
/Users/udy/hawkbot/run_geo_project.sh \
  --coarse-device cuda \
  --refine-device cuda \
  --batch-size 4 \
  --top-k-frames 32 \
  --risk-neighbors 8
```

Muốn đổi split hoặc giữ full split nhưng đổi kích thước benchmark:

```bash
/Users/udy/hawkbot/run_geo_project.sh \
  --dronescapes-split train_set \
  --dronescapes-max-frames 0
```

## Ghi chú benchmark

- `Dronescapes` được chấm bằng ground-truth depth.
- `ODMData` không có ground-truth depth dày, nên benchmark chạy ở chế độ `pseudo_reference`, dùng depth export từ `COLMAP + OpenMVS` làm mốc so sánh.
