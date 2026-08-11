"""Small application stylesheet for the initial desktop shell."""


APPLICATION_STYLE = """
QWidget {
    color: #d9e2ec;
    background-color: #111820;
    font-size: 10.5pt;
}
QMainWindow, QSplitter {
    background-color: #0c1219;
}
QFrame#connectionBar, QFrame#terminalPanel, QFrame#sidePanel {
    background-color: #151e28;
    border: 1px solid #263442;
    border-radius: 6px;
}
QWidget#panelHeader, QWidget#commandArea {
    background-color: #151e28;
}
QWidget#panelHeader {
    border-bottom: 1px solid #263442;
}
QWidget#commandArea {
    border-top: 1px solid #263442;
}
QLabel#fieldLabel, QLabel#panelTitle {
    color: #8fa3b8;
    font-size: 9pt;
    font-weight: 600;
    letter-spacing: 1px;
}
QLabel#mutedLabel {
    color: #718399;
}
QLabel#connectionStatusDot {
    color: #7f8c99;
    font-size: 11pt;
}
QLabel#connectionStatusLabel {
    color: #aebdca;
    font-weight: 600;
}
QComboBox, QLineEdit {
    min-height: 32px;
    padding: 1px 9px;
    background-color: #0e151d;
    border: 1px solid #314354;
    border-radius: 4px;
    selection-background-color: #2479a9;
}
QComboBox:hover, QLineEdit:hover {
    border-color: #476176;
}
QComboBox:focus, QLineEdit:focus {
    border-color: #2f9bd1;
}
QComboBox QAbstractItemView {
    background-color: #18232e;
    border: 1px solid #314354;
    selection-background-color: #2479a9;
}
QPushButton {
    min-height: 32px;
    padding: 1px 14px;
    background-color: #223140;
    border: 1px solid #344a5e;
    border-radius: 4px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #2a3d4f;
    border-color: #49677f;
}
QPushButton:pressed {
    background-color: #1a2733;
}
QPushButton#connectButton, QPushButton#sendButton {
    color: #ffffff;
    background-color: #1978a8;
    border-color: #238dbf;
}
QPushButton#connectButton:hover, QPushButton#sendButton:hover {
    background-color: #2189bb;
}
QPlainTextEdit#terminalOutput {
    color: #c9f0dc;
    background-color: #0a1016;
    border: 0;
    padding: 14px;
    selection-background-color: #255b72;
}
QGroupBox {
    color: #bac8d5;
    background-color: #111923;
    border: 1px solid #293846;
    border-radius: 5px;
    margin-top: 9px;
    padding-top: 6px;
    font-weight: 600;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 9px;
    padding: 0 5px;
}
QGroupBox QLabel, QGroupBox QCheckBox {
    color: #94a7b9;
    background: transparent;
    font-weight: 400;
}
QStatusBar {
    color: #8fa3b8;
    background-color: #0c1219;
    border-top: 1px solid #1d2a35;
}
QStatusBar::item {
    border: 0;
}
QSplitter::handle {
    background-color: transparent;
    width: 8px;
}
QScrollBar:vertical {
    width: 10px;
    background: #0a1016;
}
QScrollBar::handle:vertical {
    min-height: 24px;
    background: #334655;
    border-radius: 4px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
"""
