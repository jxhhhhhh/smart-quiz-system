"""
Smart Quiz System - Theme / CSS Module
深色 / 浅色两套主题样式，适配长时间刷题，校园课程设计级颜值。

CSS 文件已外置到 styles/ 目录：
  - styles/common.css   公共组件样式
  - styles/sidebar.css  侧边栏样式
  - styles/dark.css     深色模式
  - styles/light.css    浅色模式
"""
import os
import streamlit as st

_STYLES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "styles")


def _read_css(filename: str) -> str:
    """读取 CSS 文件内容。"""
    filepath = os.path.join(_STYLES_DIR, filename)
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""


# 缓存已读取的 CSS
_SIDEBAR_CSS = None
_COMMON_CSS = None
_DARK_CSS = None
_LIGHT_CSS = None


def inject_theme():
    """读取 session_state 中的 theme_mode，注入对应 CSS。"""
    global _SIDEBAR_CSS, _COMMON_CSS, _DARK_CSS, _LIGHT_CSS

    if _COMMON_CSS is None:
        _SIDEBAR_CSS = _read_css("sidebar.css")
        _COMMON_CSS = _read_css("common.css")
        _DARK_CSS = _read_css("dark.css")
        _LIGHT_CSS = _read_css("light.css")

    mode = st.session_state.get("theme_mode", "light")
    theme_css = _DARK_CSS if mode == "dark" else _LIGHT_CSS
    full_css = f"<style>\n{_SIDEBAR_CSS}\n{_COMMON_CSS}\n{theme_css}\n</style>"
    st.markdown(full_css, unsafe_allow_html=True)
