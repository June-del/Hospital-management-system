import os
from datetime import datetime
from typing import Optional, Type
from werkzeug.utils import secure_filename
from models import db


def generate_id(prefix: str, model: Type[db.Model]) -> str:
    """
    Generates a unique, sequential ID with a given prefix.
    Example: P-20260801-0001
    """
    today_str = datetime.utcnow().strftime("%Y%m%d")
    # This count is an approximation. For high-concurrency, a different method is needed.
    count = model.query.count() + 1
    return f"{prefix}-{today_str}-{count:04d}"


def save_uploaded_file(file_storage, upload_folder: str, allowed_extensions: set) -> Optional[str]:
    """
    Saves a file from a FileStorage object to a specified folder with a unique name.
    Validates the file extension.
    """
    if not file_storage or not file_storage.filename:
        return None

    if '.' not in file_storage.filename or file_storage.filename.rsplit('.', 1)[1].lower() not in allowed_extensions:
        return None # Invalid file type

    filename = secure_filename(file_storage.filename)
    unique_name = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{filename}"
    os.makedirs(upload_folder, exist_ok=True)
    file_storage.save(os.path.join(upload_folder, unique_name))
    return unique_name