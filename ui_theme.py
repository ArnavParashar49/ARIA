"""Shared UI colors and helpers — sharp dark theme with electric-blue accent."""
import platform

from PySide6.QtGui import QColor


class C:
    # Core surfaces — deep charcoal (reference: #121212)
    BG        = "#121212"
    SURFACE   = "#1a1a1a"
    SURFACE2  = "#242424"
    PANEL     = "#121212"
    PANEL2    = "#1e1e1e"
    BORDER    = "rgba(255, 255, 255, 0.07)"
    BORDER_B  = "rgba(255, 255, 255, 0.12)"
    BORDER_A  = "rgba(255, 255, 255, 0.05)"
    # Text
    PRI       = "#ffffff"
    PRI_DIM   = "#a1a1aa"
    PRI_GHO   = "#52525b"
    ACC       = "#d4d4d8"
    ACC2      = "#71717a"
    GREEN     = "#6ee7a0"
    GREEN_D   = "#3d9a6a"
    RED       = "#f87171"
    MUTED_C   = "#71717a"
    TEXT      = "#ffffff"
    TEXT_DIM  = "#a1a1aa"
    TEXT_MED  = "#71717a"
    WHITE     = "#fafafa"
    DARK      = "#121212"
    BAR_BG    = "#1a1a1a"
    USER_BUB  = "#2a2a2e"
    # Accents — electric blue glow
    BLUE      = "#3b82f6"
    BLUE_L    = "#60a5fa"
    BLUE_D    = "#2563eb"
    BLUE_GLOW = "rgba(59, 130, 246, 0.45)"
    PURPLE    = "#a855f7"
    USER      = "#fafafa"
    AI        = "#f4f4f5"
    LINK      = "#60a5fa"
    ACCENT    = BLUE


RADIUS_L = 20
RADIUS_M = 14
RADIUS_S = 10

PANEL_GLASS_BG = "rgba(18, 18, 18, 0.92)"
PANEL_GLASS_BORDER = "rgba(255, 255, 255, 0.08)"
PANEL_GLASS_INNER = "rgba(18, 18, 18, 0.96)"

_UI_FONT = (
    ".AppleSystemUIFont"
    if platform.system() == "Darwin"
    else "Segoe UI"
)
_MONO_FONT = "Menlo" if platform.system() == "Darwin" else "Consolas"
_UI_FONT_FAMILY = _UI_FONT


def ui_font(size: int = 13, bold: bool = False) -> str:
    w = "bold" if bold else "normal"
    return f'font-family: "{_UI_FONT}"; font-size: {size}pt; font-weight: {w};'


def mono_font(size: int = 12) -> str:
    return f'font-family: "{_MONO_FONT}"; font-size: {size}pt;'


def qcol(h: str, a: int = 255) -> QColor:
    c = QColor(h)
    c.setAlpha(a)
    return c


def expanded_shell_stylesheet() -> str:
    return """
        QMainWindow#neoExpandedShell,
        QWidget#neoExpandedShell {
            background: transparent;
        }
        QLabel {
            background: transparent;
        }
    """


def panel_card_stylesheet() -> str:
    return f"""
        QFrame#neoPanelCard {{
            background: {C.BG};
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: {RADIUS_L}px;
        }}
    """


def panel_card_compact_stylesheet() -> str:
    """Compact siri bar — fully transparent; only the orb is visible."""
    return """
        QFrame#neoPanelCard {
            background: transparent;
            border: none;
        }
    """


def log_widget_stylesheet() -> str:
    return f"""
        QTextEdit {{
            background: transparent;
            color: {C.TEXT};
            border: none;
            border-radius: {RADIUS_M}px;
            padding: 8px 10px;
            selection-background-color: rgba(59, 130, 246, 0.35);
        }}
        QScrollBar:vertical {{
            background: transparent;
            width: 5px;
            margin: 4px 1px;
        }}
        QScrollBar::handle:vertical {{
            background: rgba(255, 255, 255, 0.14);
            border-radius: 2px;
            min-height: 24px;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0;
        }}
    """


def command_input_stylesheet(*, focused: bool = False) -> str:
    border = C.BLUE if focused else "rgba(255, 255, 255, 0.10)"
    bg = C.SURFACE if not focused else "#1a1a1e"
    return f"""
        QTextEdit {{
            background: {bg};
            color: {C.TEXT};
            border: 2px solid {border};
            border-radius: 22px;
            padding: 10px 16px;
        }}
    """


def command_input_drag_stylesheet() -> str:
    return f"""
        QTextEdit {{
            background: {C.SURFACE2};
            color: {C.TEXT};
            border: 2px solid {C.BLUE};
            border-radius: 22px;
            padding: 10px 16px;
        }}
    """


def input_container_stylesheet(*, focused: bool = False, dragging: bool = False) -> str:
    if dragging or focused:
        border = f"2px solid {C.BLUE}"
        bg = "#1a1a1e"
    else:
        border = "1.5px solid rgba(255, 255, 255, 0.10)"
        bg = C.SURFACE
    return f"""
        QFrame#inputContainer {{
            background: {bg};
            border: {border};
            border-radius: 22px;
        }}
    """


def pill_toolbar_button_stylesheet(*, active: bool = False) -> str:
    if active:
        bg = "rgba(59, 130, 246, 0.12)"
        border = "rgba(59, 130, 246, 0.35)"
        color = C.BLUE_L
    else:
        bg = C.SURFACE2
        border = "rgba(255, 255, 255, 0.08)"
        color = C.TEXT_DIM
    return f"""
        QPushButton {{
            background: {bg};
            color: {color};
            border: 1px solid {border};
            border-radius: 14px;
            padding: 5px 12px;
            {ui_font(10)}
        }}
        QPushButton:hover {{
            background: rgba(255, 255, 255, 0.06);
            color: {C.TEXT};
            border: 1px solid rgba(255, 255, 255, 0.14);
        }}
    """


def header_icon_button_stylesheet() -> str:
    return f"""
        QPushButton {{
            background: transparent;
            color: {C.TEXT_MED};
            border: none;
            border-radius: 8px;
            padding: 4px 6px;
            min-width: 28px;
            min-height: 28px;
            {ui_font(12)}
        }}
        QPushButton:hover {{
            background: rgba(255, 255, 255, 0.06);
            color: {C.TEXT};
        }}
    """


def ghost_action_button_stylesheet() -> str:
    return f"""
        QPushButton {{
            background: transparent;
            color: {C.TEXT_DIM};
            border: 1px solid rgba(255, 255, 255, 0.10);
            border-radius: 12px;
            padding: 4px 10px;
            {ui_font(9)}
        }}
        QPushButton:hover {{
            background: rgba(255, 255, 255, 0.05);
            color: {C.TEXT};
            border: 1px solid rgba(255, 255, 255, 0.16);
        }}
    """


def icon_button_stylesheet() -> str:
    return header_icon_button_stylesheet()


def primary_button_stylesheet() -> str:
    return f"""
        QPushButton {{
            background: {C.BLUE};
            color: #ffffff;
            border: none;
            border-radius: 18px;
            {ui_font(12, bold=True)}
        }}
        QPushButton:hover {{ background: {C.BLUE_L}; }}
        QPushButton:pressed {{ background: {C.BLUE_D}; }}
    """


def progress_bar_stylesheet() -> str:
    return f"""
        QProgressBar {{
            background: rgba(255, 255, 255, 0.06);
            border: none;
            border-radius: 2px;
        }}
        QProgressBar::chunk {{
            background: qlineargradient(
                x1:0, y1:0, x2:1, y2:0,
                stop:0 {C.BLUE}, stop:1 {C.BLUE_L}
            );
            border-radius: 2px;
        }}
    """


def embed_panel_stylesheet() -> str:
    return f"""
        QLabel {{
            background: {C.SURFACE2};
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: {RADIUS_M}px;
            color: {C.TEXT_DIM};
        }}
    """
