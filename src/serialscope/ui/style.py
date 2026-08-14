"""Small application stylesheet for the initial desktop shell."""


SHARED_TYPOGRAPHY = """
QWidget {
    font-family: "Sans Serif";
    font-size: 10.5pt;
}
"""


DARK_STYLE = SHARED_TYPOGRAPHY + """
QWidget {
    color: #d9e2ec;
    background-color: #111820;
}
QMainWindow, QSplitter {
    background-color: #0c1219;
}
QWidget#menuApplicationInformation,
QLabel#menuAuthorLabel,
QLabel#menuVersionLabel {
    background-color: transparent;
    color: #8fa3b8;
}
QToolButton#githubUpdatesButton {
    color: #9fc9dd;
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 3px;
    padding: 3px 6px;
}
QToolButton#githubUpdatesButton:hover {
    color: #d9edf7;
    background-color: #1b2a36;
    border-color: #36566a;
}
QTabWidget#workspaceTabs::pane {
    background-color: #151e28;
    border: 1px solid #263442;
    border-radius: 0 5px 5px 5px;
}
QTabBar::tab {
    color: #8fa3b8;
    background-color: #111923;
    border: 1px solid #263442;
    border-bottom: 0;
    padding: 9px 18px;
    margin-right: 2px;
}
QTabBar::tab:selected {
    color: #d9e2ec;
    background-color: #151e28;
    border-top-color: #2f9bd1;
}
QTabBar::tab:hover:!selected {
    color: #bac8d5;
    background-color: #18232e;
}
QMenu {
    color: #d9e2ec;
    background-color: #151e28;
    border: 1px solid #314354;
}
QMenu::item:selected:enabled {
    color: #eef7fc;
    background-color: #28465a;
}
QMenu::item:disabled {
    color: #647585;
    background-color: transparent;
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
QLabel#profileStatusLabel { color: #718399; font-size: 9pt; }
QToolButton#deviceProfileMenuButton {
    color: #bac8d5; background-color: #18232e; border: 1px solid #314354;
    border-radius: 4px; padding: 4px 7px;
}
QToolButton#deviceProfileMenuButton:hover { background-color: #223341; border-color: #477088; }
QToolButton#deviceProfileMenuButton:disabled { color: #647585; background-color: #141d25; }
QLabel#replayModeBanner {
    color: #bfe7fa;
    background-color: #132a38;
    border: 1px solid #28566d;
    border-radius: 4px;
    padding: 7px 10px;
    font-weight: 600;
}
QLabel#graphCursorReadout, QLabel#graphStatisticsLabel {
    color: #aebdca;
    background-color: #182630;
    border: 1px solid #293f4d;
    border-radius: 4px;
    padding: 6px 9px;
}
QScrollArea#channelSelector {
    color: #c6d2dc;
    background-color: #0e151d;
    border: 1px solid #293846;
    border-radius: 4px;
    padding: 4px;
}
QWidget#channelSelectorContent { background-color: transparent; }
QFrame#channelToggle {
    border: 1px solid transparent;
    border-radius: 4px;
    background-color: transparent;
}
QFrame#channelToggle:hover {
    background-color: #182630;
    border-color: #314c5d;
}
QFrame#channelToggle[checked="true"] {
    background-color: #162630;
    border-color: #35657b;
}
QFrame#channelToggle[checked="true"]:hover {
    background-color: #1a2d3a;
    border-color: #477b94;
}
QFrame#channelToggle:focus { border-color: #5689a1; }
QLabel#channelToggleLabel {
    color: #aebdca;
    background-color: transparent;
    border: none;
    font-weight: 400;
}
QFrame#channelToggle[checked="true"] QLabel#channelToggleLabel { color: #d5e2eb; }
QFrame#channelToggle:disabled QLabel#channelToggleLabel { color: #647585; }
QFrame#channelToggle:disabled {
    background-color: #121b23;
    border-color: transparent;
}
QCheckBox#channelToggleIndicator { spacing: 0; padding: 0; }
QCheckBox#channelToggleIndicator::indicator {
    width: 14px;
    height: 14px;
    border: 1px solid #60788b;
    border-radius: 7px;
    background-color: #0e151d;
}
QCheckBox#channelToggleIndicator::indicator:hover { border-color: #8ab7cc; }
QCheckBox#channelToggleIndicator::indicator:checked {
    background-color: #2f9bd1;
    border: 1px solid #78bad7;
}
QCheckBox#channelToggleIndicator::indicator:disabled {
    background-color: #1a242d;
    border-color: #40505d;
}
QFrame#dashboardChannelTile {
    background-color: #151e28;
    border: 1px solid #314657;
    border-radius: 5px;
}
QFrame#dashboardChannelTile:hover {
    border-color: #477088;
    background-color: #18242f;
}
QFrame#dashboardChannelTile[dragState="active"] {
    border: 2px solid #6fa6c2;
}
QFrame#dashboardDropIndicator {
    background-color: #101d27;
    border: 2px dashed #6fa6c2;
    border-radius: 5px;
}
QLabel#dashboardTileName {
    color: #8fa3b8;
    font-size: 11pt;
    font-weight: 500;
}
QLabel#dashboardTileValue {
    color: #e2eef6;
    font-size: 24pt;
    font-weight: 600;
}
QLabel#dashboardTileUnit {
    color: #8fa3b8;
    font-size: 11pt;
}
QLabel#dashboardTileStatus {
    color: #8fa3b8;
    font-size: 9pt;
    font-weight: 600;
}
QLabel#dashboardTileSource { color: #718399; font-size: 8.5pt; }
QFrame#dashboardChannelTile[alarmState="warning"] {
    background-color: #302a19;
    border-color: #a88637;
}
QFrame#dashboardChannelTile[alarmState="alarm"] {
    background-color: #351f23;
    border-color: #bc5660;
}
QLabel#dashboardTileStatus[alarmState="warning"] { color: #e0b95c; }
QLabel#dashboardTileStatus[alarmState="alarm"] { color: #ef8991; }
QLabel#dashboardEmptyLabel {
    color: #718399;
    font-size: 12pt;
}
QFrame#connectionStatusIndicator {
    min-height: 32px;
    background-color: #211b20;
    border: 1px solid #594047;
    border-radius: 4px;
}
QFrame#connectionStatusIndicator[connectionState="connected"] {
    background-color: #16251e;
    border-color: #315f48;
}
QFrame#connectionStatusIndicator[connectionState="error"] {
    background-color: #2b1c20;
    border-color: #7a454d;
}
QLabel#connectionStatusDot {
    color: #bd6e76;
    background-color: transparent;
    font-size: 10pt;
}
QLabel#connectionStatusDot[connectionState="connected"] { color: #43b97b; }
QLabel#connectionStatusDot[connectionState="error"] { color: #dd6973; }
QLabel#connectionStatusLabel {
    color: #d3a1a6;
    background-color: transparent;
    font-size: 10.5pt;
    font-weight: 600;
    letter-spacing: 0.4px;
}
QLabel#connectionStatusLabel[connectionState="connected"] { color: #9bd9b8; }
QLabel#connectionStatusLabel[connectionState="error"] { color: #ee9aa1; }
QLabel#loggingStatusDot {
    color: #596775;
    font-size: 10pt;
}
QLabel#loggingStatusDot[recordingState="active"] {
    color: #ff3b4f;
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
QPushButton, QToolButton#engineeringUnitSelector {
    min-height: 32px;
    padding: 1px 14px;
    background-color: #223140;
    border: 1px solid #344a5e;
    border-radius: 4px;
    font-weight: 600;
}
QPushButton:hover, QToolButton#engineeringUnitSelector:hover {
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
QTableWidget#channelDataTable {
    color: #d9e2ec;
    background-color: #0e151d;
    alternate-background-color: #111b25;
    border: 1px solid #293846;
    gridline-color: #263442;
    selection-background-color: #255b72;
}
QTableWidget#channelDataTable QHeaderView::section {
    color: #aebdca;
    background-color: #18232e;
    border: 0;
    border-bottom: 1px solid #314354;
    padding: 8px;
    font-weight: 600;
}
QLabel#dataEmptyLabel, QLabel#graphsEmptyLabel {
    color: #94a7b9;
    font-size: 12pt;
}
QLabel#graphsEmptyDetail {
    color: #718399;
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


LIGHT_STYLE = SHARED_TYPOGRAPHY + """
QWidget {
    color: #263442;
    background-color: #eef2f5;
}
QMainWindow, QSplitter { background-color: #e7ecef; }
QWidget#menuApplicationInformation,
QLabel#menuAuthorLabel,
QLabel#menuVersionLabel {
    background-color: transparent;
    color: #607486;
}
QToolButton#githubUpdatesButton {
    color: #286985;
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 3px;
    padding: 3px 6px;
}
QToolButton#githubUpdatesButton:hover {
    color: #174b65;
    background-color: #dce9ef;
    border-color: #8eb0c0;
}
QTabWidget#workspaceTabs::pane {
    background-color: #f7f9fb;
    border: 1px solid #c5cfd8;
}
QTabBar::tab {
    color: #526474;
    background-color: #e5eaee;
    border: 1px solid #c5cfd8;
    border-bottom: 0;
    padding: 9px 18px;
    margin-right: 2px;
}
QTabBar::tab:selected {
    color: #182631;
    background-color: #f7f9fb;
    border-top-color: #1978a8;
}
QMenu {
    color: #263442;
    background-color: #f7f9fb;
    border: 1px solid #b8c5cf;
}
QMenu::item:selected:enabled {
    color: #172f3d;
    background-color: #c9dfe9;
}
QMenu::item:disabled {
    color: #929da6;
    background-color: transparent;
}
QFrame#connectionBar, QFrame#terminalPanel, QFrame#sidePanel {
    background-color: #f7f9fb;
    border: 1px solid #c5cfd8;
    border-radius: 6px;
}
QWidget#panelHeader, QWidget#commandArea { background-color: #f7f9fb; }
QWidget#panelHeader { border-bottom: 1px solid #d2dae1; }
QWidget#commandArea { border-top: 1px solid #d2dae1; }
QLabel#fieldLabel, QLabel#panelTitle {
    color: #607486;
    font-size: 9pt;
    font-weight: 600;
    letter-spacing: 1px;
}
QLabel#mutedLabel, QLabel#graphsEmptyDetail { color: #718399; }
QLabel#profileStatusLabel { color: #718399; font-size: 9pt; }
QToolButton#deviceProfileMenuButton {
    color: #455b6d; background-color: #edf1f4; border: 1px solid #bcc8d0;
    border-radius: 4px; padding: 4px 7px;
}
QToolButton#deviceProfileMenuButton:hover { background-color: #e2edf2; border-color: #7fa6b9; }
QToolButton#deviceProfileMenuButton:disabled { color: #93a1ac; background-color: #e5eaed; }
QLabel#replayModeBanner {
    color: #174b65;
    background-color: #dcecf3;
    border: 1px solid #9fc5d5;
    border-radius: 4px;
    padding: 7px 10px;
    font-weight: 600;
}
QLabel#graphCursorReadout, QLabel#graphStatisticsLabel {
    color: #374f5e;
    background-color: #e4edf2;
    border: 1px solid #c1d2da;
    border-radius: 4px;
    padding: 6px 9px;
}
QScrollArea#channelSelector {
    color: #374b5b;
    background-color: #ffffff;
    border: 1px solid #c5cfd8;
    border-radius: 4px;
    padding: 4px;
}
QWidget#channelSelectorContent { background-color: transparent; }
QFrame#channelToggle {
    border: 1px solid transparent;
    border-radius: 4px; background-color: transparent;
}
QFrame#channelToggle:hover {
    background-color: #e8eff3;
    border-color: #a4b9c4;
}
QFrame#channelToggle[checked="true"] {
    background-color: #e3edf2;
    border-color: #7b9faf;
}
QFrame#channelToggle[checked="true"]:hover {
    background-color: #dce9ef;
    border-color: #628ea2;
}
QFrame#channelToggle:focus { border-color: #4f839b; }
QLabel#channelToggleLabel {
    color: #526879;
    background-color: transparent;
    border: none;
    font-weight: 400;
}
QFrame#channelToggle[checked="true"] QLabel#channelToggleLabel { color: #263f4e; }
QFrame#channelToggle:disabled QLabel#channelToggleLabel { color: #93a1ac; }
QFrame#channelToggle:disabled {
    background-color: #edf1f4;
    border-color: transparent;
}
QCheckBox#channelToggleIndicator { spacing: 0; padding: 0; }
QCheckBox#channelToggleIndicator::indicator {
    width: 14px; height: 14px; border: 1px solid #718a9b;
    border-radius: 7px; background-color: #f7f9fb;
}
QCheckBox#channelToggleIndicator::indicator:hover { border-color: #376f8b; }
QCheckBox#channelToggleIndicator::indicator:checked {
    background-color: #287fa8; border: 1px solid #4f91ad;
}
QCheckBox#channelToggleIndicator::indicator:disabled {
    background-color: #e1e6e9; border-color: #b4c0c8;
}
QFrame#dashboardChannelTile {
    background-color: #f7f9fb;
    border: 1px solid #bccbd5;
    border-radius: 5px;
}
QFrame#dashboardChannelTile:hover {
    border-color: #7fa6b9;
    background-color: #f0f5f7;
}
QFrame#dashboardChannelTile[dragState="active"] { border: 2px solid #4f829b; }
QFrame#dashboardDropIndicator {
    background-color: #e8f1f5;
    border: 2px dashed #4f829b;
    border-radius: 5px;
}
QLabel#dashboardTileName {
    color: #607486;
    font-size: 11pt;
    font-weight: 500;
}
QLabel#dashboardTileValue {
    color: #1d3442;
    font-size: 24pt;
    font-weight: 600;
}
QLabel#dashboardTileUnit { color: #607486; font-size: 11pt; }
QLabel#dashboardTileStatus { color: #607486; font-size: 9pt; font-weight: 600; }
QLabel#dashboardTileSource { color: #718399; font-size: 8.5pt; }
QFrame#dashboardChannelTile[alarmState="warning"] {
    background-color: #fff7dd;
    border-color: #b18a2e;
}
QFrame#dashboardChannelTile[alarmState="alarm"] {
    background-color: #fae7e9;
    border-color: #b94b57;
}
QLabel#dashboardTileStatus[alarmState="warning"] { color: #765712; }
QLabel#dashboardTileStatus[alarmState="alarm"] { color: #9b2935; }
QLabel#dashboardEmptyLabel { color: #718399; font-size: 12pt; }
QFrame#connectionStatusIndicator {
    min-height: 32px;
    background-color: #f4e9ea;
    border: 1px solid #d5b8bc;
    border-radius: 4px;
}
QFrame#connectionStatusIndicator[connectionState="connected"] {
    background-color: #e8f3ed;
    border-color: #a5c9b4;
}
QFrame#connectionStatusIndicator[connectionState="error"] {
    background-color: #f7e6e8;
    border-color: #d7a3a9;
}
QLabel#connectionStatusDot {
    color: #aa5962;
    background-color: transparent;
    font-size: 10pt;
}
QLabel#connectionStatusDot[connectionState="connected"] { color: #258658; }
QLabel#connectionStatusDot[connectionState="error"] { color: #bd404c; }
QLabel#connectionStatusLabel {
    color: #874b52;
    background-color: transparent;
    font-size: 10.5pt;
    font-weight: 600;
    letter-spacing: 0.4px;
}
QLabel#connectionStatusLabel[connectionState="connected"] { color: #256e4d; }
QLabel#connectionStatusLabel[connectionState="error"] { color: #9f3540; }
QLabel#loggingStatusDot { color: #8b98a3; font-size: 10pt; }
QLabel#loggingStatusDot[recordingState="active"] { color: #df2338; }
QComboBox, QLineEdit {
    min-height: 32px;
    padding: 1px 9px;
    background-color: #ffffff;
    border: 1px solid #b8c5cf;
    border-radius: 4px;
    selection-background-color: #79b8d8;
}
QComboBox:focus, QLineEdit:focus { border-color: #1978a8; }
QComboBox QAbstractItemView {
    background-color: #ffffff;
    border: 1px solid #b8c5cf;
    selection-background-color: #79b8d8;
}
QPushButton, QToolButton#engineeringUnitSelector {
    min-height: 32px;
    padding: 1px 14px;
    background-color: #e1e7eb;
    border: 1px solid #b8c5cf;
    border-radius: 4px;
    font-weight: 600;
}
QPushButton:hover, QToolButton#engineeringUnitSelector:hover { background-color: #d5dde3; }
QPushButton#connectButton, QPushButton#sendButton {
    color: #ffffff;
    background-color: #1978a8;
    border-color: #166b96;
}
QPlainTextEdit#terminalOutput {
    color: #173d2c;
    background-color: #f8fafb;
    border: 0;
    padding: 14px;
    selection-background-color: #9bc9dd;
}
QTableWidget#channelDataTable {
    color: #263442;
    background-color: #ffffff;
    alternate-background-color: #f1f4f6;
    border: 1px solid #c5cfd8;
    gridline-color: #d7dee4;
    selection-background-color: #9bc9dd;
}
QTableWidget#channelDataTable QHeaderView::section {
    color: #374b5b;
    background-color: #e4e9ed;
    border: 0;
    border-bottom: 1px solid #c5cfd8;
    padding: 8px;
    font-weight: 600;
}
QGroupBox {
    color: #455b6d;
    background-color: #f2f5f7;
    border: 1px solid #c9d2d9;
    border-radius: 5px;
    margin-top: 9px;
    padding-top: 6px;
    font-weight: 600;
}
QGroupBox::title { subcontrol-origin: margin; left: 9px; padding: 0 5px; }
QGroupBox QLabel, QGroupBox QCheckBox {
    color: #526879; background: transparent; font-weight: 400;
}
QStatusBar {
    color: #607486;
    background-color: #e7ecef;
    border-top: 1px solid #cbd4db;
}
QStatusBar::item { border: 0; }
QSplitter::handle { background-color: transparent; width: 8px; }
QScrollBar:vertical { width: 10px; background: #edf1f4; }
QScrollBar::handle:vertical {
    min-height: 24px; background: #aebbc5; border-radius: 4px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""

# Backward-compatible name for callers that explicitly request the dark style.
APPLICATION_STYLE = DARK_STYLE
