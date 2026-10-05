"""Hạng thành viên, tính lại từ ledger điểm (không lưu số dư riêng nên luôn khớp đối soát).

Điểm xét hạng (qualifying points):
- Cộng: điểm tích từ thanh toán (type='earn').
- Trừ: hoàn tác điểm tích khi hoàn tiền (type='refund' có points_delta âm).
- Không ảnh hưởng: đổi điểm/đổi thưởng (redeem, reward_redeem) và hoàn lại điểm đã đổi
  (refund có points_delta dương) – dùng điểm không làm tụt hạng.
- Điều chỉnh thủ công (adjustment_add/subtract) chỉ được tính khi bật tier_count_adjustments.
Xét trên toàn bộ lịch sử (điểm giai đoạn 3A không hết hạn), không bao giờ âm.
"""
from sqlalchemy import func, case, and_, or_

from ..extensions import db
from ..models import LoyaltyPointTransaction
from . import loyalty_service

DEFAULT_TIERS = [
    dict(code='member', name='Thành viên', min_points=0),
    dict(code='silver', name='Bạc', min_points=200),
    dict(code='gold', name='Vàng', min_points=500),
    dict(code='diamond', name='Kim cương', min_points=1000),
]
MAX_TIERS = 10


def tiers(config=None):
    config = config or loyalty_service.get_config()
    return [dict(t) for t in (config.tier_thresholds or DEFAULT_TIERS)]


def counts_adjustments(config=None):
    config = config or loyalty_service.get_config()
    return bool(config.tier_count_adjustments)


def qualifying_points(makh, config=None):
    T = LoyaltyPointTransaction
    counted = or_(T.type == 'earn', and_(T.type == 'refund', T.points_delta < 0))
    if counts_adjustments(config):
        counted = or_(counted, T.type.in_(['adjustment_add', 'adjustment_subtract']))
    total = db.session.query(func.coalesce(func.sum(case((counted, T.points_delta), else_=0)), 0)).filter(
        T.makh == makh).scalar()
    return max(int(total or 0), 0)


def tier_for(points, tier_list):
    current = tier_list[0]
    for tier in tier_list:
        if points >= tier['min_points']:
            current = tier
    return current


def tier_status(makh, config=None):
    config = config or loyalty_service.get_config()
    tier_list = tiers(config)
    points = qualifying_points(makh, config)
    current = tier_for(points, tier_list)
    index = tier_list.index(current)
    upcoming = tier_list[index + 1] if index + 1 < len(tier_list) else None
    if upcoming:
        span = upcoming['min_points'] - current['min_points']
        progress = round((points - current['min_points']) / span * 100, 1) if span > 0 else 100.0
        to_next = upcoming['min_points'] - points
    else:
        progress, to_next = 100.0, 0
    return dict(qualifying_points=points, tier=current, next_tier=upcoming,
                points_to_next=max(to_next, 0), progress_percent=min(max(progress, 0.0), 100.0),
                tiers=tier_list, counts_adjustments=bool(config.tier_count_adjustments))


def validate_tiers(raw):
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_TIERS:
        raise loyalty_service.LoyaltyError(f'Cần từ 1 đến {MAX_TIERS} hạng')
    result, codes = [], set()
    for row in raw:
        if not isinstance(row, dict):
            raise loyalty_service.LoyaltyError('Hạng không hợp lệ')
        code = str(row.get('code', '')).strip().lower()
        name = str(row.get('name', '')).strip()
        points = row.get('min_points')
        if not code or len(code) > 30 or not code.replace('_', '').replace('-', '').isalnum():
            raise loyalty_service.LoyaltyError('Mã hạng chỉ gồm chữ, số, "-" hoặc "_" (tối đa 30 ký tự)')
        if not name or len(name) > 50:
            raise loyalty_service.LoyaltyError('Tên hạng bắt buộc, tối đa 50 ký tự')
        if isinstance(points, bool) or not isinstance(points, int) or points < 0 or points > 100_000_000:
            raise loyalty_service.LoyaltyError('Ngưỡng điểm phải là số nguyên không âm')
        if code in codes:
            raise loyalty_service.LoyaltyError('Mã hạng bị trùng')
        codes.add(code)
        result.append(dict(code=code, name=name, min_points=points))
    if result[0]['min_points'] != 0:
        raise loyalty_service.LoyaltyError('Hạng đầu tiên phải bắt đầu từ 0 điểm')
    if any(b['min_points'] <= a['min_points'] for a, b in zip(result, result[1:])):
        raise loyalty_service.LoyaltyError('Ngưỡng điểm phải tăng dần')
    return result


def update_policy(data):
    if not isinstance(data, dict) or set(data) - {'tiers', 'count_adjustments'}:
        raise loyalty_service.LoyaltyError('Cấu hình hạng không hợp lệ')
    config = loyalty_service.get_config()
    if 'tiers' in data:
        config.tier_thresholds = validate_tiers(data['tiers'])
    if 'count_adjustments' in data:
        if not isinstance(data['count_adjustments'], bool):
            raise loyalty_service.LoyaltyError('count_adjustments phải là boolean')
        config.tier_count_adjustments = data['count_adjustments']
    db.session.add(config)
    db.session.flush()
    return config


def serialize_policy(config=None):
    config = config or loyalty_service.get_config()
    return dict(tiers=tiers(config), count_adjustments=bool(config.tier_count_adjustments))
