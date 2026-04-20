"""CapCut automation control, mainly related to automatic export"""

import time
import shutil
import sys

# Platform check and dependency import
if sys.platform != "win32":
    raise ImportError("JianyingController is only available on Windows platform")

try:
    import uiautomation as uia
except ImportError as e:
    raise ImportError(f"Missing required Windows dependencies: {e}. Please install with: pip install capcut-mate[windows]")

try:
    import pyautogui  # pyright: ignore[reportMissingModuleSource]
except ImportError as e:
    raise ImportError(f"Missing required Windows dependencies: {e}. Please install with: pip install pyautogui[windows]")

from enum import Enum
from typing import Optional, Literal, Callable

from . import exceptions
from .exceptions import AutomationError

# Add logger import
from src.utils.logger import logger

class ExportResolution(Enum):
    """Export resolution"""
    RES_8K = "8K"
    RES_4K = "4K"
    RES_2K = "2K"
    RES_1080P = "1080P"
    RES_720P = "720P"
    RES_480P = "480P"

class ExportFramerate(Enum):
    """Export frame rate"""
    FR_24 = "24fps"
    FR_25 = "25fps"
    FR_30 = "30fps"
    FR_50 = "50fps"
    FR_60 = "60fps"

class ControlFinder:
    """Control finder, encapsulates logic for finding UI controls"""

    @staticmethod
    def desc_matcher(target_desc: str, depth: int = 2, exact: bool = False) -> Callable[[uia.Control, int], bool]:
        """Matcher for finding controls by full_description"""
        target_desc = target_desc.lower()
        def matcher(control: uia.Control, _depth: int) -> bool:
            if _depth != depth:
                return False
            full_desc: str = control.GetPropertyValue(30159).lower()
            return (target_desc == full_desc) if exact else (target_desc in full_desc)
        return matcher

    @staticmethod
    def class_name_matcher(class_name: str, depth: int = 1, exact: bool = False) -> Callable[[uia.Control, int], bool]:
        """Matcher for finding controls by ClassName"""
        class_name = class_name.lower()
        def matcher(control: uia.Control, _depth: int) -> bool:
            if _depth != depth:
                return False
            curr_class_name: str = control.ClassName.lower()
            return (class_name == curr_class_name) if exact else (class_name in curr_class_name)
        return matcher

class JianyingController:
    """CapCut controller"""

    app: uia.WindowControl
    """CapCut window"""
    app_status: Literal["home", "edit", "pre_export"]
    """When app_status is pre_export, app_sub_status indicates the sub-status during export process"""
    app_sub_status: Literal["none", "export_start", "exporting", "export_succeed"]

    def __init__(self):
        """Initialize CapCut controller, CapCut should be at the home page"""
        self.get_window()

    def find_and_click_draft(self, draft_name: str, max_retries: int = 5, retry_interval: float = 5.0) -> None:
        """Find and click specified draft
        
        Args:
            draft_name (str): Draft name to find
            max_retries (int): Maximum retry count, default 5
            retry_interval (float): Retry interval (seconds), default 5
            
        Raises:
            DraftNotFound: Draft not found
        """
        last_exception = None
        for attempt in range(max_retries):
            try:
                # Click corresponding draft
                draft_name_text = self.app.TextControl(
                    searchDepth=2,
                    Compare=ControlFinder.desc_matcher(f"HomePageDraftTitle:{draft_name}", exact=True)
                )
                if not draft_name_text.Exists(0):
                    raise exceptions.DraftNotFound(f"CapCut draft named {draft_name} not found")
                draft_btn = draft_name_text.GetParentControl()
                assert draft_btn is not None
                draft_btn.Click(simulateMove=False)
                time.sleep(10)
                self.get_window()
                return  # Success
            except exceptions.DraftNotFound as e:
                last_exception = e
                if attempt < max_retries - 1:
                    logger.info(f"CapCut draft named {draft_name} not found, retrying {attempt + 1}...")
                    time.sleep(retry_interval)
        
        # All retries failed
        raise last_exception

    def click_export_button(self) -> None:
        """Click export button in edit page
        
        Raises:
            AutomationError: Export button not found
        """
        export_btn = self.app.TextControl(searchDepth=2, Compare=ControlFinder.desc_matcher("MainWindowTitleBarExportBtn"))
        if not export_btn.Exists(0):
            raise AutomationError("Export button not found in edit window")
        export_btn.Click(simulateMove=False)
        time.sleep(10)
        self.get_window()

    def get_original_export_path(self) -> str:
        """Get original export path
        
        Returns:
            str: Original export path
            
        Raises:
            AutomationError: Export path box not found
        """
        # Get original export path (with extension)
        export_path_sib = self.app.TextControl(searchDepth=2, Compare=ControlFinder.desc_matcher("ExportPath"))
        if not export_path_sib.Exists(0):
            raise AutomationError("Export path box not found")
        export_path_text = export_path_sib.GetSiblingControl(lambda ctrl: True)
        assert export_path_text is not None
        export_path = export_path_text.GetPropertyValue(30159)
        return export_path

    def set_export_resolution(self, resolution: Optional[ExportResolution]) -> None:
        """Set export resolution
        
        Args:
            resolution (Optional[ExportResolution]): Export resolution, None for no change
            
        Raises:
            AutomationError: Required controls not found
        """
        if resolution is not None:
            setting_group = self.app.GroupControl(searchDepth=1,
                                          Compare=ControlFinder.class_name_matcher("PanelSettingsGroup_QMLTYPE"))
            if not setting_group.Exists(0):
                raise AutomationError("Export setting group not found")
            resolution_btn = setting_group.TextControl(searchDepth=2, Compare=ControlFinder.desc_matcher("ExportSharpnessInput"))
            if not resolution_btn.Exists(0.5):
                raise AutomationError("Export resolution dropdown not found")
            resolution_btn.Click(simulateMove=False)
            time.sleep(0.5)
            resolution_item = self.app.TextControl(
                searchDepth=2, Compare=ControlFinder.desc_matcher(resolution.value)
            )
            if not resolution_item.Exists(0.5):
                raise AutomationError(f"Resolution option {resolution.value} not found")
            resolution_item.Click(simulateMove=False)
            time.sleep(0.5)

    def set_export_framerate(self, framerate: Optional[ExportFramerate]) -> None:
        """Set export frame rate
        
        Args:
            framerate (Optional[ExportFramerate]): Export frame rate, None for no change
            
        Raises:
            AutomationError: Required controls not found
        """
        if framerate is not None:
            setting_group = self.app.GroupControl(searchDepth=1,
                                          Compare=ControlFinder.class_name_matcher("PanelSettingsGroup_QMLTYPE"))
            if not setting_group.Exists(0):
                raise AutomationError("Export setting group not found")
            framerate_btn = setting_group.TextControl(searchDepth=2, Compare=ControlFinder.desc_matcher("FrameRateInput"))
            if not framerate_btn.Exists(0.5):
                raise AutomationError("Export frame rate dropdown not found")
            framerate_btn.Click(simulateMove=False)
            time.sleep(0.5)
            framerate_item = self.app.TextControl(
                searchDepth=2, Compare=ControlFinder.desc_matcher(framerate.value)
            )
            if not framerate_item.Exists(0.5):
                raise AutomationError(f"Frame rate option {framerate.value} not found")
            framerate_item.Click(simulateMove=False)
            time.sleep(0.5)

    def click_final_export_button(self) -> None:
        """Click final export button in export window
        
        Raises:
            AutomationError: Export button not found
        """
        export_btn = self.app.TextControl(searchDepth=2, Compare=ControlFinder.desc_matcher("ExportOkBtn", exact=True))
        if not export_btn.Exists(0):
            raise AutomationError("Export button not found in export window")
        export_btn.Click(simulateMove=False)
        time.sleep(5)

    def __ensure_window_focus(self) -> None:
        """Ensure window focus before clicking"""
        # 1. Ensure window activation
        self.app.SetActive()
        time.sleep(1)
        
        # 2. Ensure window is on top
        self.app.SetTopmost()
        time.sleep(1)
        
        # 3. Force focus
        try:
            self.app.SetFocus()
        except:
            pass  # May fail in some cases, but continue
        time.sleep(1)

    def wait_for_export_completion(self, timeout: float) -> None:
        """Wait for export completion
        
        Args:
            timeout (float): Timeout (seconds)
            
        Raises:
            AutomationError: Export timeout
        """
        # Click count for 'Continue Export' button
        continue_export_click_count = 0
        
        # Wait for completion
        st = time.time()
        while True:
            self.get_window()
            if self.app_status != "pre_export": break

            succeed_close_btn = self.app.TextControl(searchDepth=2, Compare=ControlFinder.desc_matcher("ExportSucceedCloseBtn"))
            if succeed_close_btn.Exists(0):
                break

            if time.time() - st > timeout:
                raise AutomationError("Export timeout, limit is %d seconds" % timeout)

            # During export, if an exception popup appears, click 'Continue Export' button
            if continue_export_click_count < 20:
                print("pyautogui.size(): ", pyautogui.size(), ", click index: ", continue_export_click_count)
                pyautogui.click(x=996, y=597, button="left")
                continue_export_click_count += 1

            time.sleep(1)
        time.sleep(2)

    def return_to_home(self) -> None:
        """Return to home page with delay"""
        self.get_window()
        self.switch_to_home()
        time.sleep(2)

    def move_exported_file(self, original_path: str, output_path: Optional[str]) -> None:
        """Move exported file to specified location
        
        Args:
            original_path (str): Original export path
            output_path (Optional[str]): Target output path, None for no movement
        """
        logger.info(f"move {original_path} to {output_path}")
        if output_path is not None:
            shutil.move(original_path, output_path)

    def export_draft(self, draft_name: str, output_path: Optional[str] = None, *,
                     resolution: Optional[ExportResolution] = None,
                     framerate: Optional[ExportFramerate] = None,
                     timeout: float = 1200) -> None:
        """Export specified CapCut draft, **currently only supports version 6 and below**

        **Note: Ensure you have permission to export (no VIP features or VIP subscription), 
        otherwise it may fall into an infinite loop.**

        Args:
            draft_name (`str`): Draft name to export
            output_path (`str`, optional): Export path (folder or file), uses default if None.
            resolution (`ExportResolution`, optional): Export resolution, default is no change.
            framerate (`ExportFramerate`, optional): Export frame rate, default is no change.
            timeout (`float`, optional): Timeout (seconds), default 20 minutes.

        Raises:
            `DraftNotFound`: Draft not found
            `AutomationError`: Operation failed
        """
        logger.info(f"start export {draft_name} to {output_path}")

        # Initial preparation
        self.get_window()
        self.switch_to_home()

        original_path = None

        for i in range(16):
            # Ensure window focus
            self.__ensure_window_focus()
            if self.app_status == "home":
                logger.info("[%d]app is already in home page", i)
                self.find_and_click_draft(draft_name)
            elif self.app_status == "edit":
                logger.info("[%d]app is already in edit page", i)
                # Click export button to enter export interface
                self.click_export_button()
            elif self.app_status == "pre_export":                
                if self.app_sub_status == "export_start":
                    logger.info("[%d]app is already in pre_export[export_start] page", i)
                    # Get original export path
                    original_path = self.get_original_export_path()
                    # Set resolution (if specified)
                    self.set_export_resolution(resolution)                    
                    # Set frame rate (if specified)
                    self.set_export_framerate(framerate)                    
                    # Click final export button
                    self.click_final_export_button()
                    # Get window status
                    self.get_window()
                elif self.app_sub_status == "exporting":
                    logger.info("[%d]app is already in pre_export[exporting] page", i)
                    self.wait_for_export_completion(timeout)                    
                elif self.app_sub_status == "export_succeed":
                    logger.info("[%d]app is already in pre_export[export_succeed] page", i)
                    self.return_to_home()
                    break
                else:
                    raise AutomationError("[%d]app is in unknown sub-status: %s" % (i, self.app_sub_status))
            else:
                raise AutomationError("[%d]app is in unknown status: %s" % (i, self.app_status))
        
        # Move exported file (if specified)
        self.move_exported_file(original_path, output_path)
        
        logger.info(f"export {draft_name} to {output_path} completed")

    def switch_to_home(self) -> None:
        """Switch to CapCut home page"""
        for i in range(8):
            if self.app_status == "home":
                return
            elif self.app_status == "pre_export":
                if self.app_sub_status == "export_succeed":
                    succeed_close_btn = self.app.TextControl(searchDepth=2, Compare=ControlFinder.desc_matcher("ExportSucceedCloseBtn"))
                    if succeed_close_btn.Exists(0):
                        succeed_close_btn.Click(simulateMove=False)
                        time.sleep(2)
                        self.get_window()
            elif self.app_status == "edit":
                close_btn = self.app.GroupControl(searchDepth=1, ClassName="TitleBarButton", foundIndex=3)
                close_btn.Click(simulateMove=False)
                time.sleep(2)
                self.get_window()
            else:
                raise AutomationError("invalid app status: %s" % self.app_status)
        
        logger.info("can not switch to home page after 32 attempts")

    def get_window(self) -> None:
        """Find CapCut window and bring to top"""
        if hasattr(self, "app") and self.app.Exists(0):
            self.app.SetTopmost(False)

        self.app = uia.WindowControl(searchDepth=1, Compare=self.__jianying_window_cmp)
        if not self.app.Exists(0):
            raise AutomationError("CapCut window not found")

        # Find potential export window
        export_window = self.app.WindowControl(searchDepth=1, Name="导出") # "Export"
        if export_window.Exists(0):
            self.app = export_window
            self.app_status = "pre_export"

        # Initialize export sub-status
        self.init_export_sub_status()

        logger.info("app_status: %s, app_sub_status: %s", self.app_status, self.app_sub_status)

        self.app.SetActive()
        self.app.SetTopmost()

    # Initialize export sub-status
    def init_export_sub_status(self) -> None:
        if self.app_status == "pre_export":
            # 0. Default to exporting
            self.app_sub_status = "exporting"
            
            # 1. Check if on export start page
            export_ok_btn = self.app.TextControl(searchDepth=2, Compare=ControlFinder.desc_matcher("ExportOkBtn", exact=True))
            if export_ok_btn.Exists(0):
                self.app_sub_status = "export_start"
                return

            # 2. Check if on export success page
            succeed_close_btn = self.app.TextControl(searchDepth=2, Compare=ControlFinder.desc_matcher("ExportSucceedCloseBtn"))
            if succeed_close_btn.Exists(0):
                self.app_sub_status = "export_succeed"
                return
        else:
            self.app_sub_status = "none"

    def __jianying_window_cmp(self, control: uia.WindowControl, depth: int) -> bool:
        if control.Name != "剪映专业版": # "Jianying Pro"
            return False
        if "HomePage".lower() in control.ClassName.lower():
            self.app_status = "home"
            return True
        if "MainWindow".lower() in control.ClassName.lower():
            self.app_status = "edit"
            return True

        logger.info(f"ClassName: {control.ClassName.lower()}, Name: {control.Name.lower()}")
        return False