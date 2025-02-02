"""html2.py - HTML related classes"""

import os.path
import pickle
import webbrowser

import wx
import wx.lib.dragscroller
from wx import html

from constants import BOOK_NAMES, BOOK_LENGTHS

_ = wx.GetTranslation


class HelpSystem(html.HtmlHelpController):
    def __init__(self, frame):
        super(HelpSystem, self).__init__(parentWindow=frame)
        self._frame = frame
        self.SetTempDir(os.path.join(frame._app.userdatadir, ""))
        self.SetTitleFormat("%s")
        self.UseConfig(frame._app.config, "Help")
        filename = os.path.join(frame._app.cwd, "locale", frame._app.language, "help", "header.hhp")
        if not os.path.isfile(filename):
            filename = os.path.join(frame._app.cwd, "locale", "en_US", "help", "header.hhp")
        self.AddBook(filename)

    def show_frame(self):
        frame = self.GetFrame()
        if not frame:
            self.DisplayContents()
            self.GetHelpWindow().Bind(html.EVT_HTML_LINK_CLICKED, self.OnHtmlLinkClicked)
        else:
            frame.Raise()

    def OnHtmlLinkClicked(self, event):
        url = event.GetLinkInfo().GetHref()
        if url.partition(":")[0] in ("http", "https", "mailto"):
            webbrowser.open(url)
        else:
            event.Skip()


class PrintingSystem(html.HtmlEasyPrinting):
    def __init__(self, frame):
        super(PrintingSystem, self).__init__("Berean", frame)
        self._frame = frame
        data = self.GetPageSetupData()
        data.SetMarginTopLeft(wx.Point(15, 15))
        data.SetMarginBottomRight(wx.Point(15, 15))
        self.SetFooter(_("<div align=\"center\"><font size=\"-1\">Page @PAGENUM@</font></div>"))
        self.SetStandardFonts(**frame.default_font)

    def get_chapter_text(self):
        text = self._frame.get_htmlwindow().get_html(
            *self._frame.reference[:2])
        tab = self._frame.notebook.GetSelection()
        if tab < len(self._frame.version_list):
            text = text.replace("</b>", " (%s)</b>" % self._frame.notebook.GetPageText(tab), 1)
        return text

    def print_chapter(self):
        self.SetName(self._frame.GetTitle()[9:])
        self.PrintText(self.get_chapter_text())

    def preview_chapter(self):
        self.SetName(self._frame.GetTitle()[9:])
        self.PreviewText(self.get_chapter_text())


class HtmlWindowBase(html.HtmlWindow):
    def __init__(self, parent, frame):
        super(HtmlWindowBase, self).__init__(parent)
        self.SetAcceleratorTable(wx.AcceleratorTable([(wx.ACCEL_CTRL, ord("A"), wx.ID_SELECTALL)]))
        self.SetStandardFonts(**frame.default_font)
        self.Bind(wx.EVT_MENU, self.OnSelectAll, id=wx.ID_SELECTALL)
        self.dragscroller = wx.lib.dragscroller.DragScroller(self)
        self.Bind(wx.EVT_MIDDLE_DOWN, self.OnMiddleDown)
        self.Bind(wx.EVT_MIDDLE_UP, self.OnMiddleUp)

    def OnSelectAll(self, event):
        self.SelectAll()

    def OnMiddleDown(self, event):
        if not self.HasCapture():  # Skip event if context menu is shown
            self.dragscroller.Start(event.GetPosition())

    def OnMiddleUp(self, event):
        self.dragscroller.Stop()


class ChapterWindowBase(HtmlWindowBase):
    def __init__(self, parent, frame):
        super(ChapterWindowBase, self).__init__(parent, frame)
        self._frame = frame
        self.current_verse = -1
        self.reference = None
        self.zoom_level = frame.zoom_level
        self.Bind(wx.EVT_CONTEXT_MENU, self.OnContextMenu)

    def load_chapter(self, book, chapter, verse):
        self.SetPage(self.get_html(book, chapter, verse))
        if verse > 1:  # and self.HasAnchor(str(verse)):
            wx.CallAfter(self.ScrollToAnchor, str(verse))
            self.current_verse = -1
        self.reference = (book, chapter, verse)
        self.zoom_level = self._frame.zoom_level

    def OnContextMenu(self, event):
        menu = wx.Menu()
        selected = len(self.SelectionToText()) > 0
        if selected:
            menu.Append(wx.ID_COPY, _("&Copy"))
        menu.Append(wx.ID_SELECTALL, _("Select &All"))
        menu.AppendSeparator()
        search_item = menu.Append(wx.ID_ANY, _("&Search for Selected Text"))
        self.Bind(wx.EVT_MENU, self.OnSearch, search_item)
        menu.Enable(search_item.GetId(), selected)
        menu.AppendSeparator()
        menu.Append(wx.ID_PRINT, _("&Print..."))
        menu.Append(wx.ID_PREVIEW, _("P&rint Preview"))
        self.PopupMenu(menu)

    def OnSearch(self, event):
        if not self._frame.aui.GetPane("search_pane").IsShown():
            self._frame.show_search_pane()
        self._frame.search.text.SetValue(
            self.SelectionToText().strip().lstrip("1234567890 "))
        self._frame.search.OnSearch(None)


class ChapterWindow(ChapterWindowBase):
    def __init__(self, parent, version):
        super(ChapterWindow, self).__init__(parent, parent.GetParent())
        filename = os.path.join(self._frame._app.cwd, "versions", "%s.bbl" % version)
        if not os.path.isfile(filename):
            filename = os.path.join(self._frame._app.version_dir, "%s.bbl" % version)
        try:
            with open(filename, 'rb') as fileobj:
                metadata = pickle.load(fileobj)
                self.Bible = pickle.load(fileobj)
                self.Bible[0] = metadata
        except IOError as exc:
            wx.MessageBox(_("Could not load %s.\n\nError: %s") % (version, exc), _("Error"),
                          wx.ICON_WARNING | wx.OK)
        else:
            self.description = self.Bible[0]["description"]
            self.flag_name = self.Bible[0]["lang"].split("-")[0]

    def get_html(self, book, chapter, verse=-1):
        if self.Bible[book] and self.Bible[book][chapter]:
            header = "<font size=\"+2\"><b>%s %d</b></font>" % (BOOK_NAMES[book - 1], chapter)
            if self.Bible[book][chapter][0]:
                header += "<br><i>%s</i>" % self.Bible[book][chapter][0].replace("]", "<i>").replace("[", "</i>")
            verses = []
            for i in range(1, len(self.Bible[book][chapter])):
                verse_text = self.Bible[book][chapter][i]
                if not verse_text:
                    continue
                verse_text = "<font size=\"-1\">%d&nbsp;</font>%s" % \
                             (i, verse_text.replace("[", "<i>").replace("]", "</i>"))
                if i == verse:
                    verse_text = "<b>%s</b>" % verse_text
                if not self._frame.menubar.paragraph_breaks:
                    verses.append("<a name=\"%d\">%s</a>" % (i, verse_text))
                elif "\xb6" in verse_text or len(verses) == 0:
                    verses.append("&nbsp;&nbsp;&nbsp;&nbsp;<a name=\"%d\">%s</a>" %
                                  (i, verse_text.replace("\xb6", "")))
                else:
                    verses[-1] += "&nbsp;<a name=\"%d\">%s</a>" % (i, verse_text)
            if chapter == BOOK_LENGTHS[book - 1] and self.Bible[book][0]:
                verses[-1] += "<hr><div align=\"center\"><i>%s</i></div>" % \
                              self.Bible[book][0].replace("]", "<i>").replace("[", "</i>")
        else:
            header = ""
            verses = [_("<font color=\"gray\">%s %d is not in this version.</font>") %
                      (BOOK_NAMES[book - 1], chapter)]
        return "<html><body><font size=\"%d\"><div align=center>%s</div>%s</font></body>" \
               "</html>" % (self._frame.zoom_level, header, "<br>".join(verses))
