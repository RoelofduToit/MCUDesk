from pathlib import Path

from serialscope import PRODUCT_NAME, STORAGE_APP_NAME, __version__
from serialscope.app import main
from serialscope.data.calculated_store import default_calculated_path
from serialscope.logging.multi_session import MultiSourceRecordingSession
from serialscope.logging.session import RecordingSession
from serialscope.profiles.store import default_profile_path
from serialscope.resources import APPLICATION_ICON
from serialscope.updates.model import GITHUB_REPOSITORY, REPOSITORY_URL

STABLE_WINDOWS_APP_ID = "{E893C988-663D-46E8-8C25-E4B83C414F1E}"
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_product_name_is_mcudesk_and_internal_package_is_serialscope() -> None:
    assert PRODUCT_NAME == "MCUDesk"
    assert STORAGE_APP_NAME == "SerialScope"
    assert __version__ == "0.15.0"
    assert Path("src/serialscope").is_dir()
    assert APPLICATION_ICON.as_posix() == "assets/icons/mcudesk.png"
    assert GITHUB_REPOSITORY == "MCUDesk"
    assert REPOSITORY_URL == "https://github.com/RoelofduToit/MCUDesk"


def test_application_startup_keeps_serialscope_settings_identity() -> None:
    source = Path(main.__code__.co_filename).with_name("app.py").read_text("utf-8")
    assert "setApplicationName(STORAGE_APP_NAME)" in source
    assert "setOrganizationName(STORAGE_APP_NAME)" in source
    assert "setApplicationDisplayName(PRODUCT_NAME)" in source


def test_profiles_calculated_channels_and_sessions_keep_existing_identity() -> None:
    profile_source = Path(default_profile_path.__code__.co_filename).read_text("utf-8")
    calculated_source = Path(default_calculated_path.__code__.co_filename).read_text(
        "utf-8"
    )
    session_source = Path(RecordingSession.__init__.__code__.co_filename).read_text(
        "utf-8"
    )
    multi_source = Path(
        MultiSourceRecordingSession.__init__.__code__.co_filename
    ).read_text("utf-8")
    assert "AppConfigLocation" in profile_source
    assert "device_profiles.json" in profile_source
    assert "AppConfigLocation" in calculated_source
    assert "calculated_channels.json" in calculated_source
    assert '"serialscope_version": __version__' in session_source
    assert '"serialscope_version": __version__' in multi_source


def test_windows_installer_appid_must_remain_exactly_unchanged() -> None:
    installer = (
        PROJECT_ROOT / "packaging" / "windows" / "serialscope.iss"
    ).read_text("utf-8")
    assert "AppId={{E893C988-663D-46E8-8C25-E4B83C414F1E}" in installer
    assert STABLE_WINDOWS_APP_ID in installer
    assert installer.count(STABLE_WINDOWS_APP_ID) == 1
    assert "AppId={{" in installer


def test_user_facing_ui_modules_do_not_contain_stale_serialscope_branding() -> None:
    ui_root = PROJECT_ROOT / "src" / "serialscope" / "ui"
    stale = []
    for path in ui_root.rglob("*.py"):
        text = path.read_text("utf-8")
        if "SerialScope" in text:
            stale.append(str(path.relative_to(PROJECT_ROOT)))
    assert stale == []


def test_active_github_urls_point_at_mcudesk() -> None:
    about = (PROJECT_ROOT / "src" / "serialscope" / "ui" / "about_dialog.py").read_text(
        "utf-8"
    )
    model = (PROJECT_ROOT / "src" / "serialscope" / "updates" / "model.py").read_text(
        "utf-8"
    )
    installer = (
        PROJECT_ROOT / "packaging" / "windows" / "serialscope.iss"
    ).read_text("utf-8")
    assert "RoelofduToit/SerialScope" not in about
    assert 'GITHUB_REPOSITORY = "MCUDesk"' in model
    assert "https://github.com/RoelofduToit/MCUDesk" in installer
    assert "RoelofduToit/SerialScope" not in installer
