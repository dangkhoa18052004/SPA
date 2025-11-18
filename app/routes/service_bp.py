from flask import Blueprint, jsonify, current_app, render_template
from ..models import DichVu
import base64

service_bp = Blueprint("service", __name__)

@service_bp.route("", methods=["GET"])
def get_services():
    """
    API lấy danh sách tất cả dịch vụ đang hoạt động
    URL: /api/services
    """
    try:
        current_app.logger.info("=== BẮT ĐẦU LẤY DANH SÁCH DỊCH VỤ ===")
        
        # Lấy tất cả dịch vụ (bỏ filter active để debug)
        services = DichVu.query.all()
        current_app.logger.info(f"Tổng số dịch vụ trong DB: {len(services)}")
        
        # Lọc dịch vụ active
        active_services = [s for s in services if s.active]
        current_app.logger.info(f"Số dịch vụ đang hoạt động: {len(active_services)}")
        
        result = []
        for s in active_services:
            try:
                # Xử lý ảnh dịch vụ an toàn
                image_data = None
                if s.anhdichvu:
                    try:
                        if isinstance(s.anhdichvu, bytes):
                            # Nếu là bytes, decode thành string
                            image_data = base64.b64encode(s.anhdichvu).decode('utf-8')
                        else:
                            # Nếu đã là string
                            image_data = s.anhdichvu
                    except Exception as img_error:
                        current_app.logger.warning(f"Lỗi xử lý ảnh dịch vụ {s.madv}: {img_error}")
                        image_data = None
                
                service_dict = {
                    "madv": s.madv, 
                    "tendv": s.tendv, 
                    "gia": str(s.gia), 
                    "thoiluong": s.thoiluong,
                    "mota": s.mota if s.mota else "",
                    "anhdichvu": image_data
                }
                result.append(service_dict)
                
            except Exception as item_error:
                current_app.logger.error(f"Lỗi xử lý dịch vụ {s.madv}: {item_error}")
                continue
        
        current_app.logger.info(f"Số dịch vụ trả về cho frontend: {len(result)}")
        
        # Trả về format JSON đúng với frontend expect
        response_data = {
            "success": True,
            "services": result,
            "total": len(result)
        }
        
        current_app.logger.info("=== KẾT THÚC LẤY DANH SÁCH DỊCH VỤ - THÀNH CÔNG ===")
        return jsonify(response_data), 200
        
    except Exception as e:
        current_app.logger.error(f"LỖI NGHIÊM TRỌNG khi lấy danh sách dịch vụ: {str(e)}")
        current_app.logger.exception(e)  # Log full traceback
        return jsonify({
            "success": False,
            "msg": "Không thể lấy danh sách dịch vụ",
            "error": str(e)  # Chỉ để debug, xóa ở production
        }), 500

@service_bp.route("/<int:service_id>", methods=["GET"])
def get_service_details(service_id):
    """
    API lấy chi tiết một dịch vụ
    URL: /api/services/<service_id>
    """
    try:
        current_app.logger.info(f"Lấy chi tiết dịch vụ ID: {service_id}")
        
        service = DichVu.query.get(service_id)
        if not service:
            current_app.logger.warning(f"Không tìm thấy dịch vụ ID: {service_id}")
            return jsonify({
                "success": False,
                "msg": "Không tìm thấy dịch vụ"
            }), 404
        
        # Xử lý ảnh dịch vụ
        image_data = None
        if service.anhdichvu:
            try:
                if isinstance(service.anhdichvu, bytes):
                    image_data = base64.b64encode(service.anhdichvu).decode('utf-8')
                else:
                    image_data = service.anhdichvu
            except Exception as img_error:
                current_app.logger.warning(f"Lỗi xử lý ảnh dịch vụ {service_id}: {img_error}")
        
        response_data = {
            "success": True,
            "service": {
                "madv": service.madv, 
                "tendv": service.tendv, 
                "gia": str(service.gia),
                "thoiluong": service.thoiluong, 
                "donvitinh": service.donvitinh,
                "mota": service.mota if service.mota else "", 
                "active": service.active,
                "anhdichvu": image_data
            }
        }
        
        current_app.logger.info(f"Lấy chi tiết dịch vụ {service_id} thành công")
        return jsonify(response_data), 200
        
    except Exception as e:
        current_app.logger.error(f"Lỗi khi lấy chi tiết dịch vụ {service_id}: {str(e)}")
        current_app.logger.exception(e)
        return jsonify({
            "success": False,
            "msg": "Lỗi máy chủ nội bộ khi lấy chi tiết dịch vụ",
            "error": str(e)  # Chỉ để debug
        }), 500
