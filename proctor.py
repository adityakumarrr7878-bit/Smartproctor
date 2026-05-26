import base64
import json
import cv2
import numpy as np
from flask import Blueprint, request, jsonify
import mysql.connector

proctor_bp = Blueprint('proctor', __name__)

# ── Load classifiers once at module level ──────────────────
_face_cascade    = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
_face_cascade2   = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_alt2.xml')
_profile_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_profileface.xml')
_upper_cascade   = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_upperbody.xml')

# ── DB ─────────────────────────────────────────────────────
def get_db():
    return mysql.connector.connect(
        host='localhost',
        user='root',
        password='singhisking@02.01.2008',
        database='smartproctor5'
    )

# ── Face detection ─────────────────────────────────────────
def detect_faces(gray):
    """Returns count of faces using two cascades combined."""
    params = dict(scaleFactor=1.1, minNeighbors=4, minSize=(50, 50))
    f1 = _face_cascade.detectMultiScale(gray, **params)
    f2 = _face_cascade2.detectMultiScale(gray, **params)
    # Use whichever gives more detections
    count1 = len(f1) if f1 is not None and len(f1) > 0 else 0
    count2 = len(f2) if f2 is not None and len(f2) > 0 else 0
    return max(count1, count2)

# ── Object detection (phone / book heuristic) ─────────────
def detect_suspicious_object(frame, gray):
    """
    Simple heuristic: looks for rectangular objects in the lower
    half of the frame that are likely phones, books, or laptops.
    Returns True if a suspicious object is found.
    """
    h, w = gray.shape

    # Focus on lower half and sides (where someone might hold a phone)
    roi = gray[h//3:, :]

    # Edge detection to find rectangular shapes
    blurred = cv2.GaussianBlur(roi, (5, 5), 0)
    edges   = cv2.Canny(blurred, 50, 150)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    roi_area = roi.shape[0] * roi.shape[1]

    for cnt in contours:
        area = cv2.contourArea(cnt)
        # Ignore very small and very large contours
        if area < roi_area * 0.03 or area > roi_area * 0.6:
            continue

        # Check if contour is roughly rectangular (phone / book shape)
        peri  = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.04 * peri, True)

        if len(approx) == 4:
            x, y, rw, rh = cv2.boundingRect(approx)
            aspect = rw / float(rh) if rh > 0 else 0
            # Phone aspect ratio: 0.4–0.7  |  Book: 0.6–1.0  |  Laptop screen: 1.2–1.8
            if (0.35 <= aspect <= 0.75) or (0.6 <= aspect <= 1.05) or (1.15 <= aspect <= 1.9):
                return True

    return False

# ── Save violation to DB ───────────────────────────────────
def _save_violation(exam_id, roll, violation_type):
    if not exam_id or not roll:
        return
    try:
        db  = get_db()
        cur = db.cursor(dictionary=True)
        cur.execute(
            "SELECT id, counts FROM live_violations WHERE exam_id=%s AND roll_number=%s",
            (exam_id, roll)
        )
        row = cur.fetchone()
        if row:
            counts = json.loads(row['counts']) if isinstance(row['counts'], str) else (row['counts'] or {})
            counts[violation_type] = counts.get(violation_type, 0) + 1
            cur.execute("UPDATE live_violations SET counts=%s WHERE id=%s",
                        (json.dumps(counts), row['id']))
        else:
            counts = {violation_type: 1}
            cur.execute(
                "INSERT INTO live_violations (exam_id, roll_number, counts) VALUES (%s,%s,%s)",
                (exam_id, roll, json.dumps(counts))
            )
        db.commit()
        db.close()
        print(f'[Proctor] Violation saved: {violation_type} | exam={exam_id} roll={roll} | counts={counts}')
    except Exception as e:
        print(f'[Proctor] _save_violation error: {e}')

# ── Main analyze endpoint ──────────────────────────────────
@proctor_bp.route('/proctor/analyze', methods=['POST'])
def analyze():
    try:
        data     = request.get_json()
        img_data = data.get('image', '')
        exam_id  = data.get('exam_id')
        roll     = data.get('roll_number', '')

        if not img_data or ',' not in img_data:
            return jsonify({'violation': False})

        # Decode base64 image
        _, encoded = img_data.split(',', 1)
        img_bytes  = base64.b64decode(encoded)
        np_arr     = np.frombuffer(img_bytes, np.uint8)
        frame      = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        if frame is None:
            return jsonify({'violation': False})

        # Work on grayscale for detection
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)   # improve contrast for better detection

        # 1. Face count
        num_faces = detect_faces(gray)
        print(f'[Proctor] Frame analyzed | faces={num_faces} | exam={exam_id} roll={roll}')

        if num_faces == 0:
            _save_violation(exam_id, roll, 'no_face')
            return jsonify({'violation': True, 'violation_type': 'no_face'})

        if num_faces > 1:
            _save_violation(exam_id, roll, 'multi_face')
            return jsonify({'violation': True, 'violation_type': 'multi_face'})

        # 2. Object detection (only if exactly 1 face, so not a false positive)
        if detect_suspicious_object(frame, gray):
            _save_violation(exam_id, roll, 'object_detected')
            return jsonify({'violation': True, 'violation_type': 'object_detected'})

        return jsonify({'violation': False})

    except Exception as e:
        print(f'[Proctor] analyze error: {e}')
        return jsonify({'violation': False})

# ── Log tab-switch violation ───────────────────────────────
@proctor_bp.route('/proctor/log_violation', methods=['POST'])
def log_violation():
    try:
        data           = request.get_json()
        exam_id        = data.get('exam_id')
        roll           = data.get('roll_number', '')
        violation_type = data.get('violation_type', '')
        if exam_id and roll and violation_type:
            _save_violation(exam_id, roll, violation_type)
        return jsonify({'status': 'ok'})
    except Exception as e:
        print(f'[Proctor] log_violation error: {e}')
        return jsonify({'status': 'error'})

# ── Debug: view current violations for a session ───────────
@proctor_bp.route('/proctor/debug/<int:exam_id>/<roll>', methods=['GET'])
def debug_violations(exam_id, roll):
    try:
        db  = get_db()
        cur = db.cursor(dictionary=True)
        cur.execute(
            "SELECT * FROM live_violations WHERE exam_id=%s AND roll_number=%s",
            (exam_id, roll)
        )
        row = cur.fetchone()
        db.close()
        return jsonify(row if row else {'message': 'No violations recorded yet'})
    except Exception as e:
        return jsonify({'error': str(e)})
