import ctypes
import json
import subprocess
from threading import Thread
import pathlib
import sys

from pystray import Icon, Menu, MenuItem
from PIL import Image
import keyboard


class SingBoxTray:
    def __init__(
        self,
        sb_path: str,
        sb_config_path: str,
        workdir: str,
        clash_url: str,
        icon_on: Image.Image,
        icon_off: Image.Image,
        keybind: str
    ):
        self.sb_path = sb_path
        self.sb_config_path = sb_config_path
        self.workdir = workdir
        self.clash_url = clash_url
        self.icon_on = icon_on
        self.icon_off = icon_off
        self.keybind = keybind

        self.exited = False
        self.running = False
        self.icon = Icon(
            'sing-box',
            icon=icon_off,
            title='sing-box [Off]',
            menu=Menu(
                MenuItem('Toggle', self._toggle, checked=lambda _: self.running, default=True),
                MenuItem('Open clash dashboard', lambda: subprocess.run(['start', clash_url], shell=True)),
                MenuItem('Open working directory', lambda: subprocess.run(['start', workdir], shell=True)),
                MenuItem('Exit', self.close)
            )
        )

    def start_icon(self):
        Thread(target=self.icon.run).start()

    # To not show the window
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    def start_sb(self):
        self.proc = subprocess.Popen(
            [self.sb_path, 'run', '-c', self.sb_config_path, '-D', self.workdir],
            stdin=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            startupinfo=self.si
        )

    def wait_kb(self):
        # Part of keyboard.wait()
        while True:
            self.kb_lock = keyboard._Event()
            remove = keyboard.add_hotkey(self.keybind, lambda: self.kb_lock.set())
            self.kb_lock.wait()
            if self.exited:
                break
            keyboard.remove_hotkey(remove)
            self._toggle()

    def start(self):
        self.start_icon()
        self.wait_kb()

    def close(self):
        if hasattr(self, 'proc'):
            self.proc.terminate()
            self.proc.wait()
            if self.proc.returncode is None:
                self.icon.notify('sing-box wasn\'t turned off', 'Error')
                return
        self.icon.stop()
        self.exited = True
        if hasattr(self, 'kb_lock'):
            self.kb_lock.set()

    def _toggle(self):
        if self.running:
            self.proc.terminate()
            self.proc.wait()
            if self.proc.returncode is None:
                self.icon.notify('sing-box wasn\'t turned off', 'Error')
                return
            self.icon.title = 'sing-box [Off]'
            self.icon.icon = self.icon_off
        else:
            self.start_sb()
            if self.proc.poll() is not None:
                self.icon.notify('sing-box wasn\'t turned on', 'Error')
                return
            self.icon.title = 'sing-box [On]'
            self.icon.icon = self.icon_on
        self.running = not self.running

def adjust_icon(img: Image.Image, rgba: list[int]) -> Image.Image:
    r, g, b, a = img.split()

    r = r.point(lambda i: i + rgba[0])
    g = g.point(lambda i: i + rgba[1])
    b = b.point(lambda i: i + rgba[2])
    a = a.point(lambda i: i + 38 + rgba[3] if i != 0 else i)

    return Image.merge("RGBA", (r, g, b, a))

if __name__ == '__main__':

    # Admin check
    if not ctypes.windll.shell32.IsUserAnAdmin():
        raise PermissionError('Run the program with administrator privileges')

    if getattr(sys, 'frozen', False):
        workdir = pathlib.Path(sys.executable).parent.resolve()
    else:
        workdir = pathlib.Path(__file__).parent.resolve()

    with open(workdir.joinpath('sb_tray_config.json'), 'r') as file:
        cfg = json.load(file)

    icon = Image.open(pathlib.Path(__file__).parent.joinpath('icon_base.png'))
    sb_tray = SingBoxTray(
        cfg['sing_box_path'],
        cfg['sing_box_config_path'],
        cfg['sing_box_workdir'],
        cfg['clash_dashboard_url'],
        adjust_icon(icon, cfg['icon_on_rgba']),
        adjust_icon(icon, cfg['icon_off_rgba']),
        cfg['keybind']
    )
    sb_tray.start()