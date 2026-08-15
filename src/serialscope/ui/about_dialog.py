"""Compact application information shared by the Help menu."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout, QWidget

from serialscope import __version__
from serialscope.updates.model import REPOSITORY_URL


APPLICATION_AUTHOR = "Roelof du Toit"
GITHUB_URL = REPOSITORY_URL


class AboutDialog(QDialog):
    """Show authoritative version, author, and repository information."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("aboutSerialScopeDialog")
        self.setWindowTitle("About SerialScope")
        self.setMinimumWidth(360)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 16)
        layout.setSpacing(14)

        self.information_label = QLabel(
            "<h2>SerialScope</h2>"
            f"<p>Version {__version__}</p>"
            f"<p>Developed by:<br><b>{APPLICATION_AUTHOR}</b></p>"
            f'<p>GitHub:<br><a href="{GITHUB_URL}">{GITHUB_URL}</a></p>'
        )
        self.information_label.setObjectName("aboutInformationLabel")
        self.information_label.setTextFormat(Qt.TextFormat.RichText)
        self.information_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction
        )
        self.information_label.setOpenExternalLinks(True)
        layout.addWidget(self.information_label)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
