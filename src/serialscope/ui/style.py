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
QLabel#diagnosticsValue {
    color: #d9e2ec;
    font-weight: 500;
    background: transparent;
}
QLabel#profileStatusLabel { color: #718399; font-size: 9pt; }
QToolButton#deviceProfileMenuButton {
    color: #bac8d5; background-color: #18232e; border: 1px solid #314354;
    border-radius: 4px; padding: 4px 7px;
}
QToolButton#deviceProfileMenuButton::menu-indicator { image: none; width: 0; }
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
QLabel#graphCursorHeading, QLabel#graphStatisticsHeading {
    color: #c5d3de;
    font-weight: 600;
    letter-spacing: 0.4px;
}
QLabel#graphCursorTimeLabel { color: #8fa3b8; }
QLabel#graphCursorEmptyLabel, QLabel#graphStatisticsEmptyLabel {
    color: #718399;
    padding: 2px 6px;
}
QFrame#graphCursorPanel, QFrame#graphStatisticsPanel {
    background-color: #151e28;
    border: 1px solid #2a3b4c;
    border-radius: 6px;
}
QLabel#channelDataStatusBadge, QLabel#graphCursorStatus {
    padding: 5px 12px;
    border-radius: 10px;
    font-size: 10.5pt;
    font-weight: 600;
    letter-spacing: 0.3px;
    min-height: 22px;
    color: #8fa3b8;
    background-color: #18232e;
    border: 1px solid #314354;
}
QLabel#channelDataStatusBadge[alarmState="normal"],
QLabel#channelDataStatusBadge[alarmKind="NORMAL"],
QLabel#graphCursorStatus[alarmState="normal"],
QLabel#graphCursorStatus[alarmKind="NORMAL"] {
    color: #6bb88a;
    background-color: #16251e;
    border: 1px solid #315f48;
}
QLabel#channelDataStatusBadge[alarmState="warning"],
QLabel#graphCursorStatus[alarmState="warning"] {
    color: #c9a24a;
    background-color: #2a2518;
    border: 1px solid #8a7030;
}
QLabel#channelDataStatusBadge[alarmKind="LOW"],
QLabel#graphCursorStatus[alarmKind="LOW"] {
    color: #c4b06a;
    background-color: #282617;
    border: 1px solid #7a7038;
}
QLabel#channelDataStatusBadge[alarmKind="HIGH"],
QLabel#graphCursorStatus[alarmKind="HIGH"] {
    color: #c9a24a;
    background-color: #2a2518;
    border: 1px solid #8a7030;
}
QLabel#channelDataStatusBadge[alarmState="alarm"],
QLabel#graphCursorStatus[alarmState="alarm"] {
    color: #d07a82;
    background-color: #2c1c20;
    border: 1px solid #8a4a52;
}
QLabel#channelDataStatusBadge[alarmKind="LOW-LOW"],
QLabel#graphCursorStatus[alarmKind="LOW-LOW"] {
    color: #c07080;
    background-color: #28181c;
    border: 1px solid #7a4048;
}
QLabel#channelDataStatusBadge[alarmKind="HIGH-HIGH"],
QLabel#channelDataStatusBadge[alarmKind="ERROR"],
QLabel#graphCursorStatus[alarmKind="HIGH-HIGH"],
QLabel#graphCursorStatus[alarmKind="ERROR"] {
    color: #d07a82;
    background-color: #2c1c20;
    border: 1px solid #8a4a52;
}
QLabel#channelDataStatusBadge[alarmState="unknown"],
QLabel#channelDataStatusBadge[alarmKind="UNKNOWN"],
QLabel#graphCursorStatus[alarmState="unknown"] {
    color: #8fa3b8;
    background-color: #18232e;
    border: 1px solid #314354;
}
QScrollArea#channelSelector {
    color: #c6d2dc;
    background-color: #0e151d;
    border: 1px solid #293846;
    border-radius: 4px;
    padding: 6px;
}
QWidget#channelSelectorContent { background-color: transparent; }
QFrame#channelToggle {
    border: 1px solid #3a5163;
    border-radius: 6px;
    background-color: #16202a;
}
QFrame#channelToggle:hover {
    background-color: #223848;
    border-color: #5d90aa;
}
QFrame#channelToggle[checked="true"] {
    background-color: #1a5270;
    border-color: #4db3d9;
}
QFrame#channelToggle[checked="true"]:hover {
    background-color: #216388;
    border-color: #78c8e4;
}
QFrame#channelToggle:focus { border-color: #6ec4e6; }
QLabel#channelToggleLabel {
    color: #c5d3de;
    background-color: transparent;
    border: none;
    font-weight: 500;
}
QFrame#channelToggle:hover QLabel#channelToggleLabel { color: #e4eef4; }
QFrame#channelToggle[checked="true"] QLabel#channelToggleLabel {
    color: #f4fbff;
}
QFrame#channelToggle[checked="true"]:hover QLabel#channelToggleLabel {
    color: #ffffff;
}
QFrame#channelToggle:disabled QLabel#channelToggleLabel { color: #647585; }
QFrame#channelToggle:disabled {
    background-color: #121b23;
    border-color: #2a3844;
}
QCheckBox#channelToggleIndicator { spacing: 0; padding: 0; }
QCheckBox#channelToggleIndicator::indicator {
    width: 14px;
    height: 14px;
    border: 1px solid #7a93a6;
    border-radius: 7px;
    background-color: #0e151d;
}
QCheckBox#channelToggleIndicator::indicator:hover { border-color: #9fd0e6; }
QCheckBox#channelToggleIndicator::indicator:checked {
    background-color: #4db3d9;
    border: 1px solid #9fdff3;
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
QWidget#dashboardTileSparkline {
    background-color: transparent;
    min-height: 26px;
    max-height: 28px;
}
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
QFrame#connectionStatusIndicator[connectionState="error"],
QFrame#connectionStatusIndicator[connectionState="lost"],
QFrame#connectionStatusIndicator[connectionState="reconnecting"] {
    background-color: #2b1c20;
    border-color: #7a454d;
}
QFrame#connectionStatusIndicator[connectionState="connecting"] {
    background-color: #241f18;
    border-color: #7a6a3a;
}
QLabel#connectionStatusDot {
    color: #bd6e76;
    background-color: transparent;
    font-size: 10pt;
}
QLabel#connectionStatusDot[connectionState="connected"] { color: #43b97b; }
QLabel#connectionStatusDot[connectionState="error"],
QLabel#connectionStatusDot[connectionState="lost"],
QLabel#connectionStatusDot[connectionState="reconnecting"] { color: #dd6973; }
QLabel#connectionStatusDot[connectionState="connecting"] { color: #d4c07a; }
QLabel#connectionStatusLabel {
    color: #d3a1a6;
    background-color: transparent;
    font-size: 10.5pt;
    font-weight: 600;
    letter-spacing: 0.4px;
}
QLabel#connectionStatusLabel[connectionState="connected"] { color: #9bd9b8; }
QLabel#connectionStatusLabel[connectionState="error"],
QLabel#connectionStatusLabel[connectionState="lost"],
QLabel#connectionStatusLabel[connectionState="reconnecting"] { color: #ee9aa1; }
QLabel#connectionStatusLabel[connectionState="connecting"] { color: #e0d3a0; }
QFrame#loggingStatusIndicator {
    min-height: 34px;
    background-color: #18232e;
    border: 1px solid #314354;
    border-radius: 4px;
}
QFrame#loggingStatusIndicator[recordingState="active"] {
    background-color: #3a1c22;
    border: 1px solid #c44552;
}
QLabel#loggingStatusDot {
    color: #6b7785;
    background-color: transparent;
    font-size: 14pt;
    min-width: 16px;
}
QLabel#loggingStatusDot[recordingState="active"] {
    color: #ef4454;
}
QLabel#loggingStatusLabel {
    color: #8fa3b8;
    background-color: transparent;
    font-weight: 500;
}
QLabel#loggingStatusLabel[recordingState="active"] {
    color: #f3cdd1;
    font-weight: 700;
    letter-spacing: 0.8px;
}
QComboBox, QLineEdit, QAbstractSpinBox {
    min-height: 32px;
    padding: 1px 9px;
    color: #d9e2ec;
    background-color: #0e151d;
    border: 1px solid #314354;
    border-radius: 4px;
    selection-background-color: #2479a9;
}
QComboBox:hover, QLineEdit:hover, QAbstractSpinBox:hover {
    border-color: #476176;
}
QComboBox:focus, QLineEdit:focus, QAbstractSpinBox:focus {
    border-color: #2f9bd1;
}
QComboBox:disabled, QLineEdit:disabled, QAbstractSpinBox:disabled {
    color: #647585;
    background-color: #121b23;
    border-color: #2a3844;
}
QComboBox {
    padding-right: 28px;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 24px;
    border: none;
    background: transparent;
}
QComboBox::down-arrow {
    image: url(__COMBO_CHEVRON__);
    width: 10px;
    height: 6px;
}
QComboBox QAbstractItemView {
    color: #d9e2ec;
    background-color: #18232e;
    border: 1px solid #314354;
    selection-background-color: #2479a9;
    outline: none;
}
QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {
    width: 16px;
    background: transparent;
    border: none;
}
QCheckBox {
    color: #bac8d5;
    background: transparent;
    spacing: 6px;
}
QCheckBox::indicator {
    width: 14px;
    height: 14px;
    border: 1px solid #60788b;
    border-radius: 3px;
    background-color: #0e151d;
}
QCheckBox::indicator:hover { border-color: #8ab7cc; }
QCheckBox::indicator:checked {
    background-color: #2f9bd1;
    border: 1px solid #78bad7;
}
QCheckBox::indicator:disabled {
    background-color: #1a242d;
    border-color: #40505d;
}
QPushButton, QToolButton#engineeringUnitSelector {
    min-height: 32px;
    padding: 1px 14px;
    color: #d9e2ec;
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
QPushButton:disabled, QToolButton#engineeringUnitSelector:disabled {
    color: #647585;
    background-color: #18232e;
    border-color: #2a3844;
}
QPushButton#connectButton, QPushButton#sendButton,
QPushButton#loggingButton, QPushButton#dialogPrimaryButton {
    color: #ffffff;
    background-color: #1978a8;
    border-color: #238dbf;
}
QPushButton#connectButton:hover, QPushButton#sendButton:hover,
QPushButton#loggingButton:hover, QPushButton#dialogPrimaryButton:hover {
    background-color: #2189bb;
}
QPushButton#connectButton:disabled, QPushButton#sendButton:disabled,
QPushButton#loggingButton:disabled, QPushButton#dialogPrimaryButton:disabled {
    color: #8aa4b3;
    background-color: #1a3240;
    border-color: #2a4556;
}
QPushButton#addCalculatedButton, QPushButton#addEventButton,
QPushButton#addSerialSourceButton {
    color: #e8f4fa;
    background-color: #1a4a62;
    border-color: #3d7f9c;
}
QPushButton#addCalculatedButton:hover, QPushButton#addEventButton:hover,
QPushButton#addSerialSourceButton:hover {
    background-color: #21607f;
}
QPushButton#deleteCalculatedButton, QPushButton#removeSerialSourceButton {
    color: #f0cfd2;
    background-color: #3a2428;
    border-color: #7a454d;
}
QPushButton#deleteCalculatedButton:hover, QPushButton#removeSerialSourceButton:hover {
    background-color: #4a2c31;
}
QPlainTextEdit#terminalOutput {
    color: #c9f0dc;
    background-color: #0a1016;
    border: 0;
    padding: 14px;
    selection-background-color: #255b72;
}
QLabel#graphChannelsLabel, QLabel#dashboardSelectorLabel,
QLabel#dashboardTileSizeLabel,
QLabel#graphTimeWindowLabel, QLabel#graphSettingsHeading {
    color: #8fa3b8;
    font-weight: 600;
}
QLabel#graphSettingsHeading {
    font-size: 9pt;
    letter-spacing: 0.6px;
}
QLabel#graphDensityLabel, QLabel#graphMaxGapLabel,
QLabel#graphMovingAverageLabel, QLabel#graphEmaAlphaLabel {
    color: #94a7b9;
    background: transparent;
}
QLabel#graphDensityLabel:disabled, QLabel#graphMaxGapLabel:disabled {
    color: #4e5f6d;
}
QFrame#graphSettingsPanel { background: transparent; }
QFrame#graphControls, QFrame#graphProcessingControls, QFrame#graphSmoothingControls {
    background-color: #151e28;
    border: 1px solid #2a3b4c;
    border-radius: 6px;
}
QTableWidget#channelDataTable,
QTableWidget#graphCursorTable,
QTableWidget#graphStatisticsTable,
QTableWidget#eventListTable {
    color: #d9e2ec;
    background-color: #0e151d;
    alternate-background-color: #111b25;
    border: 1px solid #293846;
    gridline-color: #263442;
    selection-background-color: #255b72;
}
QTableWidget#channelDataTable,
QTableWidget#graphCursorTable,
QTableWidget#graphStatisticsTable {
    gridline-color: transparent;
    outline: none;
    alternate-background-color: #121b24;
}
QTableWidget#channelDataTable::item,
QTableWidget#graphCursorTable::item,
QTableWidget#graphStatisticsTable::item {
    padding: 6px 12px;
    border: none;
    border-bottom: 1px solid #1c2833;
}
QTableWidget#channelDataTable::item:hover,
QTableWidget#graphCursorTable::item:hover,
QTableWidget#graphStatisticsTable::item:hover {
    background-color: #18242f;
}
QTableWidget#channelDataTable::item:selected {
    color: #e8f4fa;
    background-color: #1f3a4c;
}
QWidget#channelDataStatusCell { background: transparent; }
QWidget#graphCursorChannel,
QWidget#graphStatisticsChannel,
QWidget#graphCursorStatusCell,
QLabel#graphCursorChannelLabel,
QLabel#graphStatisticsChannelLabel { background-color: transparent; }
QLabel#graphCursorChannelLabel, QLabel#graphStatisticsChannelLabel {
    color: #d9e2ec;
    font-weight: 500;
}
QLabel#graphCursorSwatch, QLabel#graphStatisticsSwatch {
    min-width: 8px;
    max-width: 8px;
    min-height: 8px;
    max-height: 8px;
    border-radius: 4px;
    border: none;
}
QTableWidget#channelDataTable QHeaderView::section,
QTableWidget#graphCursorTable QHeaderView::section,
QTableWidget#graphStatisticsTable QHeaderView::section,
QTableWidget#eventListTable QHeaderView::section {
    color: #aebdca;
    background-color: #18232e;
    border: 0;
    border-bottom: 1px solid #314354;
    padding: 8px;
    font-weight: 600;
}
QTableWidget#channelDataTable QHeaderView::section,
QTableWidget#graphCursorTable QHeaderView::section,
QTableWidget#graphStatisticsTable QHeaderView::section {
    color: #c5d3de;
    background-color: #1a2530;
    padding: 9px 12px;
    border-bottom: 1px solid #3a5163;
    font-size: 9pt;
    letter-spacing: 0.5px;
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
    width: 11px;
    background: #111820;
    margin: 0;
    border: none;
}
QScrollBar::handle:vertical {
    min-height: 28px;
    background: #3d5466;
    border-radius: 5px;
    margin: 2px;
}
QScrollBar::handle:vertical:hover { background: #5a7a90; }
QScrollBar::handle:vertical:pressed { background: #6fa6c2; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
    width: 0;
    background: none;
    border: none;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
}
QScrollBar:horizontal {
    height: 11px;
    background: #111820;
    margin: 0;
    border: none;
}
QScrollBar::handle:horizontal {
    min-width: 28px;
    background: #3d5466;
    border-radius: 5px;
    margin: 2px;
}
QScrollBar::handle:horizontal:hover { background: #5a7a90; }
QScrollBar::handle:horizontal:pressed { background: #6fa6c2; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    height: 0;
    width: 0;
    background: none;
    border: none;
}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: transparent;
}
QLabel#channelToggleBadge {
    color: #9fd0e6;
    background-color: #1a3a4c;
    border-radius: 3px;
    padding: 0 4px;
    font-size: 8pt;
    font-weight: 600;
}
QLabel#calculatedChannelsHeading {
    color: #aebdca;
    font-weight: 600;
}
QLabel#calculatedChannelStatus { color: #8fa3b8; }
QLabel#calculatedChannelPreview { color: #d9e2ec; font-weight: 600; }
QDialog {
    color: #d9e2ec;
    background-color: #111820;
}
QGroupBox#channelSettingsSection {
    color: #d9e2ec;
    background-color: #151e28;
    border: 1px solid #2a3b4c;
    border-radius: 6px;
    margin-top: 12px;
    padding: 10px 10px 8px 10px;
    font-weight: 600;
}
QGroupBox#channelSettingsSection::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #c5d3de;
}
QTableWidget#channelSettingsTable,
QTableWidget#calculatedChannelsTable,
QTableWidget#parserPreviewTable,
QTableWidget#parserMappingTable,
QTableWidget#diagnosticsChannelTable,
QTableWidget#diagnosticsGapTable,
QTableWidget#modbusRegisterTable {
    color: #d9e2ec;
    background-color: #121a23;
    alternate-background-color: #16202a;
    border: 1px solid #2a3b4c;
    gridline-color: #243342;
    selection-background-color: #1f3a4c;
}
QTableWidget#channelSettingsTable QHeaderView::section,
QTableWidget#calculatedChannelsTable QHeaderView::section,
QTableWidget#parserPreviewTable QHeaderView::section,
QTableWidget#parserMappingTable QHeaderView::section,
QTableWidget#diagnosticsChannelTable QHeaderView::section,
QTableWidget#diagnosticsGapTable QHeaderView::section,
QTableWidget#modbusRegisterTable QHeaderView::section {
    color: #c5d3de;
    background-color: #1a2530;
    border: 0;
    border-bottom: 1px solid #314354;
    padding: 8px 10px;
    font-weight: 600;
}
QLabel#channelSettingsReadOnly {
    color: #8fa3b8;
    background-color: transparent;
    padding: 0 6px;
}
QLineEdit#channelSettingsAlias,
QLineEdit#channelSettingsAlarm {
    min-height: 28px;
    padding: 2px 8px;
    background-color: #0e151d;
    border: 1px solid #3a5163;
    border-radius: 4px;
}
QLineEdit#channelSettingsAlias:hover,
QLineEdit#channelSettingsAlarm:hover { border-color: #5a7a90; }
QLineEdit#channelSettingsAlias:focus,
QLineEdit#channelSettingsAlarm:focus { border-color: #4db3d9; }
QLineEdit#channelSettingsAlarm[validationState="error"] {
    border-color: #c45b66;
    background-color: #2b1c20;
}
QLabel#calculatedChannelsEmpty {
    color: #718399;
    padding: 18px 8px;
}
QPushButton#addCalculatedButton {
    color: #e8f4fa;
    background-color: #1a4a62;
    border-color: #3d7f9c;
}
QPushButton#addCalculatedButton:hover { background-color: #21607f; }
QPushButton#deleteCalculatedButton {
    color: #f0cfd2;
    background-color: #3a2428;
    border-color: #7a454d;
}
QPushButton#deleteCalculatedButton:hover { background-color: #4a2c31; }
QPushButton#dialogPrimaryButton {
    color: #ffffff;
    background-color: #1978a8;
    border-color: #238dbf;
}
QPushButton#dialogPrimaryButton:hover { background-color: #2189bb; }
QPushButton#dialogSecondaryButton {
    color: #d9e2ec;
    background-color: #223140;
    border-color: #344a5e;
}
"""


LIGHT_STYLE = SHARED_TYPOGRAPHY + """
QWidget {
    color: #202833;
    background-color: #E8EDF2;
}
QMainWindow, QSplitter { background-color: #DDE3EA; }
QDialog, QMessageBox {
    color: #202833;
    background-color: #E8EDF2;
}
QToolTip {
    color: #202833;
    background-color: #F3F6F8;
    border: 1px solid #C5CED8;
}
QWidget#menuApplicationInformation,
QLabel#menuAuthorLabel,
QLabel#menuVersionLabel {
    background-color: transparent;
    color: #586574;
}
QToolButton#githubUpdatesButton {
    color: #2A6480;
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 3px;
    padding: 3px 6px;
}
QToolButton#githubUpdatesButton:hover {
    color: #163F54;
    background-color: #D7E3EA;
    border-color: #A7B8C4;
}
QTabWidget#workspaceTabs::pane {
    background-color: #F3F6F8;
    border: 1px solid #C5CED8;
}
QTabBar::tab {
    color: #586574;
    background-color: #EDF1F5;
    border: 1px solid #C5CED8;
    border-bottom: 0;
    padding: 9px 18px;
    margin-right: 2px;
}
QTabBar::tab:selected {
    color: #202833;
    background-color: #F3F6F8;
    border-top-color: #2A7AA8;
}
QTabBar::tab:hover:!selected {
    color: #2A3340;
    background-color: #E4EAF0;
}
QMenu {
    color: #202833;
    background-color: #F3F6F8;
    border: 1px solid #C5CED8;
}
QMenu::item:selected:enabled {
    color: #163040;
    background-color: #D2DFE8;
}
QMenu::item:disabled {
    color: #8A96A3;
    background-color: transparent;
}
QFrame#connectionBar, QFrame#terminalPanel, QFrame#sidePanel {
    background-color: #F3F6F8;
    border: 1px solid #C5CED8;
    border-radius: 6px;
}
QWidget#panelHeader, QWidget#commandArea { background-color: #F3F6F8; }
QWidget#panelHeader { border-bottom: 1px solid #C5CED8; }
QWidget#commandArea { border-top: 1px solid #C5CED8; }
QLabel#fieldLabel, QLabel#panelTitle {
    color: #586574;
    font-size: 9pt;
    font-weight: 600;
    letter-spacing: 1px;
}
QLabel#mutedLabel, QLabel#graphsEmptyDetail { color: #6B7785; }
QLabel#diagnosticsValue {
    color: #202833;
    font-weight: 500;
    background: transparent;
}
QLabel#profileStatusLabel { color: #6B7785; font-size: 9pt; }
QToolButton#deviceProfileMenuButton {
    color: #2A3340; background-color: #EDF1F5; border: 1px solid #C5CED8;
    border-radius: 4px; padding: 4px 7px;
}
QToolButton#deviceProfileMenuButton::menu-indicator { image: none; width: 0; }
QToolButton#deviceProfileMenuButton:hover { background-color: #DCE6ED; border-color: #8AA3B3; }
QToolButton#deviceProfileMenuButton:disabled { color: #8A96A3; background-color: #E4E9EE; }
QLabel#replayModeBanner {
    color: #163F54;
    background-color: #D5E3EB;
    border: 1px solid #A7C0CC;
    border-radius: 4px;
    padding: 7px 10px;
    font-weight: 600;
}
QLabel#graphCursorHeading, QLabel#graphStatisticsHeading {
    color: #2A3340;
    font-weight: 600;
    letter-spacing: 0.4px;
}
QLabel#graphCursorTimeLabel { color: #586574; }
QLabel#graphCursorEmptyLabel, QLabel#graphStatisticsEmptyLabel {
    color: #6B7785;
    padding: 2px 6px;
}
QFrame#graphCursorPanel, QFrame#graphStatisticsPanel {
    background-color: #F3F6F8;
    border: 1px solid #C5CED8;
    border-radius: 6px;
}
QLabel#channelDataStatusBadge, QLabel#graphCursorStatus {
    padding: 5px 12px;
    border-radius: 10px;
    font-size: 10.5pt;
    font-weight: 600;
    letter-spacing: 0.3px;
    min-height: 22px;
    color: #586574;
    background-color: #EDF1F5;
    border: 1px solid #C5CED8;
}
QLabel#channelDataStatusBadge[alarmState="normal"],
QLabel#channelDataStatusBadge[alarmKind="NORMAL"],
QLabel#graphCursorStatus[alarmState="normal"],
QLabel#graphCursorStatus[alarmKind="NORMAL"] {
    color: #215F43;
    background-color: #D9E8DF;
    border: 1px solid #8FB39C;
}
QLabel#channelDataStatusBadge[alarmState="warning"],
QLabel#graphCursorStatus[alarmState="warning"] {
    color: #6E5110;
    background-color: #EDE3C4;
    border: 1px solid #A37A28;
}
QLabel#channelDataStatusBadge[alarmKind="LOW"],
QLabel#graphCursorStatus[alarmKind="LOW"] {
    color: #5E5720;
    background-color: #E8E4C8;
    border: 1px solid #9A8F3A;
}
QLabel#channelDataStatusBadge[alarmKind="HIGH"],
QLabel#graphCursorStatus[alarmKind="HIGH"] {
    color: #6E5110;
    background-color: #EDE3C4;
    border: 1px solid #A37A28;
}
QLabel#channelDataStatusBadge[alarmState="alarm"],
QLabel#graphCursorStatus[alarmState="alarm"] {
    color: #8B2C36;
    background-color: #E8D4D7;
    border: 1px solid #A84A54;
}
QLabel#channelDataStatusBadge[alarmKind="LOW-LOW"],
QLabel#graphCursorStatus[alarmKind="LOW-LOW"] {
    color: #7A3040;
    background-color: #E5D0D4;
    border: 1px solid #9A5A64;
}
QLabel#channelDataStatusBadge[alarmKind="HIGH-HIGH"],
QLabel#channelDataStatusBadge[alarmKind="ERROR"],
QLabel#graphCursorStatus[alarmKind="HIGH-HIGH"],
QLabel#graphCursorStatus[alarmKind="ERROR"] {
    color: #8B2C36;
    background-color: #E8D4D7;
    border: 1px solid #A84A54;
}
QLabel#channelDataStatusBadge[alarmState="unknown"],
QLabel#channelDataStatusBadge[alarmKind="UNKNOWN"],
QLabel#graphCursorStatus[alarmState="unknown"] {
    color: #586574;
    background-color: #EDF1F5;
    border: 1px solid #C5CED8;
}
QScrollArea#channelSelector {
    color: #2A3340;
    background-color: #E4E9EE;
    border: 1px solid #C5CED8;
    border-radius: 4px;
    padding: 6px;
}
QWidget#channelSelectorContent { background-color: transparent; }
QFrame#channelToggle {
    border: 1px solid #B7C2CD;
    border-radius: 6px;
    background-color: #EDF1F5;
}
QFrame#channelToggle:hover {
    background-color: #D7E3EA;
    border-color: #6E92A6;
}
QFrame#channelToggle[checked="true"] {
    background-color: #C5D8E4;
    border-color: #2A7AA8;
}
QFrame#channelToggle[checked="true"]:hover {
    background-color: #B7CEDC;
    border-color: #21658C;
}
QFrame#channelToggle:focus { border-color: #2A7AA8; }
QLabel#channelToggleLabel {
    color: #2A3340;
    background-color: transparent;
    border: none;
    font-weight: 500;
}
QFrame#channelToggle:hover QLabel#channelToggleLabel { color: #163040; }
QFrame#channelToggle[checked="true"] QLabel#channelToggleLabel {
    color: #122838;
}
QFrame#channelToggle[checked="true"]:hover QLabel#channelToggleLabel {
    color: #0C1E2A;
}
QFrame#channelToggle:disabled QLabel#channelToggleLabel { color: #8A96A3; }
QFrame#channelToggle:disabled {
    background-color: #E4E9EE;
    border-color: #C5CED8;
}
QCheckBox#channelToggleIndicator { spacing: 0; padding: 0; }
QCheckBox#channelToggleIndicator::indicator {
    width: 14px; height: 14px; border: 1px solid #5E7384;
    border-radius: 7px; background-color: #F7F9FA;
}
QCheckBox#channelToggleIndicator::indicator:hover { border-color: #2A7AA8; }
QCheckBox#channelToggleIndicator::indicator:checked {
    background-color: #2A7AA8; border: 1px solid #1C5C80;
}
QCheckBox#channelToggleIndicator::indicator:disabled {
    background-color: #DDE3EA; border-color: #B7C2CD;
}
QFrame#dashboardChannelTile {
    background-color: #F3F6F8;
    border: 1px solid #C5CED8;
    border-radius: 5px;
}
QFrame#dashboardChannelTile:hover {
    border-color: #8AA3B3;
    background-color: #EDF1F5;
}
QFrame#dashboardChannelTile[dragState="active"] { border: 2px solid #4F829B; }
QFrame#dashboardDropIndicator {
    background-color: #DDE6EC;
    border: 2px dashed #4F829B;
    border-radius: 5px;
}
QLabel#dashboardTileName {
    color: #586574;
    font-size: 11pt;
    font-weight: 500;
}
QLabel#dashboardTileValue {
    color: #202833;
    font-size: 24pt;
    font-weight: 600;
}
QLabel#dashboardTileUnit { color: #586574; font-size: 11pt; }
QLabel#dashboardTileStatus { color: #586574; font-size: 9pt; font-weight: 600; }
QLabel#dashboardTileSource { color: #6B7785; font-size: 8.5pt; }
QWidget#dashboardTileSparkline {
    background-color: transparent;
    min-height: 26px;
    max-height: 28px;
}
QFrame#dashboardChannelTile[alarmState="warning"] {
    background-color: #F0E6C8;
    border-color: #A37A28;
}
QFrame#dashboardChannelTile[alarmState="alarm"] {
    background-color: #EDD8DB;
    border-color: #A84A54;
}
QLabel#dashboardTileStatus[alarmState="warning"] { color: #6E5110; }
QLabel#dashboardTileStatus[alarmState="alarm"] { color: #8B2C36; }
QLabel#dashboardEmptyLabel { color: #6B7785; font-size: 12pt; }
QFrame#connectionStatusIndicator {
    min-height: 32px;
    background-color: #EBDDE0;
    border: 1px solid #C9A8AD;
    border-radius: 4px;
}
QFrame#connectionStatusIndicator[connectionState="connected"] {
    background-color: #D9E8DF;
    border-color: #8FB39C;
}
QFrame#connectionStatusIndicator[connectionState="error"],
QFrame#connectionStatusIndicator[connectionState="lost"],
QFrame#connectionStatusIndicator[connectionState="reconnecting"] {
    background-color: #EBD5D8;
    border-color: #C79298;
}
QFrame#connectionStatusIndicator[connectionState="connecting"] {
    background-color: #EDE6D0;
    border-color: #C4B27A;
}
QLabel#connectionStatusDot {
    color: #9A4E57;
    background-color: transparent;
    font-size: 10pt;
}
QLabel#connectionStatusDot[connectionState="connected"] { color: #22724B; }
QLabel#connectionStatusDot[connectionState="error"],
QLabel#connectionStatusDot[connectionState="lost"],
QLabel#connectionStatusDot[connectionState="reconnecting"] { color: #B03A46; }
QLabel#connectionStatusDot[connectionState="connecting"] { color: #8A6E20; }
QLabel#connectionStatusLabel {
    color: #7A4249;
    background-color: transparent;
    font-size: 10.5pt;
    font-weight: 600;
    letter-spacing: 0.4px;
}
QLabel#connectionStatusLabel[connectionState="connected"] { color: #215F43; }
QLabel#connectionStatusLabel[connectionState="error"],
QLabel#connectionStatusLabel[connectionState="lost"],
QLabel#connectionStatusLabel[connectionState="reconnecting"] { color: #92323C; }
QLabel#connectionStatusLabel[connectionState="connecting"] { color: #6E5110; }
QFrame#loggingStatusIndicator {
    min-height: 34px;
    background-color: #E4E9EE;
    border: 1px solid #C5CED8;
    border-radius: 4px;
}
QFrame#loggingStatusIndicator[recordingState="active"] {
    background-color: #EDD4D7;
    border: 1px solid #B03A46;
}
QLabel#loggingStatusDot {
    color: #7A8692;
    background-color: transparent;
    font-size: 14pt;
    min-width: 16px;
}
QLabel#loggingStatusDot[recordingState="active"] {
    color: #C41E32;
}
QLabel#loggingStatusLabel {
    color: #586574;
    background-color: transparent;
    font-weight: 500;
}
QLabel#loggingStatusLabel[recordingState="active"] {
    color: #8B2C36;
    font-weight: 700;
    letter-spacing: 0.8px;
}
QComboBox, QLineEdit, QAbstractSpinBox {
    min-height: 32px;
    padding: 1px 9px;
    color: #202833;
    background-color: #F7F9FA;
    border: 1px solid #C5CED8;
    border-radius: 4px;
    selection-background-color: #B7D0DC;
}
QComboBox:hover, QLineEdit:hover, QAbstractSpinBox:hover {
    border-color: #8AA3B3;
}
QComboBox:focus, QLineEdit:focus, QAbstractSpinBox:focus { border-color: #2A7AA8; }
QComboBox:disabled, QLineEdit:disabled, QAbstractSpinBox:disabled {
    color: #8A96A3;
    background-color: #E4E9EE;
    border-color: #C5CED8;
}
QComboBox {
    padding-right: 28px;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 24px;
    border: none;
    background: transparent;
}
QComboBox::down-arrow {
    image: url(__COMBO_CHEVRON__);
    width: 10px;
    height: 6px;
}
QComboBox QAbstractItemView {
    color: #202833;
    background-color: #F3F6F8;
    border: 1px solid #C5CED8;
    selection-background-color: #D2DFE8;
    outline: none;
}
QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {
    width: 16px;
    background: transparent;
    border: none;
}
QCheckBox {
    color: #2A3340;
    background: transparent;
    spacing: 6px;
}
QCheckBox::indicator {
    width: 14px;
    height: 14px;
    border: 1px solid #5E7384;
    border-radius: 3px;
    background-color: #F7F9FA;
}
QCheckBox::indicator:hover { border-color: #2A7AA8; }
QCheckBox::indicator:checked {
    background-color: #2A7AA8;
    border: 1px solid #1C5C80;
}
QCheckBox::indicator:disabled {
    background-color: #DDE3EA;
    border-color: #B7C2CD;
}
QPushButton, QToolButton#engineeringUnitSelector {
    min-height: 32px;
    padding: 1px 14px;
    color: #202833;
    background-color: #DDE4EA;
    border: 1px solid #B7C2CD;
    border-radius: 4px;
    font-weight: 600;
}
QPushButton:hover, QToolButton#engineeringUnitSelector:hover {
    background-color: #D0D9E1;
    border-color: #8AA3B3;
}
QPushButton:pressed { background-color: #C4CED6; }
QPushButton:disabled, QToolButton#engineeringUnitSelector:disabled {
    color: #8A96A3;
    background-color: #E4E9EE;
    border-color: #C5CED8;
}
QPushButton#connectButton, QPushButton#sendButton,
QPushButton#loggingButton, QPushButton#dialogPrimaryButton {
    color: #F7F9FA;
    background-color: #2A7AA8;
    border-color: #21658C;
}
QPushButton#connectButton:hover, QPushButton#sendButton:hover,
QPushButton#loggingButton:hover, QPushButton#dialogPrimaryButton:hover {
    background-color: #3189BB;
}
QPushButton#connectButton:disabled, QPushButton#sendButton:disabled,
QPushButton#loggingButton:disabled, QPushButton#dialogPrimaryButton:disabled {
    color: #8A96A3;
    background-color: #C5D0D8;
    border-color: #B7C2CD;
}
QPushButton#addCalculatedButton, QPushButton#addEventButton,
QPushButton#addSerialSourceButton {
    color: #163F54;
    background-color: #D0DFE8;
    border-color: #8AA3B3;
}
QPushButton#addCalculatedButton:hover, QPushButton#addEventButton:hover,
QPushButton#addSerialSourceButton:hover {
    background-color: #C2D4DE;
}
QPushButton#deleteCalculatedButton, QPushButton#removeSerialSourceButton {
    color: #7A4249;
    background-color: #EBDDE0;
    border-color: #C9A8AD;
}
QPushButton#deleteCalculatedButton:hover, QPushButton#removeSerialSourceButton:hover {
    background-color: #E0CDD1;
}
QPlainTextEdit#terminalOutput {
    color: #1B3A2C;
    background-color: #E4EAEF;
    border: 0;
    padding: 14px;
    selection-background-color: #B7D0DC;
}
QLabel#graphChannelsLabel, QLabel#dashboardSelectorLabel,
QLabel#dashboardTileSizeLabel,
QLabel#graphTimeWindowLabel, QLabel#graphSettingsHeading {
    color: #586574;
    font-weight: 600;
}
QLabel#graphSettingsHeading {
    font-size: 9pt;
    letter-spacing: 0.6px;
}
QLabel#graphDensityLabel, QLabel#graphMaxGapLabel,
QLabel#graphMovingAverageLabel, QLabel#graphEmaAlphaLabel {
    color: #586574;
    background: transparent;
}
QLabel#graphDensityLabel:disabled, QLabel#graphMaxGapLabel:disabled {
    color: #8A96A3;
}
QFrame#graphSettingsPanel { background: transparent; }
QFrame#graphControls, QFrame#graphProcessingControls, QFrame#graphSmoothingControls {
    background-color: #F3F6F8;
    border: 1px solid #C5CED8;
    border-radius: 6px;
}
QTableWidget#channelDataTable,
QTableWidget#graphCursorTable,
QTableWidget#graphStatisticsTable,
QTableWidget#eventListTable {
    color: #202833;
    background-color: #EEF2F5;
    alternate-background-color: #E4E9EE;
    border: 1px solid #C5CED8;
    gridline-color: #D0D7DE;
    selection-background-color: #D2DFE8;
}
QTableWidget#channelDataTable,
QTableWidget#graphCursorTable,
QTableWidget#graphStatisticsTable {
    gridline-color: transparent;
    outline: none;
    alternate-background-color: #E6EBEF;
}
QTableWidget#channelDataTable::item,
QTableWidget#graphCursorTable::item,
QTableWidget#graphStatisticsTable::item {
    padding: 6px 12px;
    border: none;
    border-bottom: 1px solid #D5DCE3;
}
QTableWidget#channelDataTable::item:hover,
QTableWidget#graphCursorTable::item:hover,
QTableWidget#graphStatisticsTable::item:hover {
    background-color: #DDE6EC;
}
QTableWidget#channelDataTable::item:selected {
    color: #163040;
    background-color: #D2DFE8;
}
QWidget#channelDataStatusCell { background: transparent; }
QWidget#graphCursorChannel,
QWidget#graphStatisticsChannel,
QWidget#graphCursorStatusCell,
QLabel#graphCursorChannelLabel,
QLabel#graphStatisticsChannelLabel { background-color: transparent; }
QLabel#graphCursorChannelLabel, QLabel#graphStatisticsChannelLabel {
    color: #202833;
    font-weight: 500;
}
QLabel#graphCursorSwatch, QLabel#graphStatisticsSwatch {
    min-width: 8px;
    max-width: 8px;
    min-height: 8px;
    max-height: 8px;
    border-radius: 4px;
    border: none;
}
QTableWidget#channelDataTable QHeaderView::section,
QTableWidget#graphCursorTable QHeaderView::section,
QTableWidget#graphStatisticsTable QHeaderView::section,
QTableWidget#eventListTable QHeaderView::section {
    color: #2A3340;
    background-color: #EDF1F5;
    border: 0;
    border-bottom: 1px solid #C5CED8;
    padding: 8px;
    font-weight: 600;
}
QTableWidget#channelDataTable QHeaderView::section,
QTableWidget#graphCursorTable QHeaderView::section,
QTableWidget#graphStatisticsTable QHeaderView::section {
    color: #2A3340;
    background-color: #E4E9EE;
    padding: 9px 12px;
    border-bottom: 1px solid #B7C2CD;
    font-size: 9pt;
    letter-spacing: 0.5px;
}
QLabel#dataEmptyLabel, QLabel#graphsEmptyLabel {
    color: #586574;
    font-size: 12pt;
}
QGroupBox {
    color: #2A3340;
    background-color: #EDF1F5;
    border: 1px solid #C5CED8;
    border-radius: 5px;
    margin-top: 9px;
    padding-top: 6px;
    font-weight: 600;
}
QGroupBox::title { subcontrol-origin: margin; left: 9px; padding: 0 5px; }
QGroupBox QLabel, QGroupBox QCheckBox {
    color: #586574; background: transparent; font-weight: 400;
}
QStatusBar {
    color: #586574;
    background-color: #DDE3EA;
    border-top: 1px solid #C5CED8;
}
QStatusBar::item { border: 0; }
QSplitter::handle { background-color: transparent; width: 8px; }
QScrollBar:vertical {
    width: 11px;
    background: #DDE3EA;
    margin: 0;
    border: none;
}
QScrollBar::handle:vertical {
    min-height: 28px;
    background: #8A9AAB;
    border-radius: 5px;
    margin: 2px;
}
QScrollBar::handle:vertical:hover { background: #6F8496; }
QScrollBar::handle:vertical:pressed { background: #4F829B; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0; width: 0; background: none; border: none;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal {
    height: 11px;
    background: #DDE3EA;
    margin: 0;
    border: none;
}
QScrollBar::handle:horizontal {
    min-width: 28px;
    background: #8A9AAB;
    border-radius: 5px;
    margin: 2px;
}
QScrollBar::handle:horizontal:hover { background: #6F8496; }
QScrollBar::handle:horizontal:pressed { background: #4F829B; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    height: 0; width: 0; background: none; border: none;
}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }
QLabel#channelToggleBadge {
    color: #163F54;
    background-color: #D0DFE8;
    border-radius: 3px;
    padding: 0 4px;
    font-size: 8pt;
    font-weight: 600;
}
QLabel#calculatedChannelsHeading { color: #2A3340; font-weight: 600; }
QLabel#calculatedChannelStatus { color: #586574; }
QLabel#calculatedChannelPreview { color: #202833; font-weight: 600; }
QGroupBox#channelSettingsSection {
    color: #202833;
    background-color: #F3F6F8;
    border: 1px solid #C5CED8;
    border-radius: 6px;
    margin-top: 12px;
    padding: 10px 10px 8px 10px;
    font-weight: 600;
}
QGroupBox#channelSettingsSection::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #2A3340;
}
QTableWidget#channelSettingsTable,
QTableWidget#calculatedChannelsTable,
QTableWidget#parserPreviewTable,
QTableWidget#parserMappingTable,
QTableWidget#diagnosticsChannelTable,
QTableWidget#diagnosticsGapTable,
QTableWidget#modbusRegisterTable {
    color: #202833;
    background-color: #EEF2F5;
    alternate-background-color: #E4E9EE;
    border: 1px solid #C5CED8;
    gridline-color: #D0D7DE;
    selection-background-color: #D2DFE8;
}
QTableWidget#channelSettingsTable QHeaderView::section,
QTableWidget#calculatedChannelsTable QHeaderView::section,
QTableWidget#parserPreviewTable QHeaderView::section,
QTableWidget#parserMappingTable QHeaderView::section,
QTableWidget#diagnosticsChannelTable QHeaderView::section,
QTableWidget#diagnosticsGapTable QHeaderView::section,
QTableWidget#modbusRegisterTable QHeaderView::section {
    color: #2A3340;
    background-color: #EDF1F5;
    border: 0;
    border-bottom: 1px solid #C5CED8;
    padding: 8px 10px;
    font-weight: 600;
}
QLabel#channelSettingsReadOnly {
    color: #586574;
    background-color: transparent;
    padding: 0 6px;
}
QLineEdit#channelSettingsAlias,
QLineEdit#channelSettingsAlarm {
    min-height: 28px;
    padding: 2px 8px;
    background-color: #F7F9FA;
    border: 1px solid #C5CED8;
    border-radius: 4px;
}
QLineEdit#channelSettingsAlias:hover,
QLineEdit#channelSettingsAlarm:hover { border-color: #8AA3B3; }
QLineEdit#channelSettingsAlias:focus,
QLineEdit#channelSettingsAlarm:focus { border-color: #2A7AA8; }
QLineEdit#channelSettingsAlarm[validationState="error"] {
    border-color: #A33A44;
    background-color: #EDD8DB;
}
QLabel#calculatedChannelsEmpty {
    color: #6B7785;
    padding: 18px 8px;
}
QPushButton#addCalculatedButton {
    color: #163F54;
    background-color: #D0DFE8;
    border-color: #8AA3B3;
}
QPushButton#addCalculatedButton:hover { background-color: #C2D4DE; }
QPushButton#deleteCalculatedButton {
    color: #7A4249;
    background-color: #EBDDE0;
    border-color: #C9A8AD;
}
QPushButton#deleteCalculatedButton:hover { background-color: #E0CDD1; }
QPushButton#dialogPrimaryButton {
    color: #F7F9FA;
    background-color: #2A7AA8;
    border-color: #21658C;
}
QPushButton#dialogPrimaryButton:hover { background-color: #3189BB; }
QPushButton#dialogSecondaryButton {
    color: #202833;
    background-color: #DDE4EA;
    border-color: #B7C2CD;
}
"""

# Backward-compatible name for callers that explicitly request the dark style.
APPLICATION_STYLE = DARK_STYLE
