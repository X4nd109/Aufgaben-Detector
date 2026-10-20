"""
Windows Dialog & DPI Scaling Utilities.

Provides crisp, high-resolution native Windows Explorer file and folder selection dialogs
with Per-Monitor DPI Awareness v2, ensuring razor-sharp rendering on 4K, 1440p, and multi-monitor setups.
"""

import logging
import os
import subprocess
import sys
from typing import Optional

logger = logging.getLogger("win_dialogs")

_NO_WINDOW_FLAG = 0x08000000 if sys.platform == "win32" else 0


def enable_high_dpi_awareness() -> bool:
    """
    Enables Per-Monitor DPI Awareness v2 for the current process on Windows 10/11.
    Falls back gracefully to Per-Monitor v1 or system-wide DPI awareness.

    Returns:
        True if any DPI awareness mode was successfully activated, False otherwise.
    """
    if sys.platform != "win32":
        return False

    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32

        # 1. Best: Per-Monitor DPI Aware v2 (Windows 10 Creators Update 1703+)
        # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
        if hasattr(user32, "SetProcessDpiAwarenessContext"):
            user32.SetProcessDpiAwarenessContext.argtypes = [wintypes.HANDLE]
            user32.SetProcessDpiAwarenessContext.restype = wintypes.BOOL
            if user32.SetProcessDpiAwarenessContext(wintypes.HANDLE(-4)):
                return True

        # 2. Fallback: Per-Monitor DPI Aware v1 (Windows 8.1+)
        # PROCESS_PER_MONITOR_DPI_AWARE = 2
        try:
            shcore = ctypes.windll.shcore
            if hasattr(shcore, "SetProcessDpiAwareness"):
                shcore.SetProcessDpiAwareness.argtypes = [ctypes.c_int]
                shcore.SetProcessDpiAwareness.restype = ctypes.c_long
                if shcore.SetProcessDpiAwareness(2) == 0:
                    return True
        except Exception:
            pass

        # 3. Fallback: System DPI Aware (Windows Vista+)
        if hasattr(user32, "SetProcessDPIAware"):
            user32.SetProcessDPIAware.restype = wintypes.BOOL
            return bool(user32.SetProcessDPIAware())

    except Exception as e:
        logger.debug(f"Could not enable DPI awareness: {e}")

    return False


def pick_file(
    dialog_title: str = "Select File",
    filter_name: str = "PDF Documents",
    filter_ext: str = "*.pdf",
    initial_dir: Optional[str] = None,
) -> Optional[str]:
    """
    Opens a native, high-resolution Windows File Open dialog (IFileOpenDialog).
    Ensures Per-Monitor DPI scaling and falls back gracefully to Tkinter or PowerShell.

    Args:
        dialog_title: Window title for the file dialog.
        filter_name: Display label for the file filter.
        filter_ext: File filter pattern, e.g. '*.pdf'.
        initial_dir: Optional starting directory path.

    Returns:
        Absolute path to the chosen file, or None if cancelled.
    """
    enable_high_dpi_awareness()

    if sys.platform == "win32":
        try:
            return _pick_file_com(
                title=dialog_title,
                filter_name=filter_name,
                filter_ext=filter_ext,
                initial_dir=initial_dir,
            )
        except Exception as e:
            logger.debug(f"Native COM file dialog failed, falling back: {e}")

    # Fallback 1: Tkinter
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        selected = filedialog.askopenfilename(
            title=dialog_title,
            initialdir=initial_dir if initial_dir and os.path.isdir(initial_dir) else None,
            filetypes=[(filter_name, filter_ext), ("All Files", "*.*")],
        )
        root.destroy()
        if selected and os.path.exists(selected):
            return os.path.abspath(selected)
        if selected == "":
            return None
    except Exception as e:
        logger.debug(f"Tkinter askopenfilename fallback failed: {e}")

    # Fallback 2: PowerShell Windows Forms
    if sys.platform == "win32":
        try:
            init_dir_arg = f"$dlg.InitialDirectory = '{initial_dir}';" if initial_dir and os.path.isdir(initial_dir) else ""
            ps_script = f"""
            [System.Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms') | Out-Null
            $dlg = New-Object System.Windows.Forms.OpenFileDialog
            $dlg.Title = '{dialog_title}'
            $dlg.Filter = '{filter_name} ({filter_ext})|{filter_ext}|All Files (*.*)|*.*'
            {init_dir_arg}
            if ($dlg.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {{
                Write-Output $dlg.FileName
            }}
            """
            res = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
                capture_output=True,
                text=True,
                creationflags=_NO_WINDOW_FLAG,
                timeout=60,
            )
            chosen = res.stdout.strip()
            if chosen and os.path.exists(chosen):
                return os.path.abspath(chosen)
        except Exception as e2:
            logger.error(f"PowerShell file selection failed: {e2}")

    return None


def pick_directory(
    dialog_title: str = "Select Folder",
    initial_dir: Optional[str] = None,
) -> Optional[str]:
    """
    Opens a native, high-resolution Windows modern folder picker dialog (IFileOpenDialog with FOS_PICKFOLDERS).
    Provides modern Explorer navigation (Quick Access, Search, Address Bar) with full DPI scaling.
    Falls back gracefully to Tkinter or PowerShell.

    Args:
        dialog_title: Window title or description for the folder picker.
        initial_dir: Optional starting directory path.

    Returns:
        Absolute path to the chosen folder, or None if cancelled.
    """
    enable_high_dpi_awareness()

    if sys.platform == "win32":
        try:
            return _pick_directory_com(title=dialog_title, initial_dir=initial_dir)
        except Exception as e:
            logger.debug(f"Native COM folder dialog failed, falling back: {e}")

    # Fallback 1: Tkinter askdirectory
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        selected = filedialog.askdirectory(
            title=dialog_title,
            initialdir=initial_dir if initial_dir and os.path.isdir(initial_dir) else None,
        )
        root.destroy()
        if selected and os.path.exists(selected):
            return os.path.abspath(selected)
        if selected == "":
            return None
    except Exception as e:
        logger.debug(f"Tkinter askdirectory fallback failed: {e}")

    # Fallback 2: PowerShell FolderBrowserDialog
    if sys.platform == "win32":
        try:
            init_dir_arg = f"$dlg.SelectedPath = '{initial_dir}';" if initial_dir and os.path.isdir(initial_dir) else ""
            ps_script = f"""
            [System.Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms') | Out-Null
            $dlg = New-Object System.Windows.Forms.FolderBrowserDialog
            $dlg.Description = '{dialog_title}'
            $dlg.ShowNewFolderButton = $false
            {init_dir_arg}
            if ($dlg.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {{
                Write-Output $dlg.SelectedPath
            }}
            """
            res = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
                capture_output=True,
                text=True,
                creationflags=_NO_WINDOW_FLAG,
                timeout=60,
            )
            chosen = res.stdout.strip()
            if chosen and os.path.exists(chosen):
                return os.path.abspath(chosen)
        except Exception as e2:
            logger.error(f"PowerShell folder picker failed: {e2}")

    return None


# ---------------------------------------------------------------------------
# Native Windows COM IFileOpenDialog Implementation
# ---------------------------------------------------------------------------

def _pick_file_com(
    title: str,
    filter_name: str,
    filter_ext: str,
    initial_dir: Optional[str] = None,
) -> Optional[str]:
    """Helper invoking IFileOpenDialog for selecting a single file."""
    return _invoke_file_open_dialog(
        title=title,
        is_folder=False,
        filter_name=filter_name,
        filter_ext=filter_ext,
        initial_dir=initial_dir,
    )


def _pick_directory_com(
    title: str,
    initial_dir: Optional[str] = None,
) -> Optional[str]:
    """Helper invoking IFileOpenDialog with FOS_PICKFOLDERS for folder selection."""
    return _invoke_file_open_dialog(
        title=title,
        is_folder=True,
        initial_dir=initial_dir,
    )


def _invoke_file_open_dialog(
    title: str,
    is_folder: bool,
    filter_name: str = "Files",
    filter_ext: str = "*.*",
    initial_dir: Optional[str] = None,
) -> Optional[str]:
    """
    Low-level wrapper around Windows COM IFileOpenDialog.
    Supports both file selection and folder selection (FOS_PICKFOLDERS).
    """
    import ctypes
    from ctypes import POINTER, Structure, WINFUNCTYPE, c_void_p, wintypes

    class GUID(Structure):
        _fields_ = [
            ("Data1", wintypes.DWORD),
            ("Data2", wintypes.WORD),
            ("Data3", wintypes.WORD),
            ("Data4", wintypes.BYTE * 8),
        ]

    class COMDLG_FILTERSPEC(Structure):
        _fields_ = [
            ("pszName", wintypes.LPCWSTR),
            ("pszSpec", wintypes.LPCWSTR),
        ]

    CLSID_FileOpenDialog = GUID(
        0xDC1C5A9C,
        0xE88A,
        0x4DDE,
        (wintypes.BYTE * 8)(0xA5, 0xA1, 0x60, 0xF8, 0x2A, 0x20, 0xAE, 0xF7),
    )
    IID_IFileOpenDialog = GUID(
        0xD57C7288,
        0xD4AD,
        0x4768,
        (wintypes.BYTE * 8)(0xBE, 0x02, 0x9D, 0x96, 0x95, 0x32, 0xD9, 0x60),
    )
    IID_IShellItem = GUID(
        0x43826D1E,
        0xE718,
        0x42EE,
        (wintypes.BYTE * 8)(0xBC, 0x55, 0xA1, 0xE2, 0x61, 0xC3, 0x7B, 0xFE),
    )

    HRESULT = ctypes.c_long
    CLSCTX_INPROC_SERVER = 1

    # Dialog options
    FOS_NOCHANGEDIR = 0x00000008
    FOS_PICKFOLDERS = 0x00000020
    FOS_FORCEFILESYSTEM = 0x00000040
    FOS_FILEMUSTEXIST = 0x00001000
    FOS_PATHMUSTEXIST = 0x00000800

    SIGDN_FILESYSPATH = 0x80058000
    ERROR_CANCELLED = 0x800704C7

    ole32 = ctypes.windll.ole32
    shell32 = ctypes.windll.shell32

    # Initialize COM on this thread
    co_init_res = ole32.CoInitialize(None)
    need_uninit = co_init_res in (0, 1)  # S_OK or S_FALSE

    p_dialog = c_void_p()
    try:
        hr = ole32.CoCreateInstance(
            ctypes.byref(CLSID_FileOpenDialog),
            None,
            CLSCTX_INPROC_SERVER,
            ctypes.byref(IID_IFileOpenDialog),
            ctypes.byref(p_dialog),
        )
        if hr != 0 or not p_dialog.value:
            raise RuntimeError(f"CoCreateInstance(IFileOpenDialog) failed with HRESULT {hex(hr & 0xFFFFFFFF)}")

        vtable = ctypes.cast(p_dialog, POINTER(POINTER(c_void_p))).contents

        # COM method definitions
        fn_Release = WINFUNCTYPE(wintypes.ULONG, c_void_p)(vtable[2])
        fn_Show = WINFUNCTYPE(HRESULT, c_void_p, wintypes.HWND)(vtable[3])
        fn_SetFileTypes = WINFUNCTYPE(HRESULT, c_void_p, wintypes.UINT, POINTER(COMDLG_FILTERSPEC))(vtable[4])
        fn_SetOptions = WINFUNCTYPE(HRESULT, c_void_p, wintypes.DWORD)(vtable[9])
        fn_GetOptions = WINFUNCTYPE(HRESULT, c_void_p, POINTER(wintypes.DWORD))(vtable[10])
        fn_SetFolder = WINFUNCTYPE(HRESULT, c_void_p, c_void_p)(vtable[12])
        fn_SetTitle = WINFUNCTYPE(HRESULT, c_void_p, wintypes.LPCWSTR)(vtable[17])
        fn_GetResult = WINFUNCTYPE(HRESULT, c_void_p, POINTER(c_void_p))(vtable[20])

        # 1. Set Title
        if title:
            fn_SetTitle(p_dialog, title)

        # 2. Configure Options
        cur_options = wintypes.DWORD()
        fn_GetOptions(p_dialog, ctypes.byref(cur_options))
        opts = cur_options.value | FOS_FORCEFILESYSTEM | FOS_NOCHANGEDIR

        if is_folder:
            opts |= FOS_PICKFOLDERS
        else:
            opts |= FOS_FILEMUSTEXIST | FOS_PATHMUSTEXIST

        fn_SetOptions(p_dialog, opts)

        # 3. File filters (only for file mode)
        if not is_folder and filter_name and filter_ext:
            specs = (COMDLG_FILTERSPEC * 2)(
                COMDLG_FILTERSPEC(f"{filter_name} ({filter_ext})", filter_ext),
                COMDLG_FILTERSPEC("All Files (*.*)", "*.*"),
            )
            fn_SetFileTypes(p_dialog, 2, specs)

        # 4. Initial directory (optional)
        p_initial_folder = c_void_p()
        if initial_dir and os.path.isdir(initial_dir):
            try:
                norm_dir = os.path.abspath(initial_dir)
                hr_folder = shell32.SHCreateItemFromParsingName(
                    wintypes.LPCWSTR(norm_dir),
                    None,
                    ctypes.byref(IID_IShellItem),
                    ctypes.byref(p_initial_folder),
                )
                if hr_folder == 0 and p_initial_folder.value:
                    fn_SetFolder(p_dialog, p_initial_folder)
            except Exception:
                pass

        # 5. Show Dialog (modal)
        # Using NULL hwndOwner centers the dialog on the active monitor
        show_hr = fn_Show(p_dialog, None)

        # Clean up initial folder item if allocated
        if p_initial_folder.value:
            init_vtable = ctypes.cast(p_initial_folder, POINTER(POINTER(c_void_p))).contents
            init_Release = WINFUNCTYPE(wintypes.ULONG, c_void_p)(init_vtable[2])
            init_Release(p_initial_folder)

        # Check result
        if (show_hr & 0xFFFFFFFF) == ERROR_CANCELLED:
            return None  # User clicked cancel or closed window
        if show_hr != 0:
            raise RuntimeError(f"IFileOpenDialog.Show failed with HRESULT {hex(show_hr & 0xFFFFFFFF)}")

        # 6. Extract Result IShellItem
        p_result_item = c_void_p()
        hr_result = fn_GetResult(p_dialog, ctypes.byref(p_result_item))
        if hr_result != 0 or not p_result_item.value:
            return None

        p_display_name = wintypes.LPWSTR()
        try:
            item_vtable = ctypes.cast(p_result_item, POINTER(POINTER(c_void_p))).contents
            fn_GetDisplayName = WINFUNCTYPE(
                HRESULT, c_void_p, wintypes.DWORD, POINTER(wintypes.LPWSTR)
            )(item_vtable[5])
            fn_ItemRelease = WINFUNCTYPE(wintypes.ULONG, c_void_p)(item_vtable[2])

            hr_name = fn_GetDisplayName(p_result_item, SIGDN_FILESYSPATH, ctypes.byref(p_display_name))
            if hr_name == 0 and p_display_name.value:
                chosen_path = str(p_display_name.value)
                if os.path.exists(chosen_path):
                    return os.path.abspath(chosen_path)
        finally:
            if p_display_name.value:
                ole32.CoTaskMemFree(p_display_name)
            if p_result_item.value:
                fn_ItemRelease(p_result_item)

    finally:
        if p_dialog.value:
            fn_Release(p_dialog)
        if need_uninit:
            ole32.CoUninitialize()

    return None
