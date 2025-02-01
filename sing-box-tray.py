import os
import sys
import shutil
import pathlib
import json
import subprocess
from threading import Thread
from typing import Callable

from pystray import Icon, Menu, MenuItem
from PIL import Image
import keyboard


class SingBox:
    def __init__(
        self,
        core_path: str,
        config_path: str,
        workdir: str
    ):
        self.proc = None
        self.core_path = core_path
        self.config_path = config_path
        self.workdir = workdir

    # To not show the window on Windows
    if os.name == 'nt':
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    else:
        si = None

    def start(self) -> int | None:
        self.proc = subprocess.Popen(
            [self.core_path, 'run', '-c', self.config_path, '-D', self.workdir],
            stdin=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            startupinfo=self.si
        )
        return self.proc.poll()

    def stop(self) -> int | None:
        if self.proc:
            self.proc.terminate()
            self.proc.wait()
            return self.proc.returncode
        return 0


class TrayIcon:
    def __init__(
        self,
        on_toggle: Callable,
        on_exit: Callable,
        icon_on: Image.Image,
        icon_off: Image.Image,
        keybind: str,
        clash_url: str | None,
        sb_workdir: str,
        sbt_config_path: str,
    ):
        keybind = '+'.join([i.capitalize() for i in keybind.split('+')]) if keybind else None

        self._sb_running = False
        self.icon_on = icon_on
        self.icon_off = icon_off
        self.icon = Icon(
            'sing-box',
            icon=icon_off,
            title='sing-box [Off]',
            menu=Menu(
                MenuItem(f'Toggle\t{keybind}', on_toggle, checked=lambda _: self._sb_running, default=True, ),
                Menu.SEPARATOR,
                MenuItem('Open clash dashboard', lambda: open_path(clash_url), visible=bool(clash_url)),
                MenuItem('Open working directory', lambda: open_path(sb_workdir)),
                MenuItem('Open sing-box-tray settings', lambda: open_path(sbt_config_path)),
                Menu.SEPARATOR,
                MenuItem('Exit', on_exit)
            )
        )

    def start(self):
        self.icon.run()

    def stop(self):
        self.icon.stop()

    def toggle(self):
        if self._sb_running:
            self.icon.icon = self.icon_off
            self.icon.title = 'sing-box [Off]'
        else:
            self.icon.icon = self.icon_on
            self.icon.title = 'sing-box [On]'
        self._sb_running = not self._sb_running
        self.icon.update_menu()


class Keyboard:
    def __init__(
        self,
        keybind: str,
        on_press: Callable
    ):
        self.running = False
        self.lock = None
        self.callback = on_press
        keyboard.add_hotkey(keybind, lambda: self.lock.set())

    def start(self):
        self.running = True
        # Part of keyboard.wait()
        while self.running:
            self.lock = keyboard._Event()
            self.lock.wait()
            self.callback()

    def stop(self):
        self.running = False
        if self.lock:
            self.lock.set()


class SingBoxTray:
    def __init__(
        self,
        sbt_config_path: str,
        sb_path: str,
        sb_config_path: str,
        sb_workdir: str,
        clash_url: str | None,
        icon_on: Image.Image,
        icon_off: Image.Image,
        keybind: str | None
    ):
        self.sb_running = False

        self.sb = SingBox(sb_path, sb_config_path, sb_workdir)
        self.icon = TrayIcon(self._toggle, self.stop, icon_on, icon_off, keybind, clash_url, sb_workdir,
                             sbt_config_path)
        self.kb = Keyboard(keybind, self._toggle) if keybind else None

    def start(self):
        if self.kb:
            Thread(target=self.icon.start).start()
            self.kb.start()
        else:
            self.icon.start()

    def stop(self):
        code = self.sb.stop()
        if code is None:
            self.icon.icon.notify('sing-box wasn\'t turned off', 'Error')
            return
        self.icon.stop()
        if self.kb:
            self.kb.stop()

    def _toggle(self):
        if self.sb_running:
            code = self.sb.stop()
            if code is None:
                self.icon.icon.notify('sing-box wasn\'t turned off', 'Error')
                return
        else:
            code = self.sb.start()
            if code is not None:
                self.icon.icon.notify('sing-box wasn\'t turned on', 'Error')
                return
        self.icon.toggle()
        self.sb_running = not self.sb_running


def adjust_icon(img: Image.Image, rgba: list[int]) -> Image.Image:
    r, g, b, a = img.split()

    r = r.point(lambda i: i + rgba[0])
    g = g.point(lambda i: i + rgba[1])
    b = b.point(lambda i: i + rgba[2])
    a = a.point(lambda i: i + 38 + rgba[3] if i != 0 else i)

    return Image.merge("RGBA", (r, g, b, a))

def open_path(path: str) -> None:
    if os.name == 'nt':
        os.startfile(path)
    else:
        subprocess.run(['open', path])

if __name__ == '__main__':
    # Workdir
    file_dir = pathlib.Path(__file__).parent.resolve()
    if getattr(sys, 'frozen', False):  # If bundled with pyinstaller
        workdir = pathlib.Path(sys.executable).parent.resolve()
    else:
        workdir = file_dir

    # Config
    try:
        with open(workdir.joinpath('sb_tray_config.json'), 'r') as file:
            cfg = json.load(file)
    except FileNotFoundError:
        shutil.copy(file_dir.joinpath('sb_tray_config.dist.json'), workdir.joinpath('sb_tray_config.json'))
        raise FileNotFoundError(
            f'Configuration file ({workdir.joinpath("sb_tray_config.json")}) was created. Check it and then run the '
            'program again.'
        )

    if not cfg['sing_box_path']:
        cfg['sing_box_path'] = 'sing-box'
    if not cfg['sing_box_config_path']:
        cfg['sing_box_config_path'] = workdir.joinpath('config.json')
    if not cfg['sing_box_workdir']:
        sb_workdir_path = workdir.joinpath('sb_workdir')
        cfg['sing_box_workdir'] = sb_workdir_path
        if not os.path.exists(sb_workdir_path):
            os.mkdir(sb_workdir_path)

    icon_base = Image.open(file_dir.joinpath('icon_base.png'))
    sb_tray = SingBoxTray(
        workdir.joinpath('sb_tray_config.json'),
        cfg['sing_box_path'],
        cfg['sing_box_config_path'],
        cfg['sing_box_workdir'],
        cfg['clash_dashboard_url'],
        adjust_icon(icon_base, cfg['icon_on_rgba']),
        adjust_icon(icon_base, cfg['icon_off_rgba']),
        cfg['keybind']
    )
    sb_tray.start()