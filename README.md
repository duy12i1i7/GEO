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
