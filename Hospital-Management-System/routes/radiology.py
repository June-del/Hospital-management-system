from flask import Blueprint

from models import ImagingService, RadiologyRequest

radiology_bp = Blueprint("radiology", __name__, template_folder="../templates/radiology")


@radiology_bp.route("/radiology")
def index():
    return "Radiology dashboard placeholder.", 200
