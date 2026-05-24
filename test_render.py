from __future__ import annotations

import os
import sys
import json
import shutil
from pathlib import Path

# Add root folder to sys.path to guarantee clean imports on Windows
ROOT_DIR = Path(__file__).parent.resolve()
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from dotenv import load_dotenv
load_dotenv(dotenv_path=ROOT_DIR / ".env")

# Force Cloud AI Mode for semantic search and teaser evaluation
os.environ["DUB_AI_MODE"] = "cloud"

from tools.dub_studio.process_utils import safe_print, ensure_job_dirs
from tools.dub_studio.cli_parts.render import do_render

def run_test_render():
    safe_print("=" * 70)
    safe_print("KHỞI ĐỘNG HỆ THỐNG TEST RENDER - CAPCUT-MATE DUB STUDIO")
    safe_print("=" * 70)
    
    # 1. Xác định file và thư mục
    video_input = ROOT_DIR / "Test.mp4"
    real_analysis_path = ROOT_DIR / "temp" / "real_analysis.json"
    
    if not video_input.exists():
        safe_print(f"[ERROR] Không tìm thấy file video đầu vào: {video_input}")
        return
        
    if not real_analysis_path.exists():
        safe_print(f"[ERROR] Không tìm thấy dữ liệu phân tích mẫu: {real_analysis_path}")
        return

    # 2. Khởi tạo Job ID mới cho test
    job_id = "test_teaser_job_new"
    safe_print(f"[INFO] Khởi tạo job test mới: {job_id}")
    dirs = ensure_job_dirs(job_id)
    
    # Thư mục đích cho các file cấu hình tạm
    temp_dir = ROOT_DIR / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    analysis_json_path = temp_dir / "test_analysis.json"
    render_options_json_path = temp_dir / "test_render_options.json"
    output_json_path = temp_dir / "test_output_result.json"

    # 3. Chuẩn bị file analysis.json động phù hợp với môi trường hiện tại
    safe_print("[INFO] Đang nạp dữ liệu phân tích và điều chỉnh đường dẫn...")
    with open(real_analysis_path, "r", encoding="utf-8") as f:
        analysis_data = json.load(f)
        
    # Cập nhật thông tin đường dẫn động của hệ thống hiện tại
    analysis_data["jobId"] = job_id
    analysis_data["inputPath"] = str(video_input)
    analysis_data["thumbnailPath"] = str(dirs["analysis"] / "thumbnail.jpg")
    analysis_data["analysisDir"] = str(dirs["analysis"])
    
    # Ghi lại file analysis tạm
    with open(analysis_json_path, "w", encoding="utf-8") as f:
        json.dump(analysis_data, f, ensure_ascii=False, indent=2)
    safe_print(f"[SUCCESS] Đã chuẩn bị xong file phân tích: {analysis_json_path}")

    # 4. Chuẩn bị file render_options.json
    # - sourceSubtitleCleanupMode: localized_blur (Kích hoạt CHE SUB bằng Gaussian Blur)
    # - voiceMapping: Lồng tiếng nhiều nhân vật sử dụng bộ giọng nói Việt chất lượng cao (Valtec/Vieneu)
    # - introHook: Bật Teaser dạng montage dài 15 giây sử dụng giọng Thanh Tâm tự nhiên
    safe_print("[INFO] Đang khởi tạo tùy chọn Render nâng cao (Lồng tiếng nhiều nhân vật, Che Sub, Teaser)...")
    render_options = {
        "sourceSubtitleCleanupMode": "localized_blur",
        "videoCodecMode": "cpu_stable",
        "voiceMapping": {
            "speaker_1": "valtec:thanh_tam",  # Người kể chuyện (Nam chính)
            "speaker_2": "valtec:sf",         # Chân Hoàn / Đoan Phi (Nữ chính)
            "speaker_3": "valtec:nf",         # Long Nguyệt (Nữ trẻ)
            "speaker_4": "valtec:nm1",        # Cận Tịch (Nữ trung niên)
            "speaker_5": "valtec:nm2"         # Thái y Ngụy Lâm (Nam từ tốn)
        },
        "introHook": {
            "enabled": True,
            "mode": "montage",
            "voice": "valtec:thanh_tam",
            "clipDurationMs": 15000,
            "useBackgroundAudio": True,
            "backgroundVolume": 0.08
        },
        "subtitlePreset": {
            "enabled": True,
            "positionPreset": "bottom",
            "fontSize": 20,
            "fontFamily": "arial-bold",
            "fontColor": "#ffd200",      # Chữ màu vàng nổi bật
            "strokeColor": "#000000",    # Viền đen sắc nét
            "strokeWidth": 2,
            "cleanupBlurStrength": 80    # Che sub cực mạnh (mờ 80%)
        },
        "outputTargets": {
            "mp4": True,
            "draft": False
        }
    }
    
    with open(render_options_json_path, "w", encoding="utf-8") as f:
        json.dump(render_options, f, ensure_ascii=False, indent=2)
    safe_print(f"[SUCCESS] Đã chuẩn bị cấu hình render_options: {render_options_json_path}")

    # 5. Thực hiện render
    safe_print("\n" + "=" * 50)
    safe_print("BẮT ĐẦU QUÁ TRÌNH LỒNG TIẾNG VÀ RENDER VIDEO...")
    safe_print("=" * 50)
    
    try:
        result = do_render(
            analysis_path=analysis_json_path,
            render_options_path=render_options_json_path,
            output_json=output_json_path
        )
        
        # 6. Sao chép kết quả ra thư mục gốc để người dùng dễ xem
        rendered_mp4 = Path(result.get("outputVideoPath", ""))
        teaser_mp4 = dirs["render"] / "intro_hook_rendered.mp4"
        
        safe_print("\n" + "=" * 50)
        safe_print("HOÀN THÀNH QUÁ TRÌNH RENDER THÀNH CÔNG!")
        safe_print("=" * 50)
        
        if rendered_mp4.exists():
            dest_rendered = ROOT_DIR / "rendered_Test.mp4"
            shutil.copy2(rendered_mp4, dest_rendered)
            safe_print(f"[SUCCESS] Đã xuất video hoàn thiện (Lồng tiếng + Teaser + Che Sub) ra: {dest_rendered}")
            
        if teaser_mp4.exists():
            dest_teaser = ROOT_DIR / "teaser_Test.mp4"
            shutil.copy2(teaser_mp4, dest_teaser)
            safe_print(f"[SUCCESS] Đã xuất video teaser lẻ ra: {dest_teaser}")
            
        safe_print(f"[INFO] Chi tiết logs kết quả lưu tại: {output_json_path}")
        
    except Exception as e:
        safe_print(f"\n[CRITICAL ERROR] Quá trình render thất bại: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_test_render()
