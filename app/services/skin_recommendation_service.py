"""Service suggestions for one stored skin analysis: Gemini picks and explains, the server decides what is allowed.

- Evidence: only the reliable lesions of an 'ok' analysis (skin_analysis_service.type_groups). A 'demo' analysis
  uses the top-1 type of every lesion and its suggestions are flagged demo=True (shown as trial suggestions).
  location_only and analyses without usable lesions never get treatment suggestions.
- Candidates: active services the spa mapped to acne types in SKIN_SERVICE_MAP ({"papule": [madv, ...]}). Nothing
  is inferred from service names; an empty or missing map gives "no_matching_services".
- Gemini receives type codes, counts and confidence figures plus the candidate services, never the photo, boxes,
  customer data, tokens or paths, and only after the customer accepted CONSENT_VERSION in this request.
- Output is checked: known service ids only, no duplicates, matched types must be evidence the service is mapped to,
  plain-text reasons without diagnosis/cure/price claims. Price, duration and links always come from the database.
- One request at a time per analysis, a per-customer budget of Gemini calls and a short cache keyed by analysis +
  candidate catalog + prompt version. Kept in this worker process only; nothing new is stored in the database.
"""
import hashlib
import json
import re
import threading
import time

from flask import current_app

from ..extensions import db
from ..models import DichVu
from ..skin_models import SkinServiceMap
from . import ai_service
from . import skin_analysis_service as skin
from .recommendation_service import serialize_service

CONSENT_VERSION = '2026-10-23'
PROMPT_VERSION = 2
MAX_RESULTS = 3
CACHE_SECONDS = 30 * 60
CACHE_MAX = 500
CALLS_PER_WINDOW, WINDOW_SECONDS = 10, 10 * 60
MAX_REASON, MAX_SUMMARY, MAX_DESCRIPTION = 280, 400, 400
UNSAFE = re.compile(r'chữa khỏi|khỏi hẳn|khỏi hoàn toàn|dứt điểm|cam kết|đảm bảo|chẩn đoán|kê đơn|thuốc|kháng sinh'
                    r'|bệnh|nặng|100\s*%|giá tiền|mức giá|giá chỉ|giảm giá|ưu đãi|khuyến mãi|miễn phí'
                    r'|\d[\d.,]*\s*(k|đ|đồng|vnđ|vnd)\b|https?://|www\.|[<>{}]', re.I)
MESSAGES = {
    'location_only': 'Lần phân tích này chỉ xác định được vị trí, chưa đủ độ tin cậy về loại mụn để gợi ý dịch vụ. '
                     'Bạn có thể đặt lịch để chuyên viên tư vấn trực tiếp.',
    'insufficient': 'Chưa có điểm nào đủ độ tin cậy để gợi ý dịch vụ. Bạn có thể đặt lịch để chuyên viên tư vấn trực tiếp.',
    'no_match': 'Hiện chưa có dịch vụ được Bin Spa chọn sẵn cho kết quả này. Bạn có thể đặt lịch để được tư vấn trực tiếp.',
}
PROMPT = (
    'Bạn hỗ trợ khách của Bin Spa chọn dịch vụ chăm sóc da để THAM KHẢO, dựa trên kết quả AI soi da đã được hệ thống '
    'lọc (chỉ gồm các điểm AI đủ tin cậy).\n'
    'Quy tắc:\n'
    '- Chỉ chọn trong "services", dùng đúng service_id; tối đa 3, phù hợp nhất trước. Trả danh sách rỗng nếu không '
    'dịch vụ nào phù hợp.\n'
    '- matched_type_codes chỉ gồm mã có trong allowed_type_codes của chính dịch vụ đó.\n'
    '- reason: 1-2 câu tiếng Việt, giọng "có thể tham khảo", gắn với nhóm mụn trong "evidence". Không chẩn đoán, '
    'không nhắc thuốc, không hứa hiệu quả hay chữa khỏi, không nói mức độ nặng nhẹ, không nêu giá, ưu đãi hay đường link.\n'
    '- highest_ai_confidence là độ tin cậy của AI ở điểm rõ nhất trong nhóm, không phải mức độ nặng hay diện tích da.\n'
    '- summary: 1 câu trung tính tóm tắt vì sao các dịch vụ này được gợi ý.\n'
    '- Nếu có mode = "demo": kết quả chạy thử, loại mụn chỉ mang tính minh họa và chưa được lọc theo độ tin cậy; '
    'reason và summary dùng giọng "gợi ý thử nghiệm", không khẳng định khách có loại mụn đó.\n'
    'Trả về đúng JSON theo schema.\n\nDỮ LIỆU: '
)
SCHEMA = {
    'type': 'OBJECT',
    'properties': {
        'summary': {'type': 'STRING'},
        'recommendations': {'type': 'ARRAY', 'items': {'type': 'OBJECT', 'properties': {
            'service_id': {'type': 'INTEGER'},
            'matched_type_codes': {'type': 'ARRAY', 'items': {'type': 'STRING'}},
            'reason': {'type': 'STRING'},
        }, 'required': ['service_id', 'matched_type_codes', 'reason']}},
    },
    'required': ['summary', 'recommendations'],
}

_lock = threading.Lock()
_cache = {}      # (makh, analysis_id, catalog version) -> (expires at, data)
_running = set()  # (makh, analysis_id)
_calls = {}      # makh -> [monotonic time of each Gemini call]


def reset():
    with _lock:
        _cache.clear()
        _running.clear()
        _calls.clear()


def forget(makh, analysis_id):
    """Drop cached suggestions of a deleted analysis."""
    with _lock:
        for key in [k for k in _cache if k[:2] == (makh, analysis_id)]:
            del _cache[key]


def _service_id(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return int(value) if isinstance(value, str) and value.strip().isdigit() else None


def service_map():
    """Approved DB assignments take precedence; an empty table falls back to SKIN_SERVICE_MAP."""
    rows = SkinServiceMap.query.order_by(SkinServiceMap.type_code, SkinServiceMap.madv).all() if mapping_schema_ready() else []
    if rows:
        mapping = {}
        for row in rows:
            if row.type_code in skin.TYPE_LABELS:
                mapping.setdefault(row.type_code, []).append(row.madv)
        return mapping
    raw = current_app.config.get('SKIN_SERVICE_MAP') or {}
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            current_app.logger.warning('skin recommendations: SKIN_SERVICE_MAP is not valid JSON, nothing is suggested')
            return {}
    if not isinstance(raw, dict):
        return {}
    return {t: [m for m in map(_service_id, ids) if m] for t, ids in raw.items()
            if t in skin.TYPE_LABELS and isinstance(ids, list)}


def mapping_schema_ready():
    # Check before querying: a missing table would abort the PostgreSQL transaction
    # and prevent even an explicitly configured environment map from being read.
    from sqlalchemy import inspect
    return inspect(db.session.connection()).has_table(SkinServiceMap.__tablename__)


def candidates(evidence):
    """Active mapped services for the evidence types -> (services, {madv: [type, ...]}, catalog version)."""
    allowed = {}
    for t, ids in service_map().items():
        if any(g['type'] == t for g in evidence):
            for madv in ids:
                allowed.setdefault(madv, []).append(t)
    services = DichVu.query.filter(DichVu.madv.in_(list(allowed)), DichVu.active.is_(True)) \
        .order_by(DichVu.madv).all() if allowed else []
    allowed = {s.madv: allowed[s.madv] for s in services}
    version = hashlib.sha256(json.dumps(
        [PROMPT_VERSION] + [[s.madv, s.tendv, str(s.gia), s.thoiluong, s.mota, allowed[s.madv]] for s in services],
        ensure_ascii=False, default=str).encode()).hexdigest()[:16]
    return services, allowed, version


def _clean(text, limit):
    """Plain, short, claim-free text, else None (the caller uses a neutral sentence instead)."""
    if not isinstance(text, str):
        return None
    text = ' '.join(text.split())
    return text if text and len(text) <= limit and not UNSAFE.search(text) else None


def _labels(types):
    return ', '.join(skin.TYPE_LABELS[t].lower() for t in types)


def _ask(evidence, services, allowed, demo=False):
    facts = dict(
        evidence=[dict(type_code=g['type'], name=g['label'], reliable_point_count=g['count'],
                       highest_ai_confidence=round(g['max_probability'], 2)) for g in evidence],
        services=[dict(service_id=s.madv, name=s.tendv, description=(s.mota or '')[:MAX_DESCRIPTION],
                       category=s.category.name if s.category and s.category.active else None,
                       allowed_type_codes=allowed[s.madv]) for s in services])
    if demo:
        facts['mode'] = 'demo'
    response = ai_service.call_gemini({
        'contents': [{'role': 'user', 'parts': [{'text': PROMPT + json.dumps(facts, ensure_ascii=False)}]}],
        'generationConfig': {'temperature': 0.2, 'maxOutputTokens': 1024, 'responseMimeType': 'application/json',
                             'responseSchema': SCHEMA},
    })
    _, parts = ai_service._parts(response)
    text = ''.join(p.get('text', '') for p in parts if isinstance(p, dict)).strip()
    try:
        data = json.loads(re.sub(r'^```(json)?|```$', '', text).strip())
    except ValueError:
        data = None
    if not isinstance(data, dict) or not isinstance(data.get('recommendations'), list):
        raise ai_service.AIUpstreamError('invalid recommendation JSON')
    return data


def validate(data, allowed):
    """Gemini output -> [(madv, [type, ...], reason or None)], at most MAX_RESULTS, only what the server allowed."""
    picks, seen = [], set()
    for item in data['recommendations']:
        if not isinstance(item, dict):
            continue
        madv = _service_id(item.get('service_id'))
        if madv not in allowed or madv in seen:
            continue
        codes = item.get('matched_type_codes') if isinstance(item.get('matched_type_codes'), list) else []
        codes = [c for c in dict.fromkeys(c for c in codes if isinstance(c, str)) if c in allowed[madv]]
        if not codes:
            continue
        seen.add(madv)
        picks.append((madv, codes, _clean(item.get('reason'), MAX_REASON)))
        if len(picks) == MAX_RESULTS:
            break
    if data['recommendations'] and not picks:
        raise ai_service.AIUpstreamError('no valid recommendation')
    return picks


def _readable(text):
    """Type codes the model may echo (papule) -> the Vietnamese labels the customer sees."""
    for code, label in skin.TYPE_LABELS.items():
        text = re.sub(rf'\b{code}\b', label.lower(), text)
    return text


def _seen(demo):
    return 'mà AI ghi nhận ở chế độ thử nghiệm' if demo else 'mà AI ghi nhận đủ tin cậy'


def _card(service, codes, reason, demo=False):
    s = serialize_service(service)
    reason = _readable(reason) if reason else None
    return dict(madv=s['madv'], tendv=s['tendv'], gia=s['gia'], thoiluong=s['thoiluong'],
                category_name=s['category_name'],
                matched_types=[dict(type=t, label=skin.TYPE_LABELS[t]) for t in codes],
                reason=reason or f'Có thể tham khảo cho nhóm {_labels(codes)} {_seen(demo)} trong lần phân tích này.',
                detail_url=f'/services/{s["madv"]}', booking_url=f'/appointments/create?service={s["madv"]}')


def _start(makh, analysis_id):
    now = time.monotonic()
    with _lock:
        if (makh, analysis_id) in _running:
            raise skin.SkinAnalysisError('Đang lấy gợi ý cho lần phân tích này, vui lòng chờ.', 409)
        recent = [t for t in _calls.get(makh, []) if now - t < WINDOW_SECONDS]
        if len(recent) >= CALLS_PER_WINDOW:
            raise skin.SkinAnalysisError('Bạn đã yêu cầu gợi ý nhiều lần, vui lòng thử lại sau ít phút.', 429)
        _calls[makh] = recent + [now]
        _running.add((makh, analysis_id))


def _remember(key, data):
    now = time.monotonic()
    with _lock:
        for k in [k for k, (expires, _) in _cache.items() if expires <= now]:
            del _cache[k]
        if len(_cache) >= CACHE_MAX:
            del _cache[min(_cache, key=lambda k: _cache[k][0])]
        _cache[key] = (now + CACHE_SECONDS, data)


def recommend(makh, analysis_id, consent):
    row = skin.owned(makh, analysis_id)
    result = skin.public_result(row.result)
    demo = result['status'] == 'demo'
    base = dict(analysis_id=row.id, consent_version=CONSENT_VERSION, summary=None, message=None, recommendations=[],
                demo=demo)
    evidence = skin.type_groups(result['lesions'], demo=demo)
    if result['status'] not in ('ok', 'demo') or not evidence:
        return dict(base, status='insufficient_evidence', message=MESSAGES.get(result['status'], MESSAGES['insufficient']))
    services, allowed, version = candidates(evidence)
    if not services:
        return dict(base, status='no_matching_services', message=MESSAGES['no_match'])
    if consent != CONSENT_VERSION:
        return dict(base, status='consent_required')
    key = (makh, row.id, version)
    with _lock:
        hit = _cache.get(key)
    if hit and hit[0] > time.monotonic():
        return hit[1]
    _start(makh, row.id)
    try:
        answer = _ask(evidence, services, allowed, demo)
        picks = validate(answer, allowed)
    except ai_service.AINotConfigured:
        raise skin.SkinAnalysisError('Gợi ý dịch vụ tạm chưa sẵn sàng. Kết quả soi da vẫn được giữ nguyên.', 503)
    except ai_service.AIError as error:
        current_app.logger.warning('skin recommendations: Gemini failed for analysis %s: %s', row.id, error.message)
        raise skin.SkinAnalysisError('Chưa lấy được gợi ý dịch vụ lúc này. Kết quả soi da vẫn được giữ nguyên, '
                                     'bạn có thể thử lại.', 502)
    finally:
        with _lock:
            _running.discard((makh, row.id))
    by_id = {s.madv: s for s in services}
    if not picks:
        data = dict(base, status='no_matching_services', message=MESSAGES['no_match'])
    else:
        types = list(dict.fromkeys(t for _, codes, _ in picks for t in codes))
        summary = _clean(answer.get('summary'), MAX_SUMMARY)
        summary = _readable(summary) if summary else \
            f'Các dịch vụ dưới đây được chọn từ danh mục Bin Spa cho nhóm {_labels(types)} {_seen(demo)}.'
        data = dict(base, status='ok', summary=summary,
                    recommendations=[_card(by_id[m], c, r, demo) for m, c, r in picks])
    _remember(key, data)
    return data
