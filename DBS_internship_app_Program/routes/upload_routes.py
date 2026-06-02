from flask import Blueprint
from flask import request
from flask import jsonify

from utils.cloudinary_utils import upload_resume

upload_bp = Blueprint(
    'upload',
    __name__
)


@upload_bp.route(
    '/upload-resume',
    methods=['POST']
)

def upload_resume_route():

    if 'resume' not in request.files:

        return jsonify({
            "error": "No file uploaded"
        }), 400

    file = request.files['resume']

    result = upload_resume(file)

    return jsonify(result)