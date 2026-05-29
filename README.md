# CapCut Mate - Dub Studio 🎬🎤

**CapCut Mate - Dub Studio** là một ứng dụng desktop mạnh mẽ được xây dựng trên nền tảng PyQt6, giúp tự động hóa quy trình lồng tiếng (dubbing), tạo phụ đề (Vietsub) và biên tập video thông minh bằng trí tuệ nhân tạo (AI).

---

## ✨ Tính năng nổi bật

### 🎤 Lồng tiếng AI Chuyên nghiệp
*   **Đa dạng giọng đọc:** Tích hợp các công cụ TTS hàng đầu như **Valtec-TTS**, **OmniVoice-TTS** (giọng đọc tự nhiên như người thật) và **Edge-TTS**.
*   **Gán giọng theo nhân vật:** Tự động nhận diện và gán giọng đọc riêng biệt cho từng nhân vật trong video.
*   **Điều chỉnh thông minh:** Tự động điều chỉnh tốc độ đọc (speed/pitch) để khớp chính xác với thời gian nói trong video gốc.

### 📝 Phụ đề AI & Vietsub
*   **Dịch thuật thông minh:** Sử dụng các mô hình ngôn ngữ lớn (LLM) như **Ollama (Qwen, Gemma)** hoặc **Cloud AI (Gemini)** để dịch thuật tự nhiên, thoát ý.
*   **Phong cách hiện đại:** Hỗ trợ nhiều kiểu phụ đề (Classic, Karaoke chạy từng từ, Highlight nhấn mạnh từ đang nói).
*   **Hiệu ứng chữ:** Tích hợp các mẫu chữ nghệ thuật từ CapCut (Huazi) và các hiệu ứng chuyển động (Fade, Bounce, Typewriter).

### 🎬 Biên tập & Tối ưu hóa
*   **Xử lý sub gốc:** Tự động nhận diện và làm mờ (Blur) hoặc che (Mask) vùng phụ đề gốc một cách thông minh.
*   **Tạo Teaser/Hook:** Tự động tạo đoạn mở đầu thu hút với kịch bản và giọng đọc được tối ưu hóa năng lượng cao.
*   **Nhạc nền:** Hỗ trợ chèn nhạc nền toàn video hoặc giữ lại âm thanh gốc với mức âm lượng tùy chỉnh.

### 🚀 Hiệu suất & Tiện ích
*   **Xử lý hàng loạt (Batch):** Thêm hàng chục video vào danh sách và để máy tự động xử lý từ A-Z.
*   **Tăng tốc phần cứng:** Hỗ trợ render bằng GPU (Nvidia NVENC) để xuất video cực nhanh.
*   **Giao diện Premium:** Thiết kế hiện đại, mượt mà với Dark Mode và các hiệu ứng tương tác cao cấp.

---

## 🛠️ Yêu cầu hệ thống

*   **Hệ điều hành:** Windows 10/11 (64-bit).
*   **Python:** Phiên bản 3.10 trở lên.
*   **Công cụ hỗ trợ:** 
    *   [FFmpeg](https://ffmpeg.org/): Để xử lý video/audio.
    *   [Ollama](https://ollama.com/): Nếu sử dụng chế độ dịch thuật Local AI (Khuyến nghị: `qwen3.5:4b` hoặc `gemma2:2b`).

---

## 🚀 Bắt đầu nhanh

### 1. Cài đặt môi trường
Mở terminal tại thư mục dự án và chạy:
```bash
# Tạo môi trường ảo
python -m venv .venv

# Kích hoạt môi trường ảo
.venv\Scripts\activate

# Cài đặt các thư viện cần thiết
pip install -r requirements.txt
```

### 2. Khởi chạy ứng dụng
```bash
python main.py
```

### 3. Đóng gói thành file .exe (Phân phối)
Dự án đã tích hợp sẵn công cụ build tự động:
```bash
python build_exe.py
```
Sau khi chạy xong, file thực thi sẽ nằm trong thư mục `dist/CapCutMate`.

---

## ⚙️ Cấu hình quan trọng

Ứng dụng sử dụng file `.env` để quản lý các thông số hệ thống. Bạn có thể chỉnh sửa trực tiếp trong tab **Cấu hình** trên giao diện:
*   `DUB_OLLAMA_BASE_URL`: Địa chỉ API của Ollama (mặc định: `http://localhost:11434`).
*   `DUB_CLOUD_API_KEY`: API Key cho Gemini (nếu dùng Cloud AI).
*   `HF_TOKEN`: Token HuggingFace (để tải các model nhận diện speaker).

---

## 📧 Liên hệ

Nếu bạn có bất kỳ câu hỏi hoặc góp ý nào, vui lòng liên hệ qua:
*   **Email:** longro0211vn147@gmail.com

---

*Made with ❤️ for Content Creators.*
