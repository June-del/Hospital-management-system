"""Compatibility shim for the legacy root-level laboratory module.

The active app imports the blueprint from routes.laboratory, so this file must not
contain broken imports or duplicated model definitions.
"""

from routes.laboratory import laboratory_bp
from models import LabTestCatalog, LabTestRequest, LabTestResult

__all__ = ["laboratory_bp", "LabTestCatalog", "LabTestRequest", "LabTestResult"]
