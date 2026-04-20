# CapCut Mate API

<div align="center">

### 🌐 Chuyển đổi ngôn ngữ

[中文版](README.zh.md) | [English](README.md)

</div>

---

## Giới thiệu dự án
CapCut Mate API là một trợ lý tự động hóa bản nháp Jianying **hoàn toàn mã nguồn mở và miễn phí**, được xây dựng trên **FastAPI** và hỗ trợ **triển khai độc lập**. Dự án này tập trung vào việc trang bị cho các mô hình lớn các khả năng chỉnh sửa video cơ bản, cung cấp các **kỹ năng** chỉnh sửa video dùng được ngay, đồng thời đã **tự động hóa hoàn toàn quy trình chức năng cốt lõi của Jianying**. Nó có thể **kết nối trực tiếp với các mô hình lớn** để thực hiện nhiều hình thức chỉnh sửa video thông minh khác nhau, giúp người dùng phổ thông nhanh chóng tạo ra các sản phẩm video chuyên nghiệp và nâng cao.

Cách sử dụng dự án rất linh hoạt: có thể **triển khai độc lập**, hoặc kết hợp với **Coze hay n8n** để xây dựng **quy trình làm việc tự động hóa**; đồng thời cũng có thể kết nối với Jianying để thực hiện **kết xuất đám mây**, tạo trực tiếp video hoàn chỉnh từ bản nháp.

## Tài nguyên dự án
- [⭐ Trợ lý Jianying](https://github.com/Hommy-master/capcut-mate)
- [🔌 Trợ lý Jianying - Plugin Coze](https://www.coze.cn/store/plugin/7576197869707722771)
- [🔗 Ví dụ quy trình làm việc](https://jcaigc.cn/workflow)

⭐ Nếu bạn thấy dự án này hữu ích, hãy tặng cho chúng tôi một Star! Sự ủng hộ của bạn là động lực lớn nhất để tôi tiếp tục duy trì và cải thiện dự án 😊

## Tính năng
- 🎬 Quản lý bản nháp: Tạo bản nháp, lấy bản nháp, lưu bản nháp
- 🎥 Thêm tư liệu: Thêm video, âm thanh, hình ảnh, sticker, phụ đề, hiệu ứng, mặt nạ, v.v.
- 🔧 Chức năng nâng cao: Điều khiển keyframe, kiểu văn bản, hiệu ứng hoạt ảnh, v.v.
- 📤 Xuất video: Kết xuất đám mây để tạo video hoàn chỉnh
- 🛡️ Xác thực dữ liệu: Sử dụng Pydantic để xác thực dữ liệu yêu cầu
- 📖 API RESTful: Tuân thủ các tiêu chuẩn thiết kế API phổ biến
- 📚 Tài liệu tự động: FastAPI tự động tạo tài liệu API tương tác

## Ngăn xếp công nghệ
- Python 3.11+
- FastAPI: Framework web hiệu năng cao
- Pydantic: Xác thực dữ liệu và định nghĩa mô hình
- Passlib: Mã hóa mật khẩu (nếu sử dụng xác thực người dùng)
- Uvicorn: Máy chủ ASGI
- uv: Trình quản lý gói Python và công cụ quản lý dự án

## Bắt đầu nhanh

### Điều kiện tiên quyết
- Python 3.11+
- uv: Trình quản lý gói Python và công cụ quản lý dự án

Cài đặt:
#### Windows
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

#### Linux/macOS
```bash
sh -c "$(curl -LsSf https://astral.sh/uv/install.sh)"
```

### Các bước cài đặt
1. Sao chép dự án
```bash
git clone git@github.com:Hommy-master/capcut-mate.git
cd capcut-mate
```

2. Cài đặt phụ thuộc
```bash
# Cài đặt phụ thuộc
uv sync

# Thực thi bổ sung cho Windows
uv pip install -e .[windows]
```

3. Khởi động máy chủ
```bash
uv run main.py
```

4. Truy cập tài liệu API
Sau khi khởi động, truy cập http://localhost:30000/docs để xem tài liệu API tương tác được tạo tự động

### Triển khai Docker

#### Triển khai nhanh (Khuyến nghị)

📺 **Video hướng dẫn**: [Hướng dẫn đầy đủ triển khai riêng CapCut Mate](https://v.douyin.com/5p-o319uA5o/)

```bash
git clone https://github.com/Hommy-master/capcut-mate.git
cd capcut-mate
docker-compose pull && docker-compose up -d
```

Sau khi triển khai, truy cập tài liệu API tại: http://localhost:30000/docs

## Nhập plugin Coze bằng một cú nhấp

1. Mở nền tảng Coze: https://coze.cn/home

   ![Bước 1](./assets/coze1.png)

2. Thêm plugin

   ![Bước 2](./assets/coze2.png)

3. Nhập plugin

   ![Bước 3](./assets/coze3.png)

4. Tải lên tệp openapi.yaml trong thư mục dự án hiện tại

   ![Bước 4](./assets/coze4.png)

5. Hoàn tất tải tệp lên

   ![Bước 5](./assets/coze5.png)

6. Hoàn tất thay logo

   ![Bước 6](./assets/coze6.png)

7. Kích hoạt plugin

   ![Bước 7](./assets/coze7.png)

## Tài liệu API

Dưới đây là các giao diện cốt lõi do CapCut Mate API cung cấp, hỗ trợ một quy trình tạo video hoàn chỉnh:

### 🏗️ Quản lý bản nháp
| Giao diện | Chức năng | Mô tả | Liên kết tài liệu |
|-----------|-----------|-------|-------------------|
| **create_draft** | Tạo bản nháp | Tạo một dự án bản nháp Jianying mới, thiết lập kích thước canvas | [📖 Xem tài liệu](./docs/create_draft.md) |
| **save_draft** | Lưu bản nháp | Lưu trạng thái bản nháp hiện tại, đảm bảo nội dung chỉnh sửa được lưu lại | [📖 Xem tài liệu](./docs/save_draft.md) |
| **get_draft** | Lấy bản nháp | Lấy danh sách tệp bản nháp và thông tin chi tiết | [📖 Xem tài liệu](./docs/get_draft.md) |

### 🎥 Tư liệu video
| Giao diện | Chức năng | Mô tả | Liên kết tài liệu |
|-----------|-----------|-------|-------------------|
| **add_videos** | Thêm video | Thêm hàng loạt tư liệu video, hỗ trợ cắt, co giãn, hiệu ứng | [📖 Xem tài liệu](./docs/add_videos.md) |
| **add_images** | Thêm hình ảnh | Thêm hàng loạt tư liệu hình ảnh, hỗ trợ hoạt ảnh và hiệu ứng chuyển cảnh | [📖 Xem tài liệu](./docs/add_images.md) |
| **add_sticker** | Thêm sticker | Thêm sticker trang trí, hỗ trợ điều chỉnh vị trí và kích thước | [📖 Xem tài liệu](./docs/add_sticker.md) |

### 🎵 Xử lý âm thanh
| Giao diện | Chức năng | Mô tả | Liên kết tài liệu |
|-----------|-----------|-------|-------------------|
| **add_audios** | Thêm âm thanh | Thêm hàng loạt tư liệu âm thanh, hỗ trợ âm lượng và fade in/out | [📖 Xem tài liệu](./docs/add_audios.md) |
| **get_audio_duration** | Lấy thời lượng âm thanh | Lấy thông tin thời lượng chính xác của tệp âm thanh | [📖 Xem tài liệu](./docs/get_audio_duration.md) |

### 📝 Văn bản phụ đề
| Giao diện | Chức năng | Mô tả | Liên kết tài liệu |
|-----------|-----------|-------|-------------------|
| **add_captions** | Thêm phụ đề | Thêm hàng loạt phụ đề, hỗ trợ tô sáng từ khóa và thiết lập kiểu | [📖 Xem tài liệu](./docs/add_captions.md) |
| **add_text_style** | Kiểu văn bản | Tạo kiểu văn bản phong phú, hỗ trợ màu và phông chữ cho từ khóa | [📖 Xem tài liệu](./docs/add_text_style.md) |

### ✨ Hiệu ứng & hoạt ảnh
| Giao diện | Chức năng | Mô tả | Liên kết tài liệu |
|-----------|-----------|-------|-------------------|
| **add_effects** | Thêm hiệu ứng | Thêm hiệu ứng hình ảnh như bộ lọc, viền, hiệu ứng động | [📖 Xem tài liệu](./docs/add_effects.md) |
| **add_keyframes** | Hoạt ảnh keyframe | Tạo hoạt ảnh thuộc tính cho vị trí, tỉ lệ, xoay, v.v. | [📖 Xem tài liệu](./docs/add_keyframes.md) |
| **add_masks** | Hiệu ứng mặt nạ | Thêm nhiều loại mặt nạ hình dạng, kiểm soát vùng hiển thị trên màn hình | [📖 Xem tài liệu](./docs/add_masks.md) |

### 🎨 Tài nguyên hoạt ảnh
| Giao diện | Chức năng | Mô tả | Liên kết tài liệu |
|-----------|-----------|-------|-------------------|
| **get_text_animations** | Hoạt ảnh văn bản | Lấy các hoạt ảnh xuất hiện, biến mất và lặp cho văn bản | [📖 Xem tài liệu](./docs/get_text_animations.md) |
| **get_image_animations** | Hoạt ảnh hình ảnh | Lấy danh sách các hiệu ứng hoạt ảnh khả dụng cho hình ảnh | [📖 Xem tài liệu](./docs/get_image_animations.md) |

### 🎬 Tạo video
| Giao diện | Chức năng | Mô tả | Liên kết tài liệu |
|-----------|-----------|-------|-------------------|
| **gen_video** | Tạo video | Gửi tác vụ kết xuất video, xử lý bất đồng bộ | [📖 Xem tài liệu](./docs/gen_video.md) |
| **gen_video_status** | Truy vấn trạng thái | Truy vấn tiến độ và trạng thái của tác vụ tạo video | [📖 Xem tài liệu](./docs/gen_video_status.md) |

### 🚀 Công cụ nhanh
| Giao diện | Chức năng | Mô tả | Liên kết tài liệu |
|-----------|-----------|-------|-------------------|
| **easy_create_material** | Tạo nhanh | Thêm nhiều loại tư liệu cùng lúc, đơn giản hóa quá trình tạo | [📖 Xem tài liệu](./docs/easy_create_material.md) |

### 🛠️ Công cụ tiện ích
| Giao diện | Chức năng | Mô tả | Liên kết tài liệu |
|-----------|-----------|-------|-------------------|
| **get_url** | Trích xuất URL | Trích xuất thông tin URL từ nội dung đầu vào | [📖 Xem tài liệu](./docs/get_url.md) |
| **search_sticker** | Tìm sticker | Tìm kiếm tư liệu sticker theo từ khóa | [📖 Xem tài liệu](./docs/search_sticker.md) |
| **objs_to_str_list** | Danh sách đối tượng sang chuỗi | Chuyển danh sách đối tượng sang định dạng danh sách chuỗi | [📖 Xem tài liệu](./docs/objs_to_str_list.md) |
| **str_list_to_objs** | Danh sách chuỗi sang đối tượng | Chuyển danh sách chuỗi sang định dạng danh sách đối tượng | [📖 Xem tài liệu](./docs/str_list_to_objs.md) |
| **str_to_list** | Chuỗi sang danh sách | Chuyển chuỗi sang định dạng danh sách | [📖 Xem tài liệu](./docs/str_to_list.md) |
| **timelines** | Tạo timeline | Tạo cấu hình timeline cho chỉnh sửa video | [📖 Xem tài liệu](./docs/timelines.md) |
| **audio_timelines** | Timeline âm thanh | Tính toán timeline dựa trên thời lượng âm thanh | [📖 Xem tài liệu](./docs/audio_timelines.md) |
| **audio_infos** | Thông tin âm thanh | Tạo thông tin âm thanh từ URL và timeline | [📖 Xem tài liệu](./docs/audio_infos.md) |
| **imgs_infos** | Thông tin hình ảnh | Tạo thông tin hình ảnh từ URL và timeline | [📖 Xem tài liệu](./docs/imgs_infos.md) |
| **caption_infos** | Thông tin phụ đề | Tạo thông tin phụ đề từ văn bản và timeline | [📖 Xem tài liệu](./docs/caption_infos.md) |
| **effect_infos** | Thông tin hiệu ứng | Tạo thông tin hiệu ứng từ tên và timeline | [📖 Xem tài liệu](./docs/effect_infos.md) |
| **keyframes_infos** | Thông tin keyframe | Tạo thông tin keyframe từ cấu hình | [📖 Xem tài liệu](./docs/keyframes_infos.md) |
| **video_infos** | Thông tin video | Tạo thông tin video từ URL và timeline | [📖 Xem tài liệu](./docs/video_infos.md) |

## Ví dụ sử dụng API

### Ví dụ quy trình làm việc

Khám phá các ví dụ quy trình thực tế để tìm hiểu cách tích hợp CapCut Mate với các nền tảng tự động hóa như Coze và n8n:

👉 [Xem ví dụ quy trình làm việc](https://jcaigc.cn/workflow)

### Tạo bản nháp
```bash
curl -X POST "http://localhost:30000/openapi/capcut-mate/v1/create_draft" \
-H "Content-Type: application/json" \
-d '{"width": 1080, "height": 1920}'
```

### Thêm video
```bash
curl -X POST "http://localhost:30000/openapi/capcut-mate/v1/add_videos" \
-H "Content-Type: application/json" \
-d '{
  "draft_url": "http://localhost:30000/openapi/capcut-mate/v1/get_draft?draft_id=20251126212753cab03392",
  "video_infos": [
    {
      "url": "https://example.com/video.mp4",
      "start": 0,
      "end": 1000000
    }
  ]
}'
```

## Tài liệu API
- Truy cập cục bộ: http://localhost:30000/docs
- Phiên bản ReDoc: http://localhost:30000/redoc

## Ứng dụng khách Trợ lý Jianying

Ứng dụng khách Trợ lý Jianying cung cấp một giao diện máy tính để bàn tiện lợi. Dưới đây là các cách khởi động:

### Hướng dẫn quyền Sandbox trên macOS

Khi chạy trên macOS, ứng dụng có thể yêu cầu quyền truy cập vào một số thư mục cụ thể. Vui lòng làm theo các bước sau:

1. Nếu xuất hiện hộp thoại yêu cầu quyền trong lần chạy đầu tiên, hãy cho phép ứng dụng truy cập các thư mục cần thiết
2. Để cấu hình thủ công, vào `System Preferences > Security & Privacy > Privacy > Folder Access`
3. Đảm bảo ứng dụng CapCut Mate đã được thêm vào danh sách được phép

Để biết thêm chi tiết, vui lòng tham khảo [Hướng dẫn cấu hình quyền Sandbox trên macOS](./docs/macos_sandbox_setup.md).

1. Cài đặt phụ thuộc

```bash
# Chuyển nguồn mirror npm - cho Windows
set ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/

# Chuyển nguồn mirror yarn - cho Linux hoặc macOS
export ELECTRON_MIRROR="https://npmmirror.com/mirrors/electron/"

# Cài đặt phụ thuộc
npm install --verbose
```

2. Khởi động dự án

```bash
npm run web:dev
npm start
```

## Liên hệ

| Loại | Phương thức | Mô tả |
|------|-------------|-------|
| 📱 Nhóm WeChat | <div align="center"><img src="./assets/wechat-q.jpg" width="200" alt="Trợ lý Jianying"></div> | Nhóm thảo luận cộng đồng mã nguồn mở |
| 💬 WeChat | <div align="center"><img src="./assets/wechat.jpg" width="120" alt="WeChat hỗ trợ kỹ thuật"></div> | Hợp tác thương mại |
| 📧 Email | longro0211vn147@gmail.com | Hỗ trợ kỹ thuật |

---
