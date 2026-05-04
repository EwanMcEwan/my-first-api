"""
TradeVue — Redesigned Chart Analysis Application
Light, clean, professional trading assistant with live market data popups
"""
import sys
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QFrame, QScrollArea,
    QFileDialog, QDialog, QGraphicsDropShadowEffect, QSplitter,
    QProgressBar, QTextEdit, QLineEdit, QGridLayout, QSizePolicy,
    QSpacerItem
)
from PySide6.QtCore import Qt, QThread, Signal, QSize, QPropertyAnimation, QEasingCurve, QRect, QTimer
from PySide6.QtGui import (
    QPixmap, QPainter, QColor, QFont, QPen, QBrush,
    QLinearGradient, QPainterPath, QPolygonF, QFontDatabase,
    QCursor
)
from PySide6.QtCore import QPointF
from api_client import TradeVueAPI
from chart_analyzer import ChartAnalyzer, AnalysisResult, TradeSignal
from market_data import MarketDataFetcher, MarketInfo, try_extract_ticker
 
 
# ── Palette ────────────────────────────────────────────────────────────────────
BG          = "#F5F7FF"
CARD_BG     = "#FFFFFF"
BORDER      = "#E8ECF6"
TEXT_DARK   = "#0F172A"
TEXT_MID    = "#475569"
TEXT_LIGHT  = "#94A3B8"
ACCENT      = "#6366F1"          # indigo
ACCENT_SOFT = "#EEF2FF"
BUY_CLR     = "#059669"          # emerald
BUY_SOFT    = "#D1FAE5"
SELL_CLR    = "#E11D48"          # rose
SELL_SOFT   = "#FFE4E6"
WARN_CLR    = "#D97706"
WARN_SOFT   = "#FEF3C7"
PURPLE      = "#7C3AED"
CYAN        = "#0891B2"
CYAN_SOFT   = "#E0F2FE"
 
STYLE = f"""
QMainWindow, QWidget {{
    background: {BG};
    font-family: 'Segoe UI', 'SF Pro Display', Arial, sans-serif;
    color: {TEXT_DARK};
}}
QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{
    background: transparent; width: 6px; margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {BORDER}; border-radius: 3px; min-height: 30px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QComboBox {{
    background: {CARD_BG};
    border: 1.5px solid {BORDER};
    border-radius: 10px;
    padding: 8px 14px;
    font-size: 13px;
    font-weight: 600;
    color: {TEXT_DARK};
    min-width: 130px;
}}
QComboBox:hover {{ border-color: {ACCENT}; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {TEXT_MID};
    width: 0; height: 0;
    margin-right: 8px;
}}
QComboBox QAbstractItemView {{
    background: {CARD_BG};
    border: 1.5px solid {BORDER};
    border-radius: 10px;
    selection-background-color: {ACCENT_SOFT};
    selection-color: {ACCENT};
    padding: 4px;
}}
QLineEdit {{
    background: {CARD_BG};
    border: 1.5px solid {BORDER};
    border-radius: 10px;
    padding: 8px 14px;
    font-size: 13px;
    color: {TEXT_DARK};
}}
QLineEdit:focus {{ border-color: {ACCENT}; }}
QLineEdit::placeholder {{ color: {TEXT_LIGHT}; }}
QDialog {{
    background: {CARD_BG};
}}
"""
 
 
def make_shadow(radius=20, offset_y=4, alpha=25):
    shadow = QGraphicsDropShadowEffect()
    shadow.setBlurRadius(radius)
    shadow.setColor(QColor(0, 0, 0, alpha))
    shadow.setOffset(0, offset_y)
    return shadow
 
 
# ── Reusable pill label ────────────────────────────────────────────────────────
class PillLabel(QLabel):
    def __init__(self, text, bg, fg, parent=None):
        super().__init__(text, parent)
        self.setStyleSheet(f"""
            background: {bg};
            color: {fg};
            border-radius: 10px;
            padding: 5px 14px;
            font-size: 13px;
            font-weight: 700;
        """)
        self.setAlignment(Qt.AlignCenter)
 
 
# ── Card base ──────────────────────────────────────────────────────────────────
class Card(QFrame):
    def __init__(self, parent=None, radius=18):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background: {CARD_BG};
                border-radius: {radius}px;
                border: 1.5px solid {BORDER};
            }}
        """)
        self.setGraphicsEffect(make_shadow(16, 3, 18))
 
 
# ── Icon button ───────────────────────────────────────────────────────────────
class IconButton(QPushButton):
    def __init__(self, icon_text, label, bg, hover_bg, fg="#FFFFFF", parent=None):
        super().__init__(parent)
        self._icon = icon_text
        self._label = label
        self._bg = bg
        self._hover = hover_bg
        self._fg = fg
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setStyleSheet(self._normal_style())
        self.setText(f"{icon_text}  {label}")
 
    def _normal_style(self):
        return f"""
            QPushButton {{
                background: {self._bg};
                color: {self._fg};
                border: none;
                border-radius: 12px;
                padding: 11px 20px;
                font-size: 13px;
                font-weight: 700;
                text-align: center;
            }}
            QPushButton:hover {{
                background: {self._hover};
            }}
            QPushButton:pressed {{
                opacity: 0.85;
            }}
        """
 
 
# ── Progress bar confidence ───────────────────────────────────────────────────
class ConfidenceBar(QWidget):
    def __init__(self, value=0, color=ACCENT, parent=None):
        super().__init__(parent)
        self.value = value
        self.color = color
        self.setFixedHeight(8)
 
    def set_value(self, v, color=None):
        self.value = v
        if color:
            self.color = color
        self.update()
 
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.rect()
        # Track
        p.setBrush(QColor(BORDER))
        p.setPen(Qt.NoPen)
        path = QPainterPath()
        path.addRoundedRect(r.x(), r.y(), r.width(), r.height(), 4, 4)
        p.drawPath(path)
        # Fill
        fill_w = int(r.width() * self.value)
        if fill_w > 0:
            fill_path = QPainterPath()
            fill_path.addRoundedRect(r.x(), r.y(), fill_w, r.height(), 4, 4)
            p.setBrush(QColor(self.color))
            p.drawPath(fill_path)
 
 
# ── Image drop zone with signal overlay ──────────────────────────────────────
class ImageDropZone(QFrame):
    imageLoaded = Signal(str)
 
    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setMinimumSize(420, 320)
        self.image_path = None
        self.base_pixmap = None       # original, unmodified
        self.display_pixmap = None    # with signals drawn on it
        self._hovered = False
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self._build_placeholder()
        self._apply_style(False)
 
    def _build_placeholder(self):
        self._layout = QVBoxLayout(self)
        self._layout.setAlignment(Qt.AlignCenter)
        self._layout.setSpacing(10)
 
        self.icon_lbl = QLabel("📊")
        self.icon_lbl.setStyleSheet("font-size: 52px; background: transparent; border: none;")
        self.icon_lbl.setAlignment(Qt.AlignCenter)
 
        self.hint_lbl = QLabel("Drop a chart screenshot here\nor click to browse")
        self.hint_lbl.setStyleSheet(f"font-size: 15px; color: {TEXT_LIGHT}; background: transparent; border: none; font-weight: 500;")
        self.hint_lbl.setAlignment(Qt.AlignCenter)
 
        self.sub_lbl = QLabel("PNG · JPG · WEBP · BMP")
        self.sub_lbl.setStyleSheet(f"font-size: 12px; color: {TEXT_LIGHT}; background: transparent; border: none;")
        self.sub_lbl.setAlignment(Qt.AlignCenter)
 
        self._layout.addWidget(self.icon_lbl)
        self._layout.addWidget(self.hint_lbl)
        self._layout.addWidget(self.sub_lbl)
 
    def _apply_style(self, hovered):
        border = ACCENT if hovered else "#CBD5E1"
        bg = ACCENT_SOFT if hovered else "#F8FAFF"
        self.setStyleSheet(f"""
            QFrame {{
                background: {bg};
                border: 2.5px dashed {border};
                border-radius: 20px;
            }}
        """)
 
    def enterEvent(self, e):
        if not self.base_pixmap:
            self._apply_style(True)
 
    def leaveEvent(self, e):
        if not self.base_pixmap:
            self._apply_style(False)
 
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self._apply_style(True)
 
    def dragLeaveEvent(self, e):
        self._apply_style(False)
 
    def dropEvent(self, e):
        self._apply_style(False)
        urls = e.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if path.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.bmp')):
                self._load(path)
 
    def mousePressEvent(self, e):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Chart Image", "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        if path:
            self._load(path)
 
    def _load(self, path):
        self.image_path = path
        self.base_pixmap = QPixmap(path)
        self.display_pixmap = self.base_pixmap.copy()
        # Hide placeholder text
        for w in [self.icon_lbl, self.hint_lbl, self.sub_lbl]:
            w.hide()
        self.setStyleSheet(f"""
            QFrame {{
                background: #0D1117;
                border: 2px solid {BORDER};
                border-radius: 20px;
            }}
        """)
        self.update()
        self.imageLoaded.emit(path)
 
    def draw_signals(self, signals):
        if not self.base_pixmap:
            return
        annotated = self.base_pixmap.copy()
        p = QPainter(annotated)
        p.setRenderHint(QPainter.Antialiasing)
 
        iw, ih = annotated.width(), annotated.height()
        ref_w, ref_h = 800, 600
 
        for sig in signals:
            rx, ry = sig.position
            x = int(rx * iw / ref_w)
            y = int(ry * ih / ref_h)
            is_buy = sig.signal_type == "BUY"
            clr = QColor(BUY_CLR if is_buy else SELL_CLR)
            soft = QColor(BUY_SOFT if is_buy else SELL_SOFT)
 
            # Glow circle
            glow = QColor(clr)
            glow.setAlpha(60)
            p.setBrush(glow)
            p.setPen(Qt.NoPen)
            r = 18
            p.drawEllipse(x - r, y - r, r * 2, r * 2)
 
            # Solid inner circle
            p.setBrush(clr)
            p.drawEllipse(x - 8, y - 8, 16, 16)
 
            # Arrow
            arrow_clr = QColor("#FFFFFF")
            p.setPen(QPen(arrow_clr, 2.5))
            if is_buy:
                # Up arrow
                p.drawLine(x, y + 4, x, y - 4)
                p.drawLine(x, y - 4, x - 3, y)
                p.drawLine(x, y - 4, x + 3, y)
            else:
                # Down arrow
                p.drawLine(x, y - 4, x, y + 4)
                p.drawLine(x, y + 4, x - 3, y)
                p.drawLine(x, y + 4, x + 3, y)
 
            # Confidence badge
            conf_pct = int(sig.confidence * 100)
            font = QFont("Segoe UI", 7, QFont.Bold)
            p.setFont(font)
            badge_text = f"{conf_pct}%"
            badge_w, badge_h = 28, 14
            p.setBrush(clr)
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(x - badge_w // 2, y - r - badge_h - 2, badge_w, badge_h, 4, 4)
            p.setPen(QColor("#FFFFFF"))
            p.drawText(QRect(x - badge_w // 2, y - r - badge_h - 2, badge_w, badge_h),
                       Qt.AlignCenter, badge_text)
 
        p.end()
        self.display_pixmap = annotated
        self.update()
 
    def paintEvent(self, event):
        super().paintEvent(event)
        pix = self.display_pixmap or self.base_pixmap
        if pix:
            p = QPainter(self)
            p.setRenderHint(QPainter.SmoothPixmapTransform)
            margin = 12
            target = QSize(self.width() - margin * 2, self.height() - margin * 2)
            scaled = pix.scaled(target, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            # Rounded clip
            path = QPainterPath()
            path.addRoundedRect(x, y, scaled.width(), scaled.height(), 12, 12)
            p.setClipPath(path)
            p.drawPixmap(x, y, scaled)
 
 
# ── Popup dialogs ─────────────────────────────────────────────────────────────
class BaseDialog(QDialog):
    def __init__(self, title_text, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title_text)
        self.setMinimumWidth(440)
        self.setStyleSheet(f"""
            QDialog {{
                background: {CARD_BG};
                border-radius: 20px;
            }}
            QLabel {{
                background: transparent;
                color: {TEXT_DARK};
            }}
        """)
        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(28, 24, 28, 24)
        self._root.setSpacing(16)
 
        # Header
        hdr = QHBoxLayout()
        ttl = QLabel(title_text)
        ttl.setStyleSheet(f"font-size: 18px; font-weight: 700; color: {TEXT_DARK};")
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(32, 32)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: {BG};
                color: {TEXT_MID};
                border: none;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 700;
            }}
            QPushButton:hover {{ background: {BORDER}; }}
        """)
        close_btn.clicked.connect(self.close)
        hdr.addWidget(ttl)
        hdr.addStretch()
        hdr.addWidget(close_btn)
        self._root.addLayout(hdr)
 
        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"color: {BORDER}; background: {BORDER};")
        sep.setFixedHeight(1)
        self._root.addWidget(sep)
 
    def add_widget(self, w):
        self._root.addWidget(w)
 
    def add_layout(self, l):
        self._root.addLayout(l)
 
 
class NewsDialog(BaseDialog):
    def __init__(self, news_items, parent=None):
        super().__init__("📰  Recent News", parent)
        self.setMinimumWidth(520)
 
        if not news_items:
            no_lbl = QLabel("No news available — enter a ticker symbol to load live news.")
            no_lbl.setStyleSheet(f"color: {TEXT_LIGHT}; font-size: 14px;")
            no_lbl.setWordWrap(True)
            self.add_widget(no_lbl)
            return
 
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(380)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
 
        inner = QWidget()
        inner.setStyleSheet("background: transparent;")
        vlayout = QVBoxLayout(inner)
        vlayout.setSpacing(10)
        vlayout.setContentsMargins(0, 0, 0, 0)
 
        for i, item in enumerate(news_items):
            card = QFrame()
            card.setStyleSheet(f"""
                QFrame {{
                    background: {BG};
                    border-radius: 12px;
                    border: 1px solid {BORDER};
                }}
            """)
            cl = QVBoxLayout(card)
            cl.setContentsMargins(14, 12, 14, 12)
            cl.setSpacing(4)
 
            pub = QLabel(item.get("publisher", ""))
            pub.setStyleSheet(f"color: {ACCENT}; font-size: 11px; font-weight: 600; background: transparent; border: none;")
 
            title = QLabel(item.get("title", ""))
            title.setWordWrap(True)
            title.setStyleSheet(f"color: {TEXT_DARK}; font-size: 13px; font-weight: 500; background: transparent; border: none;")
 
            cl.addWidget(pub)
            cl.addWidget(title)
            vlayout.addWidget(card)
 
        vlayout.addStretch()
        scroll.setWidget(inner)
        self.add_widget(scroll)
 
 
class MarketDialog(BaseDialog):
    def __init__(self, info: MarketInfo, parent=None):
        super().__init__(f"📊  {info.company_name}", parent)
        self.setMinimumWidth(480)
 
        if info.error:
            err = QLabel(f"⚠️  {info.error}")
            err.setStyleSheet(f"color: {WARN_CLR}; font-size: 13px;")
            err.setWordWrap(True)
            self.add_widget(err)
            return
 
        # Price row
        price_row = QHBoxLayout()
        p_lbl = QLabel(f"${info.current_price:.4f}" if info.current_price < 1 else f"${info.current_price:,.2f}")
        p_lbl.setStyleSheet(f"font-size: 28px; font-weight: 800; color: {TEXT_DARK};")
        tick_lbl = QLabel(info.ticker)
        tick_lbl.setStyleSheet(f"""
            background: {ACCENT_SOFT}; color: {ACCENT};
            border-radius: 8px; padding: 4px 12px;
            font-size: 13px; font-weight: 700;
        """)
        price_row.addWidget(p_lbl)
        price_row.addStretch()
        price_row.addWidget(tick_lbl)
        self.add_layout(price_row)
 
        if info.sector and info.sector != "N/A":
            sec = QLabel(f"Sector: {info.sector}")
            sec.setStyleSheet(f"color: {TEXT_MID}; font-size: 13px;")
            self.add_widget(sec)
 
        # Stats grid
        grid = QGridLayout()
        grid.setSpacing(10)
 
        stats = [
            ("Market Cap",     info.market_cap,                                     "🏦"),
            ("Avg Volume",     info.avg_volume,                                      "📈"),
            ("52W High",       f"${info.week_52_high:,.4f}" if info.week_52_high < 1 else f"${info.week_52_high:,.2f}", "⬆️"),
            ("52W Low",        f"${info.week_52_low:,.4f}" if info.week_52_low < 1 else f"${info.week_52_low:,.2f}",   "⬇️"),
            ("P/E Ratio",      f"{info.pe_ratio:.1f}" if info.pe_ratio else "N/A",  "📐"),
            ("Beta",           f"{info.beta:.2f}" if info.beta else "N/A",           "⚡"),
        ]
        if info.dividend_yield:
            stats.append(("Dividend Yield", f"{info.dividend_yield:.2f}%", "💰"))
 
        for i, (label, value, icon) in enumerate(stats):
            cell = QFrame()
            cell.setStyleSheet(f"""
                QFrame {{
                    background: {BG};
                    border-radius: 12px;
                    border: 1px solid {BORDER};
                }}
            """)
            cl = QVBoxLayout(cell)
            cl.setContentsMargins(14, 12, 14, 12)
            cl.setSpacing(2)
            lbl = QLabel(f"{icon} {label}")
            lbl.setStyleSheet(f"color: {TEXT_LIGHT}; font-size: 11px; font-weight: 600; background: transparent; border: none;")
            val = QLabel(value)
            val.setStyleSheet(f"color: {TEXT_DARK}; font-size: 15px; font-weight: 700; background: transparent; border: none;")
            cl.addWidget(lbl)
            cl.addWidget(val)
            grid.addWidget(cell, i // 2, i % 2)
 
        stats_w = QWidget()
        stats_w.setStyleSheet("background: transparent;")
        stats_w.setLayout(grid)
        self.add_widget(stats_w)
 
        if info.description:
            desc = QTextEdit()
            desc.setReadOnly(True)
            desc.setPlainText(info.description)
            desc.setFixedHeight(90)
            desc.setStyleSheet(f"""
                QTextEdit {{
                    background: {BG}; border: 1px solid {BORDER};
                    border-radius: 10px; padding: 10px;
                    font-size: 12px; color: {TEXT_MID};
                }}
            """)
            self.add_widget(desc)
 
 
class VolatilityDialog(BaseDialog):
    def __init__(self, result: AnalysisResult, parent=None):
        super().__init__("⚡  Volatility & Risk", parent)
 
        risk_colors = {"LOW": BUY_CLR, "MEDIUM": WARN_CLR, "HIGH": SELL_CLR}
        risk_soft   = {"LOW": BUY_SOFT, "MEDIUM": WARN_SOFT, "HIGH": SELL_SOFT}
        clr = risk_colors.get(result.risk_level, ACCENT)
        soft = risk_soft.get(result.risk_level, ACCENT_SOFT)
 
        # Risk badge
        badge_row = QHBoxLayout()
        badge = QLabel(f"  {result.risk_level} RISK  ")
        badge.setStyleSheet(f"""
            background: {soft}; color: {clr};
            border-radius: 12px; padding: 10px 20px;
            font-size: 18px; font-weight: 800;
        """)
        badge.setAlignment(Qt.AlignCenter)
        badge_row.addStretch()
        badge_row.addWidget(badge)
        badge_row.addStretch()
        self.add_layout(badge_row)
 
        # Confidence bar
        conf_w = QWidget()
        conf_w.setStyleSheet(f"background: {BG}; border-radius: 14px;")
        cf = QVBoxLayout(conf_w)
        cf.setContentsMargins(16, 14, 16, 14)
        cf.setSpacing(8)
 
        cf_title = QLabel("Analysis Confidence")
        cf_title.setStyleSheet(f"font-size: 13px; color: {TEXT_MID}; font-weight: 600;")
        pct = int(result.confidence * 100)
        cf_val = QLabel(f"{pct}%")
        cf_val.setStyleSheet(f"font-size: 24px; font-weight: 800; color: {clr};")
 
        bar = ConfidenceBar(result.confidence, clr)
        bar.setFixedHeight(10)
 
        cf.addWidget(cf_title)
        cf.addWidget(cf_val)
        cf.addWidget(bar)
        self.add_widget(conf_w)
 
        # Signal breakdown
        buy_c  = sum(1 for s in result.signals if s.signal_type == "BUY")
        sell_c = len(result.signals) - buy_c
        sig_row = QHBoxLayout()
 
        for label, count, bg, fg in [
            (f"🟢  {buy_c} Buy",  buy_c,  BUY_SOFT,  BUY_CLR),
            (f"🔴  {sell_c} Sell", sell_c, SELL_SOFT, SELL_CLR),
        ]:
            w = QFrame()
            w.setStyleSheet(f"background: {bg}; border-radius: 12px;")
            wl = QVBoxLayout(w)
            wl.setContentsMargins(14, 12, 14, 12)
            l = QLabel(label)
            l.setStyleSheet(f"color: {fg}; font-size: 15px; font-weight: 700;")
            l.setAlignment(Qt.AlignCenter)
            wl.addWidget(l)
            sig_row.addWidget(w)
 
        sig_w = QWidget()
        sig_w.setStyleSheet("background: transparent;")
        sig_w.setLayout(sig_row)
        self.add_widget(sig_w)
 
        # Patterns
        for pat in result.detected_patterns:
            p_lbl = QLabel(pat)
            p_lbl.setStyleSheet(f"""
                background: {BG}; color: {TEXT_DARK};
                border: 1px solid {BORDER}; border-radius: 10px;
                padding: 8px 14px; font-size: 14px; font-weight: 500;
            """)
            self.add_widget(p_lbl)
 
 
class SignalsDialog(BaseDialog):
    def __init__(self, result: AnalysisResult, parent=None):
        super().__init__("🎯  Buy & Sell Signals", parent)
        self.setMinimumWidth(460)
 
        if not result.signals:
            no = QLabel("No strong signals detected in this chart.\nTry a higher-resolution image or different timeframe.")
            no.setStyleSheet(f"color: {TEXT_LIGHT}; font-size: 14px;")
            no.setWordWrap(True)
            self.add_widget(no)
            return
 
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(400)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
 
        inner = QWidget()
        inner.setStyleSheet("background: transparent;")
        vlayout = QVBoxLayout(inner)
        vlayout.setSpacing(8)
        vlayout.setContentsMargins(0, 0, 0, 0)
 
        for i, sig in enumerate(result.signals):
            is_buy = sig.signal_type == "BUY"
            bg  = BUY_SOFT if is_buy else SELL_SOFT
            clr = BUY_CLR if is_buy else SELL_CLR
            icon = "▲" if is_buy else "▼"
 
            card = QFrame()
            card.setStyleSheet(f"QFrame {{ background: {bg}; border-radius: 14px; }}")
            cl = QHBoxLayout(card)
            cl.setContentsMargins(16, 14, 16, 14)
 
            icon_lbl = QLabel(icon)
            icon_lbl.setStyleSheet(f"color: {clr}; font-size: 20px; font-weight: 900; background: transparent;")
            icon_lbl.setFixedWidth(28)
 
            info_w = QWidget()
            info_w.setStyleSheet("background: transparent;")
            il = QVBoxLayout(info_w)
            il.setContentsMargins(0, 0, 0, 0)
            il.setSpacing(2)
 
            type_lbl = QLabel(f"{sig.signal_type} Signal #{i+1}")
            type_lbl.setStyleSheet(f"color: {clr}; font-size: 14px; font-weight: 700; background: transparent;")
            reason_lbl = QLabel(sig.reason)
            reason_lbl.setStyleSheet(f"color: {TEXT_MID}; font-size: 12px; background: transparent;")
 
            il.addWidget(type_lbl)
            il.addWidget(reason_lbl)
 
            conf_lbl = QLabel(f"{int(sig.confidence * 100)}%")
            conf_lbl.setStyleSheet(f"color: {clr}; font-size: 16px; font-weight: 800; background: transparent;")
            conf_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
 
            cl.addWidget(icon_lbl)
            cl.addWidget(info_w, stretch=1)
            cl.addWidget(conf_lbl)
 
            vlayout.addWidget(card)
 
        vlayout.addStretch()
        scroll.setWidget(inner)
        self.add_widget(scroll)
 
 
# ── Analysis worker threads ───────────────────────────────────────────────────
class AnalysisWorker(QThread):
    finished = Signal(object)
    error    = Signal(str)
 
    def __init__(self, path, timeframe, api):
        super().__init__()
        self.path = path
        self.timeframe = timeframe
        self.api = api
        self.analyzer = ChartAnalyzer()
 
    def run(self):
        try:
            result = self.analyzer.analyze(self.path, self.timeframe)
            try:
                api_result = self.api.analyze_chart(self.path, self.timeframe)
            except Exception:
                pass
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))
 
 
class MarketWorker(QThread):
    finished = Signal(object)
 
    def __init__(self, ticker):
        super().__init__()
        self.ticker = ticker
 
    def run(self):
        fetcher = MarketDataFetcher()
        info = fetcher.fetch(self.ticker)
        self.finished.emit(info)
 
 
# ── Main Window ───────────────────────────────────────────────────────────────
class TradeVueApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.api = TradeVueAPI()
        self.analysis_result = None
        self.market_info = None
        self._setup_ui()
 
    def _setup_ui(self):
        self.setWindowTitle("TradeVue ✦")
        self.setMinimumSize(1240, 820)
        self.setStyleSheet(STYLE)
 
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(18)
 
        # ── Header ──────────────────────────────────────────────────────────
        header = QWidget()
        header.setStyleSheet("background: transparent;")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(0, 0, 0, 0)
 
        logo_w = QWidget()
        logo_w.setStyleSheet("background: transparent;")
        logo_l = QVBoxLayout(logo_w)
        logo_l.setContentsMargins(0, 0, 0, 0)
        logo_l.setSpacing(2)
 
        logo = QLabel("TradeVue  ✦")
        logo.setStyleSheet(f"font-size: 26px; font-weight: 800; color: {TEXT_DARK}; letter-spacing: -0.5px;")
        tagline = QLabel("AI-Powered Chart Analysis  •  Upload any chart to begin")
        tagline.setStyleSheet(f"font-size: 13px; color: {TEXT_LIGHT};")
        logo_l.addWidget(logo)
        logo_l.addWidget(tagline)
 
        # Status pill
        self.status_pill = QLabel("  Ready  ")
        self.status_pill.setStyleSheet(f"""
            background: {BUY_SOFT}; color: {BUY_CLR};
            border-radius: 10px; padding: 6px 14px;
            font-size: 12px; font-weight: 700;
        """)
 
        # Timeframe
        tf_label = QLabel("Timeframe")
        tf_label.setStyleSheet(f"font-size: 12px; color: {TEXT_LIGHT}; font-weight: 600;")
        self.tf_combo = QComboBox()
        self.tf_combo.addItems([
            "1 Min", "3 Min", "5 Min", "15 Min", "30 Min",
            "1 Hour", "2 Hours", "4 Hours", "6 Hours", "12 Hours",
            "1 Day", "3 Days", "1 Week", "1 Month"
        ])
        self.tf_combo.setCurrentText("15 Min")
 
        tf_w = QWidget()
        tf_w.setStyleSheet("background: transparent;")
        tf_l = QHBoxLayout(tf_w)
        tf_l.setContentsMargins(0, 0, 0, 0)
        tf_l.setSpacing(8)
        tf_l.addWidget(tf_label)
        tf_l.addWidget(self.tf_combo)
 
        hl.addWidget(logo_w)
        hl.addStretch()
        hl.addWidget(self.status_pill)
        hl.addSpacing(16)
        hl.addWidget(tf_w)
        root.addWidget(header)
 
        # ── Main splitter ────────────────────────────────────────────────────
        splitter = QSplitter(Qt.Horizontal)
        splitter.setStyleSheet("QSplitter::handle { background: transparent; width: 12px; }")
 
        # Left panel
        left = QWidget()
        left.setStyleSheet("background: transparent;")
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 8, 0)
        ll.setSpacing(12)
 
        self.drop_zone = ImageDropZone()
        self.drop_zone.imageLoaded.connect(self._on_image_loaded)
 
        # Ticker row (optional)
        ticker_row = QHBoxLayout()
        ticker_icon = QLabel("🔍")
        ticker_icon.setStyleSheet("font-size: 15px; background: transparent;")
        self.ticker_input = QLineEdit()
        self.ticker_input.setPlaceholderText("Ticker symbol for live data  (optional — e.g. AAPL, TSLA)")
        self.ticker_input.setStyleSheet(f"""
            QLineEdit {{
                background: {CARD_BG};
                border: 1.5px solid {BORDER};
                border-radius: 10px;
                padding: 9px 14px;
                font-size: 13px;
                color: {TEXT_DARK};
            }}
            QLineEdit:focus {{ border-color: {ACCENT}; }}
        """)
        ticker_row.addWidget(ticker_icon)
        ticker_row.addWidget(self.ticker_input)
 
        # Action buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
 
        self.add_btn = IconButton("➕", "Add Chart Image", BUY_CLR, "#047857")
        self.add_btn.clicked.connect(self._browse)
        self.add_btn.setMinimumHeight(48)
 
        self.analyze_btn = IconButton("🔍", "Analyze Chart", ACCENT, PURPLE)
        self.analyze_btn.clicked.connect(self._start_analysis)
        self.analyze_btn.setEnabled(False)
        self.analyze_btn.setMinimumHeight(48)
 
        btn_row.addWidget(self.add_btn)
        btn_row.addWidget(self.analyze_btn)
 
        ll.addWidget(self.drop_zone, stretch=1)
        ll.addLayout(ticker_row)
        ll.addLayout(btn_row)
 
        # Right panel
        right = QWidget()
        right.setStyleSheet("background: transparent;")
        rl = QVBoxLayout(right)
        rl.setContentsMargins(8, 0, 0, 0)
        rl.setSpacing(12)
 
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
 
        self._results_w = QWidget()
        self._results_w.setStyleSheet("background: transparent;")
        self._results_l = QVBoxLayout(self._results_w)
        self._results_l.setSpacing(14)
        self._results_l.setContentsMargins(2, 2, 8, 2)
        self._results_l.setAlignment(Qt.AlignTop)
 
        self._build_placeholder_cards()
        scroll.setWidget(self._results_w)
        rl.addWidget(scroll)
 
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([660, 520])
        root.addWidget(splitter, stretch=1)
 
        # Status bar
        self.status_bar = QLabel("Drop a chart screenshot to begin — any market, any timeframe")
        self.status_bar.setStyleSheet(f"color: {TEXT_LIGHT}; font-size: 12px; padding: 4px 2px;")
        root.addWidget(self.status_bar)
 
    # ── Placeholder cards ────────────────────────────────────────────────────
    def _build_placeholder_cards(self):
        self._clear_results()
 
        ph = Card()
        phl = QVBoxLayout(ph)
        phl.setContentsMargins(28, 32, 28, 32)
        phl.setAlignment(Qt.AlignCenter)
        phl.setSpacing(10)
 
        ic = QLabel("📊")
        ic.setStyleSheet("font-size: 48px; background: transparent; border: none;")
        ic.setAlignment(Qt.AlignCenter)
 
        msg = QLabel("Analysis results will appear here")
        msg.setStyleSheet(f"font-size: 15px; color: {TEXT_LIGHT}; background: transparent; border: none;")
        msg.setAlignment(Qt.AlignCenter)
 
        sub = QLabel("Upload a chart image and click Analyze Chart")
        sub.setStyleSheet(f"font-size: 13px; color: {TEXT_LIGHT}; background: transparent; border: none;")
        sub.setAlignment(Qt.AlignCenter)
 
        phl.addWidget(ic)
        phl.addWidget(msg)
        phl.addWidget(sub)
        self._results_l.addWidget(ph)
 
    def _clear_results(self):
        while self._results_l.count():
            item = self._results_l.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
 
    # ── Event handlers ───────────────────────────────────────────────────────
    def _browse(self):
        self.drop_zone.mousePressEvent(None)
 
    def _on_image_loaded(self, path):
        self.analyze_btn.setEnabled(True)
        fname = Path(path).name
        self._set_status(f"✅ {fname} loaded", "ready")
        self.status_bar.setText(f"Image loaded: {fname}  •  Select timeframe and click Analyze Chart")
 
        # Auto-fill ticker if detectable from filename
        detected = try_extract_ticker(path)
        if detected and not self.ticker_input.text().strip():
            self.ticker_input.setText(detected)
            self.ticker_input.setStyleSheet(self.ticker_input.styleSheet() +
                                            f"color: {ACCENT}; font-weight: 600;")
 
    def _start_analysis(self):
        if not self.drop_zone.image_path:
            return
        self.analyze_btn.setEnabled(False)
        self.analyze_btn.setText("⏳  Analyzing…")
        self._set_status("Analyzing…", "busy")
        self.status_bar.setText("🔄  Running chart analysis — this may take a moment…")
 
        tf_map = {
            "1 Min": "1m", "3 Min": "3m", "5 Min": "5m",
            "15 Min": "15m", "30 Min": "30m",
            "1 Hour": "1H", "2 Hours": "2H", "4 Hours": "4H",
            "6 Hours": "6H", "12 Hours": "12H",
            "1 Day": "1D", "3 Days": "3D", "1 Week": "1W", "1 Month": "1M"
        }
        tf = tf_map.get(self.tf_combo.currentText(), "15m")
 
        self._worker = AnalysisWorker(self.drop_zone.image_path, tf, self.api)
        self._worker.finished.connect(self._on_analysis_done)
        self._worker.error.connect(self._on_error)
        self._worker.start()
 
        # Also kick off market data fetch if ticker provided
        ticker = self.ticker_input.text().strip().upper()
        if ticker:
            self._mworker = MarketWorker(ticker)
            self._mworker.finished.connect(self._on_market_done)
            self._mworker.start()
 
    def _on_analysis_done(self, result: AnalysisResult):
        self.analysis_result = result
        self.analyze_btn.setEnabled(True)
        self.analyze_btn.setText("🔍  Analyze Chart")
        self._set_status("✅  Complete", "ready")
        self.status_bar.setText("✅  Analysis complete!  Use the popup buttons to explore details.")
        self.drop_zone.draw_signals(result.signals)
        self._show_results(result)
 
    def _on_market_done(self, info: MarketInfo):
        self.market_info = info
 
    def _on_error(self, msg):
        self.analyze_btn.setEnabled(True)
        self.analyze_btn.setText("🔍  Analyze Chart")
        self._set_status("❌  Error", "error")
        self.status_bar.setText(f"❌  {msg}")
 
    def _set_status(self, text, mode="ready"):
        colors = {
            "ready":  (BUY_SOFT,  BUY_CLR),
            "busy":   (WARN_SOFT, WARN_CLR),
            "error":  (SELL_SOFT, SELL_CLR),
        }
        bg, fg = colors.get(mode, (BUY_SOFT, BUY_CLR))
        self.status_pill.setText(f"  {text}  ")
        self.status_pill.setStyleSheet(f"""
            background: {bg}; color: {fg};
            border-radius: 10px; padding: 6px 14px;
            font-size: 12px; font-weight: 700;
        """)
 
    # ── Build result cards ───────────────────────────────────────────────────
    def _show_results(self, r: AnalysisResult):
        self._clear_results()
 
        # 1. Sentiment card
        self._results_l.addWidget(self._make_sentiment_card(r))
        # 2. Popup action buttons
        self._results_l.addWidget(self._make_popup_buttons(r))
        # 3. Patterns card
        self._results_l.addWidget(self._make_patterns_card(r))
        # 4. Recommendation card
        self._results_l.addWidget(self._make_rec_card(r))
        # 5. Disclaimer
        disc = QLabel("⚠️  Not financial advice. Always do your own research before trading.")
        disc.setStyleSheet(f"color: {TEXT_LIGHT}; font-size: 11px; padding: 0 4px;")
        disc.setWordWrap(True)
        self._results_l.addWidget(disc)
        self._results_l.addStretch()
 
    def _make_sentiment_card(self, r: AnalysisResult) -> QWidget:
        card = Card()
        card.setGraphicsEffect(make_shadow(20, 4, 22))
        cl = QVBoxLayout(card)
        cl.setContentsMargins(24, 22, 24, 22)
        cl.setSpacing(14)
 
        sentiment_map = {
            "BULLISH": (BUY_CLR,  BUY_SOFT,  "📈  BULLISH"),
            "BEARISH": (SELL_CLR, SELL_SOFT, "📉  BEARISH"),
            "NEUTRAL": (WARN_CLR, WARN_SOFT, "📊  NEUTRAL"),
        }
        clr, soft, label_text = sentiment_map.get(r.overall_sentiment,
                                                    (TEXT_MID, BG, r.overall_sentiment))
 
        top_row = QHBoxLayout()
        title = QLabel("Market Sentiment")
        title.setStyleSheet(f"font-size: 13px; color: {TEXT_LIGHT}; font-weight: 600; background: transparent; border: none;")
 
        badge = QLabel(label_text)
        badge.setStyleSheet(f"""
            background: {soft}; color: {clr};
            border-radius: 10px; padding: 6px 16px;
            font-size: 14px; font-weight: 800;
        """)
        top_row.addWidget(title)
        top_row.addStretch()
        top_row.addWidget(badge)
        cl.addLayout(top_row)
 
        # Confidence
        conf_pct = int(r.confidence * 100)
        conf_row = QHBoxLayout()
        conf_lbl = QLabel("Confidence")
        conf_lbl.setStyleSheet(f"font-size: 13px; color: {TEXT_MID}; background: transparent; border: none;")
        conf_val = QLabel(f"{conf_pct}%")
        conf_val.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {clr}; background: transparent; border: none;")
        conf_row.addWidget(conf_lbl)
        conf_row.addStretch()
        conf_row.addWidget(conf_val)
        cl.addLayout(conf_row)
 
        bar = ConfidenceBar(r.confidence, clr)
        bar.setFixedHeight(8)
        cl.addWidget(bar)
 
        # Risk
        risk_clr_map = {"LOW": BUY_CLR, "MEDIUM": WARN_CLR, "HIGH": SELL_CLR}
        risk_clr = risk_clr_map.get(r.risk_level, TEXT_MID)
        risk_lbl = QLabel(f"Risk Level:  {r.risk_level}")
        risk_lbl.setStyleSheet(f"font-size: 13px; color: {risk_clr}; font-weight: 700; background: transparent; border: none;")
        cl.addWidget(risk_lbl)
 
        return card
 
    def _make_popup_buttons(self, r: AnalysisResult) -> QWidget:
        card = Card()
        cl = QVBoxLayout(card)
        cl.setContentsMargins(20, 18, 20, 18)
        cl.setSpacing(10)
 
        title = QLabel("Explore Details")
        title.setStyleSheet(f"font-size: 13px; color: {TEXT_LIGHT}; font-weight: 600;")
        cl.addWidget(title)
 
        grid = QGridLayout()
        grid.setSpacing(10)
 
        btn_defs = [
            ("🎯  Signals",    self._open_signals,    ACCENT,   PURPLE),
            ("⚡  Volatility", self._open_volatility, WARN_CLR, "#B45309"),
            ("📰  News",       self._open_news,       CYAN,     "#0E7490"),
            ("📊  Market Data",self._open_market,     PURPLE,   "#5B21B6"),
        ]
 
        for i, (label, handler, bg, hover) in enumerate(btn_defs):
            btn = IconButton("", label, bg, hover)
            btn.setText(label)
            btn.setMinimumHeight(42)
            btn.clicked.connect(handler)
            grid.addWidget(btn, i // 2, i % 2)
 
        cl.addLayout(grid)
        return card
 
    def _make_patterns_card(self, r: AnalysisResult) -> QWidget:
        card = Card()
        cl = QVBoxLayout(card)
        cl.setContentsMargins(22, 18, 22, 18)
        cl.setSpacing(10)
 
        title = QLabel("🔮  Detected Patterns")
        title.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {TEXT_DARK}; background: transparent; border: none;")
        cl.addWidget(title)
 
        for pat in r.detected_patterns:
            lbl = QLabel(pat)
            lbl.setStyleSheet(f"""
                background: {BG}; color: {TEXT_DARK};
                border: 1.5px solid {BORDER}; border-radius: 10px;
                padding: 9px 14px; font-size: 13px; font-weight: 500;
            """)
            cl.addWidget(lbl)
 
        return card
 
    def _make_rec_card(self, r: AnalysisResult) -> QWidget:
        card = Card()
        cl = QVBoxLayout(card)
        cl.setContentsMargins(22, 18, 22, 18)
        cl.setSpacing(10)
 
        title = QLabel("💡  Recommendation")
        title.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {TEXT_DARK}; background: transparent; border: none;")
        cl.addWidget(title)
 
        rec_lbl = QLabel(r.recommendation)
        rec_lbl.setWordWrap(True)
        rec_lbl.setStyleSheet(f"""
            background: {BG}; color: {TEXT_DARK};
            border: 1.5px solid {BORDER}; border-radius: 12px;
            padding: 14px 16px; font-size: 14px; line-height: 1.6;
        """)
        cl.addWidget(rec_lbl)
 
        # Buy / Sell count row
        buy_c  = sum(1 for s in r.signals if s.signal_type == "BUY")
        sell_c = len(r.signals) - buy_c
        sig_row = QHBoxLayout()
        sig_row.setSpacing(8)
 
        if buy_c:
            b = PillLabel(f"▲  {buy_c} Buy", BUY_SOFT, BUY_CLR)
            sig_row.addWidget(b)
        if sell_c:
            s = PillLabel(f"▼  {sell_c} Sell", SELL_SOFT, SELL_CLR)
            sig_row.addWidget(s)
        sig_row.addStretch()
        cl.addLayout(sig_row)
 
        return card
 
    # ── Popup openers ────────────────────────────────────────────────────────
    def _open_signals(self):
        if self.analysis_result:
            d = SignalsDialog(self.analysis_result, self)
            d.exec()
 
    def _open_volatility(self):
        if self.analysis_result:
            d = VolatilityDialog(self.analysis_result, self)
            d.exec()
 
    def _open_news(self):
        news = self.market_info.news if self.market_info else []
        d = NewsDialog(news, self)
        d.exec()
 
    def _open_market(self):
        ticker = self.ticker_input.text().strip().upper()
        if self.market_info:
            d = MarketDialog(self.market_info, self)
            d.exec()
        elif ticker:
            # Fetch now if not done yet
            fetcher = MarketDataFetcher()
            info = fetcher.fetch(ticker)
            self.market_info = info
            d = MarketDialog(info, self)
            d.exec()
        else:
            # Prompt for ticker
            from PySide6.QtWidgets import QInputDialog
            t, ok = QInputDialog.getText(self, "Enter Ticker", "Enter a ticker symbol to load live market data:")
            if ok and t.strip():
                self.ticker_input.setText(t.strip().upper())
                fetcher = MarketDataFetcher()
                info = fetcher.fetch(t.strip().upper())
                self.market_info = info
                d = MarketDialog(info, self)
                d.exec()
 
 
def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = TradeVueApp()
    window.show()
    sys.exit(app.exec())
 
 
if __name__ == "__main__":
    main()
