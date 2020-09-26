# Copyright (C) 2020 Hyun Woo Park
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# -*- coding: utf-8 -*-
#
# addon_template v20.5.4i8
#
# Copyright: trgk (phu54321@naver.com)
# License: GNU AGPL, version 3 or later;
# See http://www.gnu.org/licenses/agpl.html

# -*- mode: Python ; coding: utf-8 -*-
#
# Cloze (Hide All) - v6
#   Adds a new card type "Cloze (Hide All)", which hides all clozes on its
#   front and optionally on the back.
#
# Changelog
#  v6: support anki 2.1
#  v5 : DOM-boundary crossing clozes will be handled properly
#  .1 : More rubust DOM boundary handling
#        Compatiable with addon 719871418
#  v4 : Prefixing cloze content with ! will make it visibile on other clozes.
#        Other hidden content's size will be fixed. (No automatic update)
#  .1 : Fixed bug when editing notes (EditCurrent hook, better saveNow hook)
#       Fixed issues where wrong fields are marked as 'sticky'
#  v3 : Fixed issues which caused text to disappear on the mac version,
#        Added option to hide other clozes on the back.
#  v2 : Support clozes with hint
#  v1 : Initial release
#
# Copyright © 2019 Hyun Woo Park (phu54321@naver.com)
# License: GNU GPL, version 3 or later; http://www.gnu.org/copyleft/gpl.html
#
# Lots of code from
#   - Cloze overlapper (by Glutaminate)
#   - Batch Note Editing (by Glutaminate)
#

import re

from aqt.editor import Editor
from aqt.browser import ChangeModel
from anki.hooks import addHook, wrap

from .applyClozeHide import tokenizeHTML, optimizeChunks
from .clozeHideAllModel import registerClozeModel
from .consts import model_name
from .utils import openChangelog
from .utils import uuid  # duplicate UUID checked here


# @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
#
# Main code
#
# @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@

addHook("profileLoaded", registerClozeModel)


def stripClozeHelper(html):
    return re.sub(
        r"</?(cz_hide|cloze2|cloze2_w)[^>]*?>|"
        + r"<(cloze2_w|cloze2)[^>]*?class=(\"|')cz-\d+(\"|')[^>]*?>|"
        + r"<script( class=(\"|')cz-\d+(\"|'))?>_czha\(\d+\)</script>",
        "",
        html,
    )


def wrapClozeTag(segment, clozeId):
    """
    Cloze may span across DOM boundary. This ensures that clozed text
    in elements different from starting element to be properly hidden
    by enclosing them by <cloze2>
    """

    output = ["<cloze2_w class='cz-%d'></cloze2_w>" % clozeId]
    cloze_header = "<cloze2 class='cz-%d'>" % clozeId
    cloze_footer = "</cloze2>"

    chunks = tokenizeHTML(segment)
    chunks = optimizeChunks(chunks)

    for chunk in chunks:
        if chunk[0] == "raw":
            output.append(cloze_header)
            output.append(chunk[1])
            output.append(cloze_footer)
        else:
            output.append(chunk[1])

    return "".join(output)


def makeClozeCompatiable(html):
    html = re.sub(
        r"\{\{c(\d+)::([^!?]([^:}]|:[^:}])*?)\}\}",
        lambda match: "{{c%s::%s}}"
        % (match.group(1), wrapClozeTag(match.group(2), int(match.group(1)))),
        html,
    )
    html = re.sub(
        r"\{\{c(\d+)::([^!?]([^:}]|:[^:}])*?)::(([^:}]|:[^:}])*?)\}\}",
        lambda match: "{{c%s::%s::%s}}"
        % (
            match.group(1),
            wrapClozeTag(match.group(2), int(match.group(1))),
            match.group(4),
        ),
        html,
    )
    html = re.sub(r"\{\{c(\d+)::([!?])", "{{c\\1::<cz_hide>\\2</cz_hide>", html)
    return html


def updateNote(note):
    for key in note.keys():
        html = note[key]
        html = stripClozeHelper(html)
        html = makeClozeCompatiable(html)
        note[key] = html


def beforeSaveNow(self, callback, keepFocus=False, *, _old):
    """Automatically generate overlapping clozes before adding cards"""

    def newCallback():
        # self.note may be None when editor isn't yet initialized.
        # ex: entering browser
        if self.note and self.note.model()["name"] == model_name:
            updateNote(self.note)
            if not self.addMode:
                self.note.flush()
                self.mw.requireReset()
        callback()

    return _old(self, newCallback, keepFocus)


Editor.saveNow = wrap(Editor.saveNow, beforeSaveNow, "around")


# Support for `batch change node types on card type change` addon
# TODO: check if anki 2.1 version of this addon exists?


def applyClozeFormat(browser, nids):
    mw = browser.mw
    mw.checkpoint("Note type change to cloze (reveal one)")
    mw.progress.start()
    browser.model.beginReset()
    for nid in nids:
        note = mw.col.getNote(nid)
        updateNote(note)
        note.flush()
    browser.model.endReset()
    mw.requireReset()
    mw.progress.finish()
    mw.reset()


def onChangeModel(self):
    if self.targetModel["name"] == model_name:
        applyClozeFormat(self.browser, self.nids)


ChangeModel.accept = wrap(ChangeModel.accept, onChangeModel, "before")
