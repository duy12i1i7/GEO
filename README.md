# GEO

`GEO` là repo độc lập cho bài toán tái tạo không gian UAV từ chuỗi ảnh, tập trung vào benchmark và so sánh các pipeline reconstruction trên hai dataset thật:

- `Dronescapes`
- `ODMData`

Phần mã nguồn chính nằm ở [src/geo_uav_recon](/Users/udy/GEO-repo/src/geo_uav_recon), tài liệu vận hành ở [GEO_PROJECT.md](/Users/udy/GEO-repo/GEO_PROJECT.md), và báo cáo survey ở [report/main_vi.pdf](/Users/udy/GEO-repo/report/main_vi.pdf).

## Giải pháp chính

Phương pháp đề xuất là `risk-guided hybrid refinement`:

- chạy `DUSt3R` trên toàn bộ frame để có tái tạo thô
- tính điểm rủi ro tái tạo cho từng frame
- chỉ refine các frame rủi ro cao bằng `MASt3R`
- hợp nhất đầu ra để cân bằng chất lượng và chi phí tính toán

Các baseline chính hiện có:

- `COLMAP + OpenMVS`
- `DUSt3R`
- `MASt3R`
- `risk_hybrid_real`

## Chạy dự án

Lệnh chính:

```bash
/Users/udy/GEO-repo/run_geo_project.sh
```

Lệnh này sẽ:

- bootstrap môi trường nếu chưa có
- trong `full`, tự chạy suite `ODMData` mặc định `recommended`
- trong `full`, tự tải và benchmark toàn bộ các split `Dronescapes` mặc định `all_splits`
- chạy self-check
- chạy benchmark end-to-end
- xuất report HTML, JSON, CSV

## Ubuntu + NVIDIA

`run_geo_project.sh` giờ đã tự nhận biết Ubuntu và dùng bootstrap phù hợp. Cách đơn giản nhất là chạy thẳng:

```bash
cd ~/GEO-repo
./run_geo_project.sh \
  --coarse-device cuda \
  --refine-device cuda \
  --batch-size 4
```

Nếu muốn bootstrap riêng trước:

```bash
cd ~/GEO-repo
chmod +x scripts/bootstrap_geo_uav_recon_ubuntu_cuda.sh
./scripts/bootstrap_geo_uav_recon_ubuntu_cuda.sh
```

Script bootstrap Ubuntu hiện mặc định chạy ở chế độ thermal-safe:
- hạ mức ưu tiên CPU/I/O với `nice` và `ionice` nếu có
- giới hạn build jobs xuống tối đa `4` nếu bạn không override
- giảm tải cho các bước nặng như `vcpkg`, `OpenMVS`, và cài Python packages

Nếu muốn ép chặt hơn:

```bash
THERMAL_SAFE=1 BUILD_JOBS=2 ./scripts/bootstrap_geo_uav_recon_ubuntu_cuda.sh
```

Sau khi bootstrap riêng xong, có thể chạy lại bằng interpreter cố định:

```bash
~/GEO-repo/run_geo_project.sh \
  --no-bootstrap \
  --python-bin ~/GEO-repo/.venv-geo-uav-recon/bin/python \
  --coarse-device cuda \
  --refine-device cuda \
  --batch-size 4
```

Nếu cần đổi CUDA wheel, đặt:

```bash
TORCH_INDEX_URL=https://download.pytorch.org/whl/cu121 \
./scripts/bootstrap_geo_uav_recon_ubuntu_cuda.sh
```

Trên Ubuntu 24.04, script này mặc định dùng `python3` của hệ thống, tức thường là Python 3.12.

Nếu mục tiêu chỉ là `POC` ý tưởng trên máy Ubuntu + NVIDIA tầm trung, nên dùng script cân bằng sau thay vì `full`:

```bash
cd ~/GEO
git pull
./scripts/run_poc_balanced_ubuntu_nvidia.sh
```

Script này sẽ:
- tự bootstrap nếu môi trường chưa có
- mặc định bỏ `OpenMVS` để tránh build quá nặng
- chạy benchmark `2 dataset thật`:
  - `ODMData mygla`
  - `Dronescapes test_set_annotated_only`
- so sánh:
  - `DUSt3R`
  - `MASt3R`
  - `risk_hybrid`

Các biến có thể override khi cần:

```bash
THERMAL_SAFE=1 BUILD_JOBS=2 DRONESCAPES_MAX_FRAMES=16 ./scripts/run_poc_balanced_ubuntu_nvidia.sh
```

Nếu muốn chạy `full` trên máy Ubuntu + NVIDIA mạnh nhưng hay bị nhiệt, dùng script full thermal-safe:

```bash
cd ~/GEO
git pull
./scripts/run_full_thermal_safe_ubuntu_nvidia.sh
```

Mặc định script này sẽ:
- bootstrap khi cần
- vẫn build `OpenMVS`, nhưng với `BUILD_JOBS=1`
- chạy `full` với:
  - `ODMData` suite `recommended`
  - `Dronescapes` suite `all_splits`
  - `CPU_THREADS=4`
  - `BATCH_SIZE=2`

Có thể override:

```bash
THERMAL_SAFE=1 BUILD_JOBS=1 CPU_THREADS=2 BATCH_SIZE=1 ./scripts/run_full_thermal_safe_ubuntu_nvidia.sh
```

Nếu máy dễ sập vì nhiệt nhưng vẫn muốn chạy `full`, dùng thermal-safe mode:

```bash
cd ~/GEO-repo
./run_geo_project.sh \
  --thermal-safe \
  --cpu-threads 4 \
  --build-jobs 4 \
  --coarse-device cuda \
  --refine-device cuda \
  --batch-size 4
```

Ý nghĩa:
- giữ full benchmark như cũ
- giới hạn compile `OpenMVS` và runtime CPU-heavy về `4` luồng
- chạy photogrammetry với `nice`/`ionice` khi có trên Linux

Chế độ nhẹ để kiểm tra nhanh:

```bash
/Users/udy/GEO-repo/run_geo_project.sh --mode quick
```

Ví dụ chạy lớn hơn trên máy mạnh:

```bash
/Users/udy/GEO-repo/run_geo_project.sh \
  --coarse-device cuda \
  --refine-device cuda \
  --batch-size 4 \
  --top-k-frames 32 \
  --risk-neighbors 8 \
  --dronescapes-max-frames 0
```

Mặc định `full` giờ tương đương với:

```bash
/Users/udy/GEO-repo/run_geo_project.sh \
  --odm-benchmark-suite recommended \
  --dronescapes-benchmark-suite all_splits
```

Chạy một suite nhiều block `ODMData` trong cùng một lần benchmark:

```bash
/Users/udy/GEO-repo/run_geo_project.sh \
  --odm-benchmark-suite recommended
```

Preset `recommended` hiện gồm:

- `mygla`
- `toledo`
- `shitan_tw` (chấp nhận alias `shitan`)
- `tuniu_tw_1`

Preset `all_splits` của `Dronescapes` hiện gồm:

- `train_set`
- `validation_set`
- `semisupervised_set`
- `test_set`
- `train_set_annotated_only`
- `validation_set_annotated_only`
- `semisupervised_set_annotated_only`
- `test_set_annotated_only`

## Dataset và output

Dataset sẽ được chuẩn bị dưới:

- [data/geo_uav_recon](/Users/udy/GEO-repo/data/geo_uav_recon)

Output benchmark mặc định nằm ở:

- [output/geo_uav_recon/ready_run/benchmark_summary.json](/Users/udy/GEO-repo/output/geo_uav_recon/ready_run/benchmark_summary.json)
- [output/geo_uav_recon/ready_run/benchmark_report.html](/Users/udy/GEO-repo/output/geo_uav_recon/ready_run/benchmark_report.html)
- [output/geo_uav_recon/ready_run/benchmark_metrics.csv](/Users/udy/GEO-repo/output/geo_uav_recon/ready_run/benchmark_metrics.csv)

## Cấu trúc repo

```text
GEO-repo/
├── GEO_PROJECT.md
├── report/
├── run_geo_project.sh
├── scripts/
└── src/
    └── geo_uav_recon/
```

## Kiểm tra

```bash
PYTHONPATH=/Users/udy/GEO-repo/src/geo_uav_recon \
python3 -m unittest discover -s /Users/udy/GEO-repo/src/geo_uav_recon/test -v
```
