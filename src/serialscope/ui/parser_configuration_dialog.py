"""Dialog for per-source parser configuration and sample preview."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from serialscope.parsing.parser_config import (
    DELIMITER_PRESETS,
    NAME_VALUE_SEPARATOR_PRESETS,
    PAIR_SEPARATOR_PRESETS,
    ColumnMapping,
    ParserConfiguration,
    ParserConfigurationError,
    generic_channel_name,
    last_sample_line,
    preview_sample,
    split_delimited_fields,
)


_MODE_LABELS = (
    ("auto", "Auto"),
    ("delimited", "Delimited"),
    ("key_value", "Key / Value"),
    ("json", "JSON Lines"),
)
_HEADER_LABELS = (
    ("auto", "Auto"),
    ("present", "Header present"),
    ("none", "No header"),
)


class ParserConfigurationDialog(QDialog):
    """Edit parser settings without owning serial or logging state."""

    def __init__(
        self,
        configuration: ParserConfiguration | None = None,
        *,
        recent_sample: str = "",
        apply_enabled: bool = True,
        apply_disabled_reason: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._recent_sample = recent_sample
        self._apply_allowed = apply_enabled
        self._apply_disabled_reason = apply_disabled_reason
        self._updating = False
        self.setObjectName("parserConfigurationDialog")
        self.setWindowTitle("Parser Configuration")
        self.setModal(True)
        self.setMinimumSize(520, 480)
        self.resize(620, 580)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 14, 16, 12)
        outer.setSpacing(12)

        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        mode_group = QGroupBox("Parser")
        mode_group.setObjectName("channelSettingsSection")
        mode_form = QFormLayout(mode_group)
        self.mode_combo = QComboBox()
        self.mode_combo.setObjectName("parserModeCombo")
        for value, label in _MODE_LABELS:
            self.mode_combo.addItem(label, value)
        mode_form.addRow("Input Format", self.mode_combo)
        layout.addWidget(mode_group)

        self.config_stack = QStackedWidget()
        self.config_stack.setObjectName("parserConfigStack")
        self.config_stack.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum
        )
        self.config_stack.addWidget(self._build_auto_page())
        self.config_stack.addWidget(self._build_delimited_page())
        self.config_stack.addWidget(self._build_key_value_page())
        self.config_stack.addWidget(self._build_json_page())
        layout.addWidget(self.config_stack)

        sample_group = QGroupBox("Sample Input")
        sample_group.setObjectName("channelSettingsSection")
        sample_layout = QVBoxLayout(sample_group)
        self.sample_input = QPlainTextEdit()
        self.sample_input.setObjectName("parserSampleInput")
        self.sample_input.setPlaceholderText(
            "Paste a line of serial data to preview parsing."
        )
        self.sample_input.setTabChangesFocus(True)
        self.sample_input.setMinimumHeight(56)
        self.sample_input.setMaximumHeight(90)
        sample_layout.addWidget(self.sample_input)
        recent_row = QHBoxLayout()
        self.use_recent_button = QPushButton("Use Recent Input")
        self.use_recent_button.setObjectName("parserUseRecentButton")
        self.use_recent_button.setEnabled(bool(recent_sample.strip()))
        recent_row.addWidget(self.use_recent_button)
        recent_row.addStretch()
        sample_layout.addLayout(recent_row)
        layout.addWidget(sample_group)

        preview_group = QGroupBox("Parsed Preview")
        preview_group.setObjectName("channelSettingsSection")
        preview_layout = QVBoxLayout(preview_group)
        self.preview_table = QTableWidget(0, 3)
        self.preview_table.setObjectName("parserPreviewTable")
        self.preview_table.setHorizontalHeaderLabels(["Channel", "Value", "State"])
        self.preview_table.verticalHeader().setVisible(False)
        self.preview_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.preview_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        header = self.preview_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        preview_layout.addWidget(self.preview_table)
        self.status_label = QLabel()
        self.status_label.setObjectName("mutedLabel")
        self.status_label.setWordWrap(True)
        preview_layout.addWidget(self.status_label)
        self.preview_table.setMinimumHeight(96)
        layout.addWidget(preview_group, 1)

        scroll = QScrollArea()
        scroll.setObjectName("parserBodyScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.apply_button = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.apply_button.setText("Apply")
        self.apply_button.setObjectName("dialogPrimaryButton")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        outer.addWidget(self.buttons)

        self.mode_combo.currentIndexChanged.connect(self._on_controls_changed)
        self.delimiter_combo.currentIndexChanged.connect(self._on_controls_changed)
        self.custom_delimiter.textChanged.connect(self._on_controls_changed)
        self.header_combo.currentIndexChanged.connect(self._on_controls_changed)
        self.pair_separator_combo.currentIndexChanged.connect(self._on_controls_changed)
        self.custom_pair_separator.textChanged.connect(self._on_controls_changed)
        self.name_value_combo.currentIndexChanged.connect(self._on_controls_changed)
        self.custom_name_value.textChanged.connect(self._on_controls_changed)
        self.sample_input.textChanged.connect(self._on_sample_changed)
        self.use_recent_button.clicked.connect(self._use_recent_sample)
        self.mapping_table.itemChanged.connect(self._on_controls_changed)

        self._load_configuration(configuration or ParserConfiguration())
        if apply_disabled_reason:
            self.status_label.setText(apply_disabled_reason)

    def configuration(self) -> ParserConfiguration:
        return self._read_configuration()

    def _build_auto_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        label = QLabel(
            "Auto keeps MCUDesk's current format detection. "
            "Use a specific format only when the incoming data needs an explicit mapping."
        )
        label.setObjectName("mutedLabel")
        label.setWordWrap(True)
        layout.addWidget(label)
        return page

    def _build_delimited_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        form = QFormLayout()
        delimiter_row = QWidget()
        delimiter_layout = QHBoxLayout(delimiter_row)
        delimiter_layout.setContentsMargins(0, 0, 0, 0)
        self.delimiter_combo = QComboBox()
        self.delimiter_combo.setObjectName("parserDelimiterCombo")
        for key, value, label in DELIMITER_PRESETS:
            self.delimiter_combo.addItem(label, value)
        self.delimiter_combo.addItem("Custom", "__custom__")
        self.custom_delimiter = QLineEdit()
        self.custom_delimiter.setObjectName("parserCustomDelimiter")
        self.custom_delimiter.setMaximumWidth(80)
        self.custom_delimiter.setPlaceholderText("e.g. |")
        delimiter_layout.addWidget(self.delimiter_combo)
        delimiter_layout.addWidget(self.custom_delimiter)
        form.addRow("Delimiter", delimiter_row)

        self.header_combo = QComboBox()
        self.header_combo.setObjectName("parserHeaderCombo")
        for value, label in _HEADER_LABELS:
            self.header_combo.addItem(label, value)
        form.addRow("Header", self.header_combo)
        layout.addLayout(form)

        self.mapping_table = QTableWidget(0, 4)
        self.mapping_table.setObjectName("parserMappingTable")
        self.mapping_table.setHorizontalHeaderLabels(
            ["Column", "Sample", "Channel Name", "Include"]
        )
        self.mapping_table.verticalHeader().setVisible(False)
        self.mapping_table.verticalHeader().setDefaultSectionSize(26)
        self.mapping_table.setMinimumHeight(120)
        self.mapping_table.setMaximumHeight(220)
        mapping_header = self.mapping_table.horizontalHeader()
        mapping_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        mapping_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        mapping_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        mapping_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.mapping_table.setColumnWidth(0, 70)
        self.mapping_table.setColumnWidth(3, 72)
        layout.addWidget(self.mapping_table)
        return page

    def _build_key_value_page(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        form.setContentsMargins(0, 0, 0, 0)
        pair_row = QWidget()
        pair_layout = QHBoxLayout(pair_row)
        pair_layout.setContentsMargins(0, 0, 0, 0)
        self.pair_separator_combo = QComboBox()
        self.pair_separator_combo.setObjectName("parserPairSeparatorCombo")
        for key, value, label in PAIR_SEPARATOR_PRESETS:
            self.pair_separator_combo.addItem(label, value)
        self.pair_separator_combo.addItem("Custom", "__custom__")
        self.custom_pair_separator = QLineEdit()
        self.custom_pair_separator.setMaximumWidth(80)
        pair_layout.addWidget(self.pair_separator_combo)
        pair_layout.addWidget(self.custom_pair_separator)
        form.addRow("Pair separator", pair_row)

        nv_row = QWidget()
        nv_layout = QHBoxLayout(nv_row)
        nv_layout.setContentsMargins(0, 0, 0, 0)
        self.name_value_combo = QComboBox()
        self.name_value_combo.setObjectName("parserNameValueSeparatorCombo")
        for key, value, label in NAME_VALUE_SEPARATOR_PRESETS:
            self.name_value_combo.addItem(label, value)
        self.name_value_combo.addItem("Custom", "__custom__")
        self.custom_name_value = QLineEdit()
        self.custom_name_value.setMaximumWidth(80)
        nv_layout.addWidget(self.name_value_combo)
        nv_layout.addWidget(self.custom_name_value)
        form.addRow("Name/value separator", nv_row)
        hint = QLabel("Keys become source channel names. Aliases and units stay in Channel Settings.")
        hint.setObjectName("mutedLabel")
        hint.setWordWrap(True)
        form.addRow(hint)
        return page

    def _build_json_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        label = QLabel(
            "JSON Lines parses one JSON object per serial line. "
            "Numeric top-level fields become channels."
        )
        label.setObjectName("mutedLabel")
        label.setWordWrap(True)
        layout.addWidget(label)
        return page

    def _load_configuration(self, configuration: ParserConfiguration) -> None:
        self._updating = True
        self._set_combo_value(self.mode_combo, configuration.mode, "auto")
        self._set_separator_combo(
            self.delimiter_combo, self.custom_delimiter, configuration.delimiter
        )
        self._set_combo_value(self.header_combo, configuration.header_mode, "auto")
        self._set_separator_combo(
            self.pair_separator_combo,
            self.custom_pair_separator,
            configuration.pair_separator,
        )
        self._set_separator_combo(
            self.name_value_combo,
            self.custom_name_value,
            configuration.name_value_separator,
        )
        self._load_mapping_rows(configuration.columns, ())
        self._updating = False
        self._refresh_visible_pages()
        self._refresh_preview()

    def _set_combo_value(self, combo: QComboBox, value: str, fallback: str) -> None:
        index = combo.findData(value)
        if index < 0:
            index = combo.findData(fallback)
        combo.setCurrentIndex(max(0, index))

    def _set_separator_combo(
        self, combo: QComboBox, custom: QLineEdit, value: str
    ) -> None:
        index = combo.findData(value)
        if index < 0:
            combo.setCurrentIndex(combo.findData("__custom__"))
            custom.setText(value)
        else:
            combo.setCurrentIndex(index)
            custom.clear()
        custom.setVisible(combo.currentData() == "__custom__")

    def _read_separator(self, combo: QComboBox, custom: QLineEdit) -> str:
        value = combo.currentData()
        if value == "__custom__":
            return custom.text()
        return str(value)

    def _read_configuration(self) -> ParserConfiguration:
        mode = str(self.mode_combo.currentData() or "auto")
        if mode == "auto":
            return ParserConfiguration()
        if mode == "json":
            return ParserConfiguration(mode="json")
        header_mode = str(self.header_combo.currentData() or "auto")
        columns = (
            self._read_mapping_rows()
            if mode == "delimited" and header_mode == "none"
            else ()
        )
        return ParserConfiguration(
            mode=mode,
            delimiter=self._read_separator(self.delimiter_combo, self.custom_delimiter),
            header_mode=header_mode,
            columns=columns,
            pair_separator=self._read_separator(
                self.pair_separator_combo, self.custom_pair_separator
            ),
            name_value_separator=self._read_separator(
                self.name_value_combo, self.custom_name_value
            ),
        )

    def _try_configuration(self) -> tuple[ParserConfiguration | None, str | None]:
        try:
            return self._read_configuration(), None
        except (ParserConfigurationError, ValueError, TypeError) as error:
            return None, str(error)

    def _read_mapping_rows(self) -> tuple[ColumnMapping, ...]:
        columns: list[ColumnMapping] = []
        for row in range(self.mapping_table.rowCount()):
            name_item = self.mapping_table.item(row, 2)
            include = self.mapping_table.cellWidget(row, 3)
            enabled = True
            if isinstance(include, QCheckBox):
                enabled = include.isChecked()
            columns.append(
                ColumnMapping(
                    index=row,
                    name=name_item.text() if name_item is not None else "",
                    enabled=enabled,
                )
            )
        return tuple(columns)

    def _load_mapping_rows(
        self, columns: tuple[ColumnMapping, ...], samples: tuple[str, ...]
    ) -> None:
        by_index = {column.index: column for column in columns}
        count = max(len(samples), max((column.index for column in columns), default=-1) + 1)
        self.mapping_table.blockSignals(True)
        self.mapping_table.setRowCount(count)
        for index in range(count):
            sample = samples[index] if index < len(samples) else ""
            existing = by_index.get(index)
            name = existing.name if existing is not None else generic_channel_name(index)
            enabled = existing.enabled if existing is not None else True
            number = QTableWidgetItem(str(index + 1))
            number.setFlags(
                Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
            )
            number.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            sample_item = QTableWidgetItem(sample)
            sample_item.setFlags(
                Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
            )
            name_item = QTableWidgetItem(name)
            include = QCheckBox()
            include.setChecked(enabled)
            include.setToolTip("Include this column as a channel")
            include.stateChanged.connect(self._on_controls_changed)
            self.mapping_table.setItem(index, 0, number)
            self.mapping_table.setItem(index, 1, sample_item)
            self.mapping_table.setItem(index, 2, name_item)
            self.mapping_table.setCellWidget(index, 3, include)
        self.mapping_table.blockSignals(False)

    def _sync_mapping_from_sample(self) -> None:
        if self.mode_combo.currentData() != "delimited":
            return
        if self.header_combo.currentData() != "none":
            return
        delimiter = self._read_separator(self.delimiter_combo, self.custom_delimiter)
        if not delimiter:
            return
        fields = split_delimited_fields(last_sample_line(self.sample_input.toPlainText()), delimiter)
        if not fields:
            return
        existing = self._read_mapping_rows()
        self._updating = True
        self._load_mapping_rows(existing, fields)
        self._updating = False

    def _refresh_visible_pages(self) -> None:
        mode = self.mode_combo.currentData()
        pages = {"auto": 0, "delimited": 1, "key_value": 2, "json": 3}
        self.config_stack.setCurrentIndex(pages.get(mode, 0))
        custom_delimiter = self.delimiter_combo.currentData() == "__custom__"
        self.custom_delimiter.setVisible(custom_delimiter)
        self.custom_pair_separator.setVisible(
            self.pair_separator_combo.currentData() == "__custom__"
        )
        self.custom_name_value.setVisible(
            self.name_value_combo.currentData() == "__custom__"
        )
        show_mapping = mode == "delimited" and self.header_combo.currentData() == "none"
        self.mapping_table.setVisible(show_mapping)
        page = self.config_stack.currentWidget()
        if page is not None:
            self.config_stack.setMaximumHeight(max(1, page.sizeHint().height()))

    def _use_recent_sample(self) -> None:
        if self._recent_sample.strip():
            self.sample_input.setPlainText(self._recent_sample.strip())

    def _on_sample_changed(self) -> None:
        if self._updating:
            return
        self._sync_mapping_from_sample()
        self._refresh_preview()

    def _on_controls_changed(self) -> None:
        if self._updating:
            return
        self._refresh_visible_pages()
        if self.mode_combo.currentData() == "delimited":
            self._sync_mapping_from_sample()
        self._refresh_preview()

    def _refresh_preview(self) -> None:
        configuration, error = self._try_configuration()
        apply_ok = error is None and self._apply_allowed
        self.apply_button.setEnabled(apply_ok)
        if error is not None:
            self._set_preview_entries(())
            message = error
            if self._apply_disabled_reason:
                message = f"{error}\n{self._apply_disabled_reason}"
            self.status_label.setText(message)
            return
        preview = preview_sample(configuration, self.sample_input.toPlainText())
        self._set_preview_entries(preview.entries)
        message = preview.message
        if self._apply_disabled_reason:
            message = f"{message}\n{self._apply_disabled_reason}"
        self.status_label.setText(message)

    def _set_preview_entries(self, entries) -> None:
        self.preview_table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            for column, text in enumerate((entry.channel, entry.value, entry.state)):
                item = QTableWidgetItem(text)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.preview_table.setItem(row, column, item)
