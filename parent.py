"""parent.py - parent frame class"""

import os

import wx
from wx import aui

import html
import menu
import panes
import parallel
import toolbar
from globals import *

_ = wx.GetTranslation


class MainFrame(wx.Frame):
    def __init__(self, app):
        display_size = wx.GetDisplaySize()
        best_size = (int(display_size[0] * 0.8), int(display_size[1] * 0.8))
        pos = map(int, app.config.Read("Main/WindowPosition", "-1,-1").
            split(","))
        size = map(int, app.config.Read("Main/WindowSize", "%d,%d" %
            best_size).split(","))
        if not (0 - size[0] < pos[0] < display_size[0] and
                0 - size[1] < pos[1] < display_size[1]):
            pos, size = wx.DefaultPosition, best_size
        super(MainFrame, self).__init__(None, -1, "Berean", pos, size)
        self._app = app
        self.help = html.HelpSystem(self)
        self.minimize_to_tray = app.config.ReadBool("Main/MinimizeToTray")
        self.printing = html.PrintingSystem(self)
        self.rect = wx.RectPS(pos, size)
        self.reference = (app.config.ReadInt("Main/CurrentBook", 1),
            app.config.ReadInt("Main/CurrentChapter", 1),
            app.config.ReadInt("Main/CurrentVerse", -1))
        self.version_list = app.config.ReadList("VersionList", ["KJV", "WEB"])
        self.zoom_level = app.config.ReadInt("Main/ZoomLevel", 3)
        icons = wx.IconBundle()
        icons.AddIconFromFile(os.path.join(app.cwd, "images", "berean-16.png"),
            wx.BITMAP_TYPE_PNG)
        icons.AddIconFromFile(os.path.join(app.cwd, "images", "berean-32.png"),
            wx.BITMAP_TYPE_PNG)
        self.SetIcons(icons)

        self.aui = aui.AuiManager(self, aui.AUI_MGR_DEFAULT |
            aui.AUI_MGR_ALLOW_ACTIVE_PANE)
        self.menubar = menu.MenuBar(self)
        self.SetMenuBar(self.menubar)
        self.toolbar = toolbar.MainToolBar(self)
        self.aui.AddPane(self.toolbar, aui.AuiPaneInfo().Name("toolbar").
            Caption("Main Toolbar").ToolbarPane().Top())
        self.statusbar = self.CreateStatusBar(2)
        self.zoombar = toolbar.ZoomBar(self.statusbar, self)
        if wx.VERSION_STRING >= "2.9.0.0":
            self.statusbar.SetStatusWidths([-1, self.zoombar.width - 8])
        else:
            self.statusbar.SetStatusWidths([-1, self.zoombar.width + 1])

        self.notebook = aui.AuiNotebook(self, -1, style=wx.BORDER_NONE |
            aui.AUI_NB_TOP | aui.AUI_NB_SCROLL_BUTTONS |
            aui.AUI_NB_WINDOWLIST_BUTTON)
        versiondir = os.path.join(app.userdatadir, "versions")
        if not os.path.isdir(versiondir):
            os.mkdir(versiondir)
        i = 0
        tab = app.config.ReadInt("Main/ActiveVersionTab")
        while i < len(self.version_list):
            window = html.ChapterWindow(self.notebook, self.version_list[i])
            if hasattr(window, "Bible"):
                self.notebook.AddPage(window, self.version_list[i], i == tab)
                self.notebook.SetPageBitmap(i, self.get_bitmap(
                    os.path.join("flags", FLAG_NAMES[self.version_list[i]])))
                if wx.VERSION_STRING >= "2.9.4.0":
                    self.notebook.SetPageToolTip(i, window.description)
                i += 1
            else:
                self.version_list.pop(i)
                if 0 < tab <= i:
                    tab -= 1
        if len(self.version_list) > 1:
            self.parallel = parallel.ParallelPanel(self.notebook)
            self.notebook.AddPage(self.parallel, _("Parallel"),
                tab == len(self.version_list))
            if wx.VERSION_STRING >= "2.9.4.0":
                self.notebook.SetPageToolTip(len(self.version_list),
                    self.parallel.htmlwindow.description)
        else:
            self.notebook.SetTabCtrlHeight(0)
        self.notebook.Bind(aui.EVT_AUINOTEBOOK_PAGE_CHANGED,
            self.OnAuiNotebookPageChanged)
        self.aui.AddPane(self.notebook, aui.AuiPaneInfo().Name("notebook").
            CenterPane().PaneBorder(False))

        self.tree = panes.TreePane(self)
        self.aui.AddPane(self.tree, aui.AuiPaneInfo().Name("tree_pane").
            Caption(_("Tree")).Left().Layer(1).BestSize((150, -1)))
        self.search = panes.SearchPane(self)
        self.aui.AddPane(self.search, aui.AuiPaneInfo().Name("search_pane").
            Caption(_("Search")).MaximizeButton(True).Right().Layer(1).
            BestSize((300, -1)))
        self.notes = panes.NotesPane(self)
        self.aui.AddPane(self.notes, aui.AuiPaneInfo().Name("notes_pane").
            Caption(_("Notes")).MaximizeButton(True).Bottom().Layer(0).
            BestSize((-1, 220)))
        self.multiple_verse_search = panes.MultipleVerseSearch(self)
        self.aui.AddPane(self.multiple_verse_search, aui.AuiPaneInfo().
            Name("multiple_verse_search").Caption(_("Multiple Verse Search")).
            MaximizeButton(True).Float().BestSize((600, 440)).Hide())

        filename = os.path.join(app.userdatadir, "layout.dat")
        if os.path.isfile(filename):
            layout = open(filename, 'r')
            self.aui.LoadPerspective(layout.read())
            layout.close()
        self.load_chapter(self.reference[0], self.reference[1],
            self.reference[2], True)
        for pane in ("toolbar", "tree_pane", "search_pane", "notes_pane",
                "multiple_verse_search"):
            self.menubar.Check(getattr(self.menubar, "%s_item" % pane).GetId(),
                self.aui.GetPane(pane).IsShown())
        self.aui.Update()
        if app.config.ReadBool("Main/IsMaximized"):
            self.Maximize()
        self.Bind(aui.EVT_AUI_PANE_CLOSE, self.OnAuiPaneClose)
        self.Bind(wx.EVT_MOVE, self.OnMove)
        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.Bind(wx.EVT_ICONIZE, self.OnIconize)
        self.Bind(wx.EVT_CLOSE, self.OnClose)

    def get_bitmap(self, name):
        return wx.Bitmap(os.path.join(self._app.cwd, "images", "%s.png" %
            name), wx.BITMAP_TYPE_PNG)

    def get_htmlwindow(self, tab=-1):
        if tab == -1:
            tab = self.notebook.GetSelection()
        if tab == len(self.version_list) and len(self.version_list) > 1:
            return self.parallel.htmlwindow
        return self.notebook.GetPage(tab)

    def load_chapter(self, book, chapter, verse=-1, history=False):
        htmlwindow = self.get_htmlwindow()
        htmlwindow.load_chapter(book, chapter, verse)
        selection = self.notebook.GetSelection()
        version = self.notebook.GetPageText(selection)
        self.SetTitle("Berean - %s %d (%s)" % (BOOK_NAMES[book - 1], chapter,
            version))
        if verse == -1:
            reference = "%s %d" % (BOOK_NAMES[book - 1], chapter)
        else:
            reference = "%s %d:%d" % (BOOK_NAMES[book - 1], chapter, verse)
        if reference not in self.toolbar.verse_history:
            self.toolbar.verse_history = \
                self.toolbar.verse_history[:self.toolbar.history_item + 1]
            self.toolbar.verse_history.append(reference)
            if len(self.toolbar.verse_history) >= 15:
                self.toolbar.verse_history.pop(0)
            self.toolbar.set_history_item(-1)
        elif history:
            self.toolbar.set_history_item(self.toolbar.verse_history.index(
                reference))
        else:
            self.toolbar.verse_history.remove(reference)
            self.toolbar.verse_history.append(reference)
            self.toolbar.set_history_item(-1)
        self.tree.select_chapter(book, chapter)
        if self.search.rangechoice.GetSelection() == len(self.search.ranges):
            self.search.start.SetSelection(book - 1)
            self.search.stop.SetSelection(book - 1)
        for i in range(self.notes.GetPageCount()):
            page = self.notes.GetPage(i)
            page.save_text()
            page.load_text(book, chapter)
        self.statusbar.SetStatusText("%s %d (%s)" % (BOOK_NAMES[book - 1],
            chapter, htmlwindow.description), 0)
        self.reference = (book, chapter, verse)
        for i in range(self.notebook.GetPageCount()):
            if i != selection:
                self.get_htmlwindow(i).current_verse = verse
        wx.CallAfter(htmlwindow.SetFocus)

    def set_zoom(self, zoom):
        self.zoom_level = zoom
        self.get_htmlwindow().load_chapter(*self.reference)
        if self.zoombar.slider.GetValue() != zoom:
            self.zoombar.slider.SetValue(zoom)
        self.zoombar.EnableTool(wx.ID_ZOOM_OUT, zoom > 1)
        self.zoombar.EnableTool(wx.ID_ZOOM_IN, zoom < 7)
        self.menubar.Enable(wx.ID_ZOOM_IN, zoom < 7)
        self.menubar.Enable(wx.ID_ZOOM_OUT, zoom > 1)

    def show_search_pane(self, show=True):
        self.aui.GetPane("search_pane").Show(show)
        self.aui.Update()

    def show_multiple_verse_search(self, show=True):
        self.aui.GetPane("multiple_verse_search").Show(show)
        self.aui.Update()

    def OnAuiNotebookPageChanged(self, event):
        selection = event.GetSelection()
        htmlwindow = self.get_htmlwindow()
        htmlwindow.load_chapter(*self.reference)
        self.SetTitle("Berean - %s %d (%s)" %
            (BOOK_NAMES[self.reference[0] - 1], self.reference[1],
            self.notebook.GetPageText(selection)))
        self.statusbar.SetStatusText("%s %d (%s)" %
            (BOOK_NAMES[self.reference[0] - 1], self.reference[1],
            htmlwindow.description), 0)
        if selection < len(self.version_list):
            self.search.version.SetSelection(selection)

    def OnAuiPaneClose(self, event):
        self.menubar.Check(getattr(self.menubar,
            "%s_item" % event.GetPane().name).GetId(), False)

    def OnMove(self, event):
        if self.HasCapture():
            self.rect.SetPosition(self.GetPosition())
        event.Skip()

    def OnSize(self, event):
        x, y, width, height = self.statusbar.GetFieldRect(1)
        self.zoombar.SetRect(wx.Rect(x, (y + height - 19) / 2 -
            self.zoombar.GetToolSeparation(), self.zoombar.width, -1))
        if self.HasCapture():
            self.rect = wx.RectPS(self.GetPosition(), self.GetSize())

    def OnIconize(self, event):
        if (self.minimize_to_tray and event.Iconized() and
                not hasattr(self, "taskbaricon")):
            self.taskbaricon = TaskBarIcon(self)
            self.Hide()
        event.Skip()

    def OnClose(self, event):
        for i in range(self.notes.GetPageCount()):
            self.notes.GetPage(i).OnSave(None)
        self._app.config.save()
        layout = open(os.path.join(self._app.userdatadir, "layout.dat"), 'w')
        layout.write(self.aui.SavePerspective())
        layout.close()
        self.aui.UnInit()
        del self.help
        self.Freeze()
        self.Destroy()
        del self._app.locale
        self._app.ExitMainLoop()


class TaskBarIcon(wx.TaskBarIcon):
    def __init__(self, frame):
        super(TaskBarIcon, self).__init__()
        self._frame = frame
        self.SetIcon(wx.Icon(os.path.join(frame._app.cwd, "images",
            "berean-16.png"), wx.BITMAP_TYPE_PNG), frame.GetTitle())
        self.Bind(wx.EVT_TASKBAR_LEFT_DOWN, self.OnRestore)

    def OnRestore(self, event):
        self._frame.Iconize(False)
        self._frame.Show()
        self._frame.Raise()
        self.RemoveIcon()
        del self._frame.taskbaricon

    def OnExit(self, event):
        wx.CallAfter(self._frame.Close)
        self.OnRestore(event)

    def CreatePopupMenu(self):
        menu = wx.Menu()
        restore_item = menu.Append(-1, _("Restore"))
        self.Bind(wx.EVT_MENU, self.OnRestore, restore_item)
        exit_item = menu.Append(wx.ID_EXIT, _("Exit"))
        self.Bind(wx.EVT_MENU, self.OnExit, exit_item)
        return menu
