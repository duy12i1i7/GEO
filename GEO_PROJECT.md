# GEO Project

## Phạm vi

Repo này triển khai một benchmark UAV reconstruction độc lập, tập trung vào câu hỏi:

`Có thể giữ chất lượng tái tạo gần với phương pháp refine nặng, trong khi chỉ dành compute cho các frame rủi ro cao hay không?`

Thiết lập hiện tại dùng hai dataset thật:

- `Dronescapes`: benchmark định lượng với depth tham chiếu
- `ODMData`: workload photogrammetry UAV thực tế

## Pipeline

Phương pháp đề xuất `risk-guided hybrid refinement` chạy theo bốn bước:

1. `DUSt3R` dựng depth/reconstruction thô trên toàn bộ frame
2. mô-đun `risk.py` chấm điểm rủi ro dựa trên overlap, texture, depth gap và view diversity
3. chỉ `top-k` frame rủi ro cao mới được refine bằng `MASt3R`
4. benchmark tổng hợp chất lượng, runtime, selected ratio, và artifact hình học

## Mã nguồn chính

- package: [src/geo_uav_recon](/Users/udy/GEO-repo/src/geo_uav_recon)
- scripts: [scripts](/Users/udy/GEO-repo/scripts)
- survey/report: [report](/Users/udy/GEO-repo/report)

Các file quan trọng trong package:

- [dataset.py](/Users/udy/GEO-repo/src/geo_uav_recon/geo_uav_recon/dataset.py)
- [realdata.py](/Users/udy/GEO-repo/src/geo_uav_recon/geo_uav_recon/realdata.py)
- [predictors.py](/Users/udy/GEO-repo/src/geo_uav_recon/geo_uav_recon/predictors.py)
- [risk.py](/Users/udy/GEO-repo/src/geo_uav_recon/geo_uav_recon/risk.py)
- [benchmark.py](/Users/udy/GEO-repo/src/geo_uav_recon/geo_uav_recon/benchmark.py)
- [cli.py](/Users/udy/GEO-repo/src/geo_uav_recon/geo_uav_recon/cli.py)

## Cách chạy

Lệnh mặc định:

```bash
/Users/udy/GEO-repo/run_geo_project.sh
```

Mặc định `full` sẽ:

- chuẩn bị suite `ODMData` mặc định `recommended`
- tải và benchmark toàn bộ suite `Dronescapes` mặc định `all_splits`
- chạy self-check
- chạy `COLMAP + OpenMVS`, `DUSt3R`, `MASt3R`, `risk_hybrid_real`
- xuất kết quả vào [output/geo_uav_recon/ready_run](/Users/udy/GEO-repo/output/geo_uav_recon/ready_run)

Chế độ nhanh:

```bash
/Users/udy/GEO-repo/run_geo_project.sh --mode quick
```

## Ubuntu + NVIDIA

Repo đã có bootstrap riêng cho Ubuntu + NVIDIA:

- [scripts/bootstrap_geo_uav_recon_ubuntu_cuda.sh](/Users/udy/GEO-repo/scripts/bootstrap_geo_uav_recon_ubuntu_cuda.sh)

Luồng khuyến nghị:

```bash
cd ~/GEO-repo
./scripts/bootstrap_geo_uav_recon_ubuntu_cuda.sh
~/GEO-repo/run_geo_project.sh \
  --no-bootstrap \
  --python-bin ~/GEO-repo/.venv-geo-uav-recon/bin/python \
  --coarse-device cuda \
  --refine-device cuda \
  --batch-size 4
```

Chạy lớn hơn trên máy mạnh:

```bash
/Users/udy/GEO-repo/run_geo_project.sh \
  --coarse-device cuda \
  --refine-device cuda \
  --batch-size 4 \
  --top-k-frames 32 \
  --risk-neighbors 8 \
  --dronescapes-max-frames 0
```

Chạy benchmark với nhiều block `ODMData` trong một lần:

```bash
/Users/udy/GEO-repo/run_geo_project.sh \
  --odm-benchmark-suite recommended
```

Khi đó config sẽ sinh nhiều dataset:

- `odmdata_mygla_real`
- `odmdata_toledo_real`
- `odmdata_shitan_tw_real`
- `odmdata_tuniu_tw_1_real`
- `dronescapes_real`

Muốn gọi tường minh chế độ full toàn bộ:

```bash
/Users/udy/GEO-repo/run_geo_project.sh \
  --odm-benchmark-suite recommended \
  --dronescapes-benchmark-suite all_splits
```

## Artifact đầu ra

Sau mỗi lần chạy, các file chính là:

- [benchmark_summary.json](/Users/udy/GEO-repo/output/geo_uav_recon/ready_run/benchmark_summary.json)
- [benchmark_report.html](/Users/udy/GEO-repo/output/geo_uav_recon/ready_run/benchmark_report.html)
- [benchmark_metrics.csv](/Users/udy/GEO-repo/output/geo_uav_recon/ready_run/benchmark_metrics.csv)

## Báo cáo

- tiếng Anh: [main.pdf](/Users/udy/GEO-repo/report/main.pdf)
- tiếng Việt: [main_vi.pdf](/Users/udy/GEO-repo/report/main_vi.pdf)
