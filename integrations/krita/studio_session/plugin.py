"""Explicit GUI actions for one captured Krita document session.

No action runs at plugin load.  The controller deliberately retains a session
only when the active document object and its root node still match the capture.
"""
import json
from pathlib import Path

try:  # Installed package is flat; repository package keeps the shared module above us.
    from .document_session import Session
except ImportError:
    from ..document_session import Session


class Controller:
    def __init__(self, application, choose_capture, choose_request, report):
        self.application = application
        self.choose_capture = choose_capture
        self.choose_request = choose_request
        self.report = report
        self.session = None
        self.identity = None

    def _active(self):
        document = self.application.activeDocument()
        if document is None:
            raise ValueError("Select an open Krita document")
        return document

    def _key(self, document):
        return str(document.rootNode().uniqueId())

    def _captured(self):
        document = self._active()
        if self.session is None:
            raise ValueError("Capture this document before importing or comparing")
        if self.identity != self._key(document) or not (document == self.session.document):
            raise ValueError("The active document differs from the captured session; capture it as a new session")
        return self.session

    def capture(self):
        folder = self.choose_capture()
        if not folder:
            return None
        document = self._active()
        fresh = Session(document)
        snapshot = fresh.capture(Path(folder))
        self.session, self.identity = fresh, self._key(document)
        self.report("Capture complete", "Snapshot: " + str(Path(folder) / "snapshot.json") + "\nSource KRA: " + str(Path(folder) / "source.kra"))
        return snapshot

    def import_request(self):
        request = self.choose_request()
        if not request:
            return None
        request_path = Path(request)
        receipt = self._captured().import_request(request_path)
        native_path = Path(json.loads(request_path.read_text(encoding="utf-8"))["native_plan"]["path"]).resolve()
        self.report("Proposed layer imported", "Receipt: " + str(native_path.parent / "live-result.json") + "\nPackage: " + str(native_path.parent))
        return receipt

    def show_source(self):
        value = self._captured().show_source()
        self.report("Source shown", "The proposed layer is hidden. No document was saved or closed.")
        return value

    def show_result(self):
        value = self._captured().show_result()
        self.report("Result shown", "The proposed layer is visible. No document was saved or closed.")
        return value


def register():
    """Register an Extension only in Krita; do not inspect files or documents."""
    try:
        from krita import Extension, Krita
        from PyQt5.QtWidgets import QAction, QFileDialog, QMessageBox
    except ImportError:
        return None

    class StudioSessionExtension(Extension):
        def __init__(self, parent):
            super().__init__(parent)
            app = Krita.instance()
            def capture_path():
                return QFileDialog.getSaveFileName(None, "New Studio capture folder")[0]
            def request_path():
                return QFileDialog.getOpenFileName(None, "Import Studio request", "", "Studio request (*.json)")[0]
            self.controller = Controller(app, capture_path, request_path,
                                         lambda title, message: QMessageBox.information(None, title, message))

        def setup(self):
            return None

        def createActions(self, window):
            actions = (("studio_session_capture", "Capture document", self.controller.capture),
                       ("studio_session_import", "Import request", self.controller.import_request),
                       ("studio_session_source", "Show source", self.controller.show_source),
                       ("studio_session_result", "Show result", self.controller.show_result))
            for name, label, callback in actions:
                action = window.createAction(name, label, "tools/scripts")
                action.triggered.connect(lambda checked=False, run=callback: self._run(run))

        def _run(self, callback):
            try:
                callback()
            except (OSError, ValueError, KeyError, TypeError) as exc:
                QMessageBox.warning(None, "Studio document session", str(exc))

    application = Krita.instance()
    application.addExtension(StudioSessionExtension(application))
    return True
