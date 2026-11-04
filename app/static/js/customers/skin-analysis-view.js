// Soi da bằng AI: các hàm thuần chọn điểm nổi bật, sắp xếp chi tiết và phân trang (test: tests/skin-analysis-view.test.cjs).
// Thứ tự hiển thị dùng điểm số thực tế; không thay đổi cờ reliable do server tính.
(function (root) {
    const TOP_POINTS = 8;   // tối đa 8 kết quả có điểm số cao nhất, không phải ngưỡng y khoa
    const PAGE_SIZE = 20;

    const isProbability = (p) => typeof p === 'number' && Number.isFinite(p) && p >= 0 && p <= 1;

    // Độ tin cậy hợp lệ giảm dần; điểm chưa có độ tin cậy nằm cuối; bằng nhau giữ thứ tự gốc (id).
    function sortDetail(lesions) {
        const score = (l) => (isProbability(l.probability) ? l.probability : -1);
        return lesions.slice().sort((a, b) => score(b) - score(a) || a.id - b.id);
    }

    function topPoints(lesions, limit = TOP_POINTS) {
        return sortDetail(lesions).slice(0, limit);
    }

    // Mặc định vẽ cùng các điểm trong danh sách bên phải; trang chi tiết hiện toàn bộ vị trí.
    function visiblePoints(data, view) {
        const lesions = data.lesions || [];
        const drawable = lesions.filter((l) => l.bbox);
        let points;
        if (view.showAll) points = sortDetail(drawable);
        else points = topPoints(lesions).filter((l) => l.bbox);
        const selected = drawable.find((l) => l.id === view.selectedId);
        if (selected && !points.includes(selected)) points = points.concat(selected);
        return points;
    }

    function escapeHtml(value) {
        return String(value ?? '').replace(/[&<>"']/g, (c) => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
        })[c]);
    }

    root.SkinAnalysisView = { TOP_POINTS, PAGE_SIZE, isProbability, sortDetail, topPoints, visiblePoints, escapeHtml };
})(typeof window !== 'undefined' ? window : globalThis);
