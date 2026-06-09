# Kế Hoạch Hoàn Thiện Đồ Án GEO

## 1. Mục tiêu đầu ra

Đồ án cần hoàn thiện theo ba đầu ra chính:

1. **Báo cáo tốt nghiệp tiếng Việt** có cấu trúc chương rõ ràng, không viết theo kiểu paper ngắn.
2. **Mã nguồn và pipeline chạy được** cho benchmark UAV reconstruction trên `Dronescapes` và `ODMData`.
3. **Bộ kết quả minh họa và định lượng** đủ để giải thích ý tưởng `risk-guided hybrid refinement`.

## 2. Hiện trạng đã có

### 2.1. Phần đã hoàn thành

- Repo dự án đã được tách riêng tại `GEO-repo`.
- Pipeline chính đã có:
  - `DUSt3R`
  - `MASt3R`
  - `risk-guided hybrid refinement`
  - `COLMAP + OpenMVS`
- Có script chạy:
  - `run_geo_project.sh`
  - `scripts/run_poc_balanced_ubuntu_nvidia.sh`
  - `scripts/run_full_thermal_safe_ubuntu_nvidia.sh`
- Có benchmark trên hai dataset thật:
  - `Dronescapes`
  - `ODMData`
- Đã có bản manuscript paper-like và một bộ hình qualitative trong `report/figures/`.

### 2.2. Phần chưa hoàn chỉnh theo chuẩn đồ án

- Bản tiếng Việt cũ vẫn còn thiên về bài báo thực nghiệm.
- Chưa có một khung đồ án rõ ràng theo dạng:
  - mở đầu
  - tổng quan
  - cơ sở lý thuyết
  - giải pháp đề xuất
  - thiết kế hệ thống
  - thực nghiệm
  - kết luận
- Chưa tách rõ:
  - phần đóng góp kỹ thuật
  - phần cài đặt hệ thống
  - phần giới hạn và hướng phát triển

## 3. Hướng hoàn thiện

### 3.1. Định vị đồ án

Đồ án nên được viết như một **báo cáo kỹ thuật có chiều sâu học thuật**, không nên cố trình bày như một bài báo claim SOTA.

Luận điểm trung tâm cần giữ:

> Có thể cải thiện trade-off giữa chất lượng tái tạo và chi phí tính toán bằng cách chỉ refine các frame UAV có rủi ro tái tạo cao.

### 3.2. Thông điệp chính

- `MASt3R` hiện vẫn là baseline mạnh hơn về độ chính xác tuyệt đối.
- `risk_hybrid` chưa thắng toàn diện.
- Nhưng `risk_hybrid` cho thấy hướng **selective refinement theo budget** là hợp lý và đáng phát triển.

Đây là cách viết an toàn và thuyết phục hơn cho đồ án tốt nghiệp.

## 4. Kế hoạch hoàn thiện theo giai đoạn

### Giai đoạn A. Chuẩn hóa báo cáo

Mục tiêu:

- dựng bản thảo đồ án tiếng Việt theo cấu trúc chương;
- thống nhất tên đề tài, mục tiêu, phạm vi, đóng góp;
- đưa kết quả benchmark hiện có vào đúng ngữ cảnh.

Việc cần làm:

- tạo file báo cáo tốt nghiệp riêng;
- đưa mục lục hoàn chỉnh;
- viết lại phần tổng quan và khảo sát 3D reconstruction;
- tách chương phương pháp, cài đặt hệ thống, thực nghiệm.

Deliverable:

- `report/thesis_vi.tex`
- `report/thesis_vi.pdf`

### Giai đoạn B. Khóa thực nghiệm

Mục tiêu:

- chốt bộ thực nghiệm dùng trong đồ án;
- chọn một protocol đủ ổn định để trình bày;
- tránh để bảng số bị mâu thuẫn giữa các tài liệu.

Việc cần làm:

- xác định rõ run nào sẽ là run chính dùng trong báo cáo;
- khóa bảng số cho:
  - `Dronescapes`
  - `ODMData`
- khóa bộ hình qualitative đại diện.

Deliverable:

- bảng kết quả cuối cùng;
- figure set cuối cùng cho báo cáo;
- ghi rõ điều kiện đánh giá của từng dataset.

### Giai đoạn C. Hoàn thiện bảo vệ

Mục tiêu:

- chuẩn bị bản nộp, bản thuyết trình và câu trả lời phản biện.

Việc cần làm:

- rút ra 3 đến 5 đóng góp rõ ràng;
- viết phần hạn chế trung thực;
- chuẩn bị FAQ cho hội đồng:
  - novelty là gì
  - vì sao chọn dataset này
  - vì sao chưa thắng MASt3R
  - hướng phát triển tiếp theo là gì

Deliverable:

- bản báo cáo sạch;
- bộ slide bảo vệ;
- checklist demo/chạy code.

## 5. Cấu trúc báo cáo đề xuất

1. Mở đầu  
2. Tổng quan về 3D reconstruction và các hướng nghiên cứu liên quan  
3. Cơ sở lý thuyết cho bài toán tái tạo UAV từ ảnh  
4. Giải pháp đề xuất: risk-guided hybrid refinement  
5. Thiết kế và cài đặt hệ thống GEO  
6. Thực nghiệm và đánh giá  
7. Kết luận và hướng phát triển  
Phụ lục  

## 6. Checklist hoàn thiện trước khi nộp

### 6.1. Báo cáo

- [ ] Tên đề tài thống nhất ở mọi file
- [ ] Mục tiêu và phạm vi viết rõ
- [ ] Chương tổng quan có survey đủ rộng nhưng không lan man
- [ ] Chương phương pháp nêu rõ novelty
- [ ] Chương thực nghiệm có bảng và hình
- [ ] Kết luận có cả điểm mạnh và hạn chế

### 6.2. Mã nguồn

- [ ] Có lệnh chạy chính
- [ ] Có script POC cho máy tầm trung
- [ ] Có script full cho máy mạnh
- [ ] Có README mô tả pipeline và output

### 6.3. Kết quả

- [ ] Có ít nhất một run định lượng ổn định trên `Dronescapes`
- [ ] Có một run so sánh trên `ODMData`
- [ ] Có hình qualitative đủ đẹp để giải thích pipeline

## 7. Khuyến nghị thực tế

Nếu mục tiêu là **bảo vệ đồ án tốt**, ưu tiên nên là:

1. khóa một bản báo cáo sạch, rõ và trung thực;
2. khóa một bộ kết quả POC đủ thuyết phục;
3. chỉ coi `full` benchmark là phần mở rộng, không biến nó thành điểm nghẽn làm chậm tiến độ.

## 8. Tệp nên dùng làm đầu mối

- Báo cáo đồ án: `report/thesis_vi.tex`
- PDF đồ án: `report/thesis_vi.pdf`
- Manuscript paper-like: `report/main_isprsjprs.tex`
- Tài liệu vận hành: `GEO_PROJECT.md`
- Mã nguồn chính: `src/geo_uav_recon`
