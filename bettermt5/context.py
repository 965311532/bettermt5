from typing import Union, Optional
from pathlib import Path

import shutil
import subprocess
import time
import logging
import sys

from .errors import MT5Error
from .templates.dynamic.config import CFG_TEMPLATE

import MetaTrader5 as _mt5

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

parent_path = Path(__file__).parent.absolute()


def normalize_path(
    path: Union[None, str, Path], parent: Union[str, Path], target: str
) -> str:
    """Takes a possible full path, partial path or None and
    turns it into the desired format."""
    parent = Path(parent)
    if path is None:
        return f"{str(parent.absolute())}{target}"
    else:
        path = Path(path)
        if path.is_dir():
            return f"{str(path.absolute())}{target}"
        else:
            return str(path.absolute())


class Connection:
    def __init__(
        self,
        path: Union[Path, str, None] = None,
        config_path: Optional[str] = None,
        terminal_config_path: Optional[str] = None,
        config_template: str = CFG_TEMPLATE,
        login: Union[str, int, None] = None,
        server: Optional[str] = None,
        password: Optional[str] = None,
        auto_trading_enabled: bool = False,
        real_trading_enabled: bool = False,
        quiet: bool = False,
        max_bars: int = 1000,
        timeout: int = 10,
    ) -> None:
        """The context manager for the MetaTrader5 terminal connection

        Parameters:
            path: Path to terminal
            config_path: Path to custom config file to start the terminal
            terminal_config_path: Path to custom terminal configuration file
            config_template: Str where parameters are specified using the prefix
                "$" and according to this: www.metatrader5.com/en/terminal/help/start_advanced/start#configuration_file
            login: Account login number
            server: Server name
            password: Account password
            portable: Whether to store the terminal data locally
            auto_trading_enabled: Enable Auto-Trading feature in terminal
            real_trading_enabled: If this is false and the Account type
                is REAL, it will raise an Exception
            quiet: Whether to display the terminal GUI
            max_bars: Number of candles loaded in chart
            timeout: Connection initialisation timeout

        Returns:
            None"""

        path = Path(path)

        if path.is_dir():
            try:
                path = next(path.glob("**/terminal64.exe"))
            except StopIteration:
                raise MT5Error("Invalid path to terminal")
        if not path.exists() or "terminal64" not in str(path):
            raise MT5Error("Invalid path to terminal")

        self.path = str(path.absolute())
        self.config_path = normalize_path(
            path=config_path, parent=path.parent, target="\\config\\config.ini"
        )
        self.terminal_config_path = normalize_path(
            path=terminal_config_path,
            parent=path.parent,
            target="\\config\\terminal.ini",
        )
        self.config_template = config_template
        self.login = login
        self.server = server
        self.password = password
        self.auto_trading_enabled = auto_trading_enabled
        self.real_trading_enabled = real_trading_enabled
        self.quiet = quiet
        self.max_bars = max_bars
        self.timeout = timeout

    def _make_config_ini(self) -> None:
        """Makes config.ini file from template and puts it in the
        terminal/config folder"""

        sub = dict(
            login=self.login,
            server=self.server,
            password=self.password,
            autotrading=int(self.auto_trading_enabled),
            maxbars=self.max_bars,
        )

        Path.mkdir(Path(self.config_path).parent, exist_ok=True)
        lines = self.config_template.splitlines()
        with open(self.config_path, "w") as f:
            for line in lines:
                if "$" in line:
                    words = line.split("=")
                    # Should be split in two
                    if words[1][0] == "$":
                        value = sub[words[1][1:]]
                        if value is not None:
                            words[1] = str(value)
                            f.write("=".join(words) + "\n")
                else:
                    f.write(line + "\n")
        log.debug(f"Created {self.config_path}")
        for key in sub:
            log.debug(f"MT5 config {key} = {sub[key]}")

    def _make_terminal_quiet(self):
        # Makes the folder if it's not there
        Path.mkdir(Path(self.config_path).parent, exist_ok=True)

        static_path = str(parent_path) + "\\templates\\static"
        terminal_quiet_ini = static_path + "\\terminal_quiet.ini"
        self.terminal_backup_ini = static_path + "\\terminal_backup.ini"

        # Move the terminal.ini file to the static template folder for later
        shutil.move(
            self.terminal_config_path,
            self.terminal_backup_ini,
            copy_function=shutil.copyfile,
        )

        # Copy the quiet template to MT5 config folder
        shutil.copyfile(terminal_quiet_ini, self.terminal_config_path)
        log.info("MT5 terminal has been shushed")

    def _restore_terminal_ini(self):
        # Move the terminal_origin.ini file from before to MT5 config folder
        shutil.move(
            self.terminal_backup_ini,
            self.terminal_config_path,
            copy_function=shutil.copyfile,
        )
        log.info("MT5 terminal settings have been restored")

    def _reset_terminal_ini(self):
        """Copy the terminal_default.ini file to Mt5 config folder"""
        default = str(parent_path) + "\\templates\\static\\terminal_default.ini"
        shutil.copyfile(default, self.terminal_config_path)

        log.info("MT5 terminal settings have been reset")

    def _check_real_trading_setting(self):
        if not self.real_trading_enabled:
            err_msg = None
            if self.account_info.trade_mode == _mt5.ACCOUNT_TRADE_MODE_REAL:
                err_msg = "Real trading was not enabled in context manager"
            # Detects possible Prop Firm Challenge accounts
            elif (
                self.account_info.trade_mode == _mt5.ACCOUNT_TRADE_MODE_DEMO
                and "challenge" in self.account_info.name.lower()
                and "demo" not in self.account_info.name.lower()
            ):
                err_msg = (
                    "This is probably a Prop Firm Challenge Account and "
                    "real trading was not enabled in the context manager."
                    "To get rid of this error, set real_trading_enabled=True "
                    "in the context manager parameters."
                )

            if err_msg is not None:
                raise MT5Error(err_msg)

    def _check_credentials(self, timeout=None):
        """Checks if the terminal is running and the credentials are correct"""
        if timeout is None:
            timeout = self.timeout

        for _ in range(timeout):
            if (
                self.account_info.login == self.login
                and self.account_info.server == self.server
            ):
                return None
            time.sleep(1)

        log.error("MT5 login or server is not correct")
        log.error("MT5 login: %s", self.account_info.login)
        log.error("MT5 server: %s", self.account_info.server)
        log.error("MT5 last_error: %s", _mt5.last_error())
        raise MT5Error(
            (
                "Account information doesn't match what was provided in "
                "the context manager. (The problem might be that other "
                "terminal instances are open.)"
            )
        )

    def __enter__(self):
        """Starts the terminal MANUALLY by calling the terminal executable
        with the parameter /config in order to specify how we want to terminal
        to start up, then we call mt5.initialize to let it automatically bind to
        the instantiated terminal."""

        # Creates the configuration file
        self._make_config_ini()

        if self.quiet:
            self._make_terminal_quiet()
        else:
            self._reset_terminal_ini()

        args = [self.path, "/portable", "/config:", self.config_path]
        log.debug("Starting terminal")
        for arg in args:
            log.debug("Args: %s", arg)

        # This call will make the terminal lose focus because terminal64.exe
        # will briefly open metaeditor64.exe to compile some files. The
        # issue is that I have no control over the metaeditor executable,
        # so even if I can keep terminal64 from getting focus, it will change
        # because of its child. This is very annoying but for now I'll leave it
        # at that. It's a nuisance but it only happens when the ctx is instantiated.
        self.process = subprocess.Popen(args)
        log.info(f"Started MT5 terminal with pid {self.process.pid}")

        time.sleep(2)  # Could be done better but it works

        log.debug(f"Inializing MT5 pipeline ...")
        initialized = _mt5.initialize(path=self.path, portable=True)
        log.info("Connection with MT5 terminal successful")

        self.account_info = _mt5.account_info()
        self.terminal_info = _mt5.terminal_info()

        # Raises an error if it's a real account and real trading is not enabled
        try:
            self._check_real_trading_setting()
            self._check_credentials()
        except MT5Error as e:
            self.__exit__(*sys.exc_info())
            raise e

    def __exit__(self, exc_type, exc_value, traceback):

        log.debug(f"Shutting down MT5 pipeline ...")
        shutdown = _mt5.shutdown()
        log.info("Disconnection from MT5 terminal successful")

        self.process.terminate()
        while self.process.poll() is None:
            log.debug(f"Closing MT5 terminal with pid {self.process.pid} ...")
            time.sleep(0.5)
        log.info("MT5 terminal shutdown successful")

        # Resets the gui setting
        if self.quiet:
            self._restore_terminal_ini()

        # Deletes the config file (contains sensitive info)
        Path(self.config_path).unlink(missing_ok=True)
        log.debug(f"Removed {self.config_path}")
