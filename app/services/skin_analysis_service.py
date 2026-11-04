"""Customer skin (acne) analysis through the local BinSpa AI service (BinSpa_AI repo, api/server.py).

The website only forwards the photo and keeps the result; all AI logic lives in the AI service.
- Nothing is analysed or stored without the customer's explicit consent (CONSENT_VERSION).
- The photo is decoded, EXIF-rotated and re-encoded as JPEG here; the same bytes are sent to the AI and
  stored, so the returned boxes match the stored photo.
- "retake_photo" results (photo unfit for analysis) are returned but never stored.
- "demo" results (AI service started with --demo): every lesion gets its top-1 type, flagged low_confidence when
  the AI's calibrated probability is below its threshold; the page says the types are only indicative.
- Photos are private: uploads/skin/<makh>/, served only to their owner; deleting an analysis deletes the photo.

AI contract (BinSpa_AI scripts/phase2/predict_acne_type.py AcnePipeline.analyze): predictions[] = bbox (pixels),
detection_confidence (detector), top3 [{type, probability}] (temperature-calibrated) and type_status
'confident' | 'uncertain' (top-1 against the calibrated accept threshold). A lesion is "reliable" only in an 'ok'
result, with type_status 'confident' and a known type with a probability in [0, 1]; nothing else is used for the
highlights or for service recommendations. Each lesion keeps the id of its place in the AI's predictions.
"""
import io
import math
import os
import uuid
from datetime import datetime

import requests
from flask import current_app

from ..extensions import db
from ..skin_models import SkinAnalysis

CONSENT_VERSION = '2026-10-21'
FORMATS = {'JPEG', 'PNG', 'WEBP', 'MPO'}
MAX_PIXELS = 40_000_000
MAX_SIDE = 4096
TYPE_LABELS = {
    'closed_comedo': 'Mụn đầu trắng',
    'open_comedo': 'Mụn đầu đen',
    'papule': 'Sẩn viêm',
    'pustule': 'Mụn mủ',
    'nodule': 'Nốt (mụn bọc)',
}
HIGHLIGHT_TYPES = 3  # design default, not a medical threshold


class SkinAnalysisError(Exception):
    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.message, self.status_code = message, status_code


def prepare_image(data):
    """bytes -> (JPEG bytes, width, height), EXIF orientation applied."""
    from PIL import Image, ImageOps
    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    try:
        img = Image.open(io.BytesIO(data))
        if img.format not in FORMATS:
            raise SkinAnalysisError('Chỉ nhận ảnh JPG, PNG hoặc WebP.')
        img = ImageOps.exif_transpose(img).convert('RGB')
    except SkinAnalysisError:
        raise
    except Exception:
        raise SkinAnalysisError('Không đọc được ảnh. Vui lòng chọn ảnh khác.')
    if max(img.size) > MAX_SIDE:
        img.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
    out = io.BytesIO()
    img.save(out, 'JPEG', quality=92)
    return out.getvalue(), img.width, img.height


def call_ai(jpeg):
    """POST the photo to the AI service -> its JSON result."""
    url = current_app.config.get('AI_SKIN_URL', '').rstrip('/')
    if not url:
        raise SkinAnalysisError('Chức năng phân tích da chưa được cấu hình.', 503)
    headers = {}
    if current_app.config.get('AI_SKIN_KEY'):
        headers['X-API-Key'] = current_app.config['AI_SKIN_KEY']
    try:
        r = requests.post(f'{url}/analyze', files={'image': ('photo.jpg', jpeg, 'image/jpeg')}, headers=headers,
                          timeout=current_app.config.get('AI_SKIN_TIMEOUT', 60))
    except requests.RequestException:
        current_app.logger.warning('skin analysis: AI service unreachable at %s', url)
        raise SkinAnalysisError('Dịch vụ phân tích da đang tạm ngừng. Vui lòng thử lại sau.', 503)
    if r.status_code != 200:
        current_app.logger.warning('skin analysis: AI service returned %s', r.status_code)
        raise SkinAnalysisError('Dịch vụ phân tích da gặp lỗi. Vui lòng thử lại sau.', 502)
    return r.json()


def _number(value):
    if isinstance(value, bool):
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _probability(value):
    value = _number(value)
    return value if value is not None and 0 <= value <= 1 else None


def _bbox(value):
    """[x1, y1, x2, y2] with x2 > x1 and y2 > y1, else None (the lesion is listed but not drawn)."""
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return None
    box = [_number(v) for v in value]
    if None in box or box[2] <= box[0] or box[3] <= box[1]:
        return None
    return box


def _option(item):
    """A top3 entry with a known type and a valid probability, else None."""
    if not isinstance(item, dict) or item.get('type') not in TYPE_LABELS:
        return None
    probability = _probability(item.get('probability'))
    return None if probability is None else dict(type=item['type'], label=TYPE_LABELS[item['type']],
                                                  probability=probability)


def lesions(result):
    """AI predictions -> what the page needs: id, box, and the type when the AI is confident (every type in demo).
    A missing type_status counts as not confident; an invalid top-1 is never replaced by the next option."""
    status, out = result.get('analysis_status'), []
    predictions = result.get('predictions')
    for i, p in enumerate(predictions if isinstance(predictions, list) else [], 1):
        p = p if isinstance(p, dict) else {}
        top3 = p.get('top3') if isinstance(p.get('top3'), list) else []
        top = _option(top3[0]) if top3 else None
        confident = p.get('type_status') == 'confident'
        shown = top is not None and (status == 'demo' or (confident and status == 'ok'))
        out.append(dict(id=i, bbox=_bbox(p.get('bbox')), type=top['type'] if shown else None,
                        label=top['label'] if shown else 'Chưa xác định loại',
                        probability=top['probability'] if shown else None,
                        low_confidence=shown and not confident,
                        reliable=shown and confident and status == 'ok',
                        alternatives=[o for o in map(_option, top3[1:]) if o] if shown else []))
    return out


def counts(items):
    c = {}
    for x in items:
        if x['type']:
            c[x['type']] = c.get(x['type'], 0) + 1
    return c


def type_groups(items, demo=False):
    """Reliable lesions per type, strongest first: highest AI confidence in the group, then count, then type code.
    demo=True: every typed lesion of a demo result counts (service suggestions only, never the highlights).
    max_probability is the best single lesion of the group, not a confidence for the whole type."""
    groups = {}
    for x in items:
        if x['reliable'] or (demo and x['type']):
            group = groups.setdefault(x['type'], dict(type=x['type'], label=x['label'], count=0, max_probability=0.0))
            group['count'] += 1
            group['max_probability'] = max(group['max_probability'], x['probability'])
    return sorted(groups.values(), key=lambda g: (-g['max_probability'], -g['count'], g['type']))


def public_result(result):
    items = lesions(result)
    check = result.get('input_check') if isinstance(result.get('input_check'), dict) else {}
    retake = result.get('analysis_status') == 'retake_photo'
    return dict(status=result.get('analysis_status'), message=result.get('message'),
                reasons=[r['message'] for r in check.get('reasons') or [] if isinstance(r, dict) and r.get('message')],
                image_size=result.get('image_size'), lesion_count=None if retake else len(items), lesions=items,
                reliable_count=sum(1 for x in items if x['reliable']),
                highlights=type_groups(items)[:HIGHLIGHT_TYPES],
                type_counts=counts(items), type_labels=TYPE_LABELS, disclaimer=result.get('disclaimer'))


def serialize(row):
    return dict(id=row.id, created_at=row.created_at.isoformat() + 'Z', has_image=bool(row.image_file),
                image_url=f'/api/me/skin-analyses/{row.id}/image' if row.image_file else None,
                **public_result(row.result))


def folder(makh):
    path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'skin', str(int(makh)))
    os.makedirs(path, exist_ok=True)
    return path


def analyze(makh, data, consent):
    if not consent:
        raise SkinAnalysisError('Vui lòng đồng ý cho Bin Spa lưu ảnh và kết quả phân tích trước khi tiếp tục.')
    if not data:
        raise SkinAnalysisError('Vui lòng chọn hoặc chụp một ảnh khuôn mặt.')
    jpeg, width, height = prepare_image(data)
    result = call_ai(jpeg)
    status = result.get('analysis_status')
    if status == 'retake_photo':
        return dict(saved=False, **public_result(result))
    if status not in ('ok', 'location_only', 'demo'):
        raise SkinAnalysisError('Dịch vụ phân tích da trả về kết quả không hợp lệ.', 502)
    name = f'{uuid.uuid4().hex}.jpg'
    with open(os.path.join(folder(makh), name), 'wb') as f:
        f.write(jpeg)
    items = lesions(result)
    row = SkinAnalysis(makh=makh, status=status, lesion_count=len(items),
                       confident_count=sum(1 for x in items if x['type'] and not x['low_confidence']),
                       type_counts=counts(items), result=result,
                       image_file=name, image_width=width, image_height=height, consent_version=CONSENT_VERSION,
                       consent_at=datetime.utcnow())
    db.session.add(row)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        os.remove(os.path.join(folder(makh), name))
        raise
    return dict(saved=True, **serialize(row))


def owned(makh, analysis_id):
    row = SkinAnalysis.query.filter_by(id=analysis_id, makh=makh).first()
    if row is None:
        raise SkinAnalysisError('Không tìm thấy kết quả phân tích.', 404)
    return row


def history(makh, limit=20):
    rows = SkinAnalysis.query.filter_by(makh=makh).order_by(SkinAnalysis.created_at.desc()).limit(limit).all()
    return [dict(id=r.id, created_at=r.created_at.isoformat() + 'Z', status=r.status, lesion_count=r.lesion_count,
                 confident_count=r.confident_count, type_counts=r.type_counts) for r in rows]


def image_path(makh, analysis_id):
    row = owned(makh, analysis_id)
    path = os.path.join(folder(makh), row.image_file or '')
    if not row.image_file or not os.path.isfile(path):
        raise SkinAnalysisError('Ảnh đã bị xóa.', 404)
    return path


def delete(makh, analysis_id):
    row = owned(makh, analysis_id)
    if row.image_file:
        path = os.path.join(folder(makh), row.image_file)
        if os.path.isfile(path):
            os.remove(path)
    db.session.delete(row)
    db.session.commit()
    from . import skin_recommendation_service
    skin_recommendation_service.forget(makh, analysis_id)
