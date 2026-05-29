"""
오버레이 모듈 - 현재 상태를 화면에 표시합니다 (선택적 tkinter 오버레이).
"""

import threading
import tkinter as tk


class StatusOverlay:
    """매크로 상태를 화면에 오버레이로 표시하는 클래스."""

    def __init__(self):
        self._thread: threading.Thread | None = None
        self._root: tk.Tk | None = None
        self._label: tk.Label | None = None
        self._running = False

    def _create_window(self):
        self._root = tk.Tk()
        self._root.overrideredirect(True)
        self._root.attributes("-topmost", True)
        self._root.attributes("-alpha", 0.8)

        # 화면 왼쪽 상단에 표시
        self._root.geometry("220x50+10+10")
        self._root.configure(bg="black")

        self._label = tk.Label(
            self._root,
            text="[매크로 대기중]",
            fg="lime",
            bg="black",
            font=("Consolas", 14, "bold"),
        )
        self._label.pack(expand=True, fill="both")

        self._root.mainloop()

    def start(self):
        """오버레이를 시작합니다."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._create_window, daemon=True)
        self._thread.start()

    def update(self, text: str):
        """오버레이 텍스트를 업데이트합니다."""
        if self._root and self._label:
            try:
                self._root.after(0, lambda: self._label.config(text=text))
            except tk.TclError:
                pass

    def stop(self):
        """오버레이를 종료합니다."""
        self._running = False
        if self._root:
            try:
                self._root.after(0, self._root.destroy)
            except tk.TclError:
                pass
