from flask import Flask, request, jsonify
import os
from passport_ocr import get_data
from orientation_detector import detect_face, rotate_bound
import cv2
from pdf_extractor import process_pdf
from datetime import datetime
import hashlib
from db_utils import initialize_database, get_cached_result, cache_result

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'pdf'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


initialize_database()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_detected_face(img):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"detected_face_{timestamp}.jpeg"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    cv2.imwrite(filepath, img, [cv2.IMWRITE_JPEG_QUALITY, 95])
    return filepath

def remove_temporary_files(detected_face_path, extracted_image_path=None):
    if os.path.exists(detected_face_path):
        os.remove(detected_face_path)
    if extracted_image_path and os.path.exists(extracted_image_path):
        os.remove(extracted_image_path)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if file and allowed_file(file.filename):
        # Calculate hash of the uploaded file content
        file_hash = hashlib.md5(file.read()).hexdigest()
        file.seek(0)  

        # Check cache before saving or processing
        cached_result = get_cached_result(file_hash)
        if cached_result:
            return jsonify({
                'file_name': cached_result['file_name'],
                'result': cached_result['result']
            }), 200

        # If not in cache, save and process the file
        filename = file.filename
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        extracted_image_path = None
        if filename.endswith('.pdf'):
            extracted_image_path = process_pdf(filepath, app.config['UPLOAD_FOLDER'])
            filepath = extracted_image_path  # Use the extracted image for further processing

        # Perform orientation detection and face detection
        img = cv2.imread(filepath)
        if img is None:
            return jsonify({'error': 'Failed to load uploaded image'}), 500

        start_angle = 0
        end_angle = 270
        step_angle = 90
        face_detected = False
        rotated_img = img.copy()

        # Attempt face detection with rotation
        while not face_detected and start_angle <= end_angle:
            rotated_img = rotate_bound(img, start_angle)
            face_detected, face = detect_face(rotated_img)
            start_angle += step_angle

        if not face_detected:
            return jsonify({'error': 'No face detected after rotating through 270 degrees.'}), 404

        detected_face_path = save_detected_face(rotated_img)

        try:
            data = get_data(detected_face_path)
            '''
            print("Data extracted:", data)  
            '''
            remove_temporary_files(detected_face_path, extracted_image_path)
            
            # Cache the result in the database
            cache_result(file_hash, filename, data)
            
            return jsonify({
                'file_name': filename,
                'result': data
            }), 200
        except Exception as e:
            remove_temporary_files(detected_face_path, extracted_image_path)
            return jsonify({'error': str(e)}), 500
    else:
        return jsonify({'error': 'Allowed file types are jpg, jpeg, pdf only'}), 400

if __name__ == '__main__':
    app.run(debug=True)