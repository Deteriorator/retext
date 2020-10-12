# This file is part of ReText
# Copyright: 2012-2018 Dmitry Shachnev
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from ReText import settings
from enum import IntFlag, auto
import re

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat

reHtmlTags     = re.compile('<[^<>@]*>')
reHtmlSymbols  = re.compile(r'&#?\w+;')
reHtmlStrings  = re.compile('"[^"<]*"(?=[^<]*>)')
reHtmlComments = re.compile('<!--[^<>]*-->')
reAsterisks    = re.compile(r'(?<!\*)\*[^ \*][^\*]*\*')
reUnderline    = re.compile(r'(?<!_|\w)_[^_]+_(?!\w)')
reDblAsterisks = re.compile(r'(?<!\*)\*\*((?!\*\*).)*\*\*')
reDblUnderline = re.compile(r'(?<!_|\w)__[^_]+__(?!\w)')
reTrpAsterisks = re.compile(r'\*{3,3}[^\*]+\*{3,3}')
reTrpUnderline = re.compile('___[^_]+___')
reMkdHeaders   = re.compile('^#.+')
reMkdLinksImgs = re.compile(r'(?<=\[)[^\[\]]*(?=\])')
reMkdLinkRefs  = re.compile(r'(?<=\]\()[^\(\)]*(?=\))')
reBlockQuotes  = re.compile('^ *>.+')
reReSTDirects  = re.compile(r'\.\. [a-z]+::')
reReSTRoles    = re.compile('(:[a-z-]+:)(`.+?`)')
reReSTLinks    = re.compile('(`.+?<)(.+?)(>`__?)')
reReSTLinkRefs = re.compile(r'\.\. _`?(.*?)`?: (.*)')
reReSTFldLists = re.compile('^ *:(.*?):')
reTextileHdrs  = re.compile(r'^h[1-6][()<>=]*\.\s.+')
reTextileQuot  = re.compile(r'^bq\.\s.+')
reMkdCodeSpans = re.compile('`[^`]*`')
reMkdMathSpans = re.compile(r'\\[\(\[].*?\\[\)\]]')
reReSTCodeSpan = re.compile('``.+?``')
reWords        = re.compile('[^_\\W]+')
reSpacesOnEnd  = re.compile(r'\s+$')

defaultColorScheme = {
	'htmlTags': Qt.darkMagenta,
	'htmlSymbols': Qt.darkCyan,
	'htmlStrings': Qt.darkYellow,
	'htmlComments': Qt.gray,
	'codeSpans': QColor(0x50, 0x50, 0x50),
	'markdownLinks': QColor(0, 0, 0x90),
	'blockquotes': Qt.darkGray,
	'restDirectives': Qt.darkMagenta,
	'restRoles': Qt.darkRed,
	'whitespaceOnEnd': QColor(0xe1, 0xe1, 0xa5, 0x80)
}
colorScheme = {}

def updateColorScheme(settings=settings):
	settings.beginGroup('ColorScheme')
	for key in defaultColorScheme:
		if settings.contains(key):
			colorScheme[key] = settings.value(key, type=QColor)
		else:
			colorScheme[key] = defaultColorScheme[key]
	settings.endGroup()

updateColorScheme()

class Formatter:
	def __init__(self, funcs=None):
		self._funcs = funcs or []

	def __or__(self, other):
		result = Formatter(self._funcs.copy())
		if isinstance(other, Formatter):
			result._funcs.extend(other._funcs)
		elif isinstance(other, QFont.Weight):
			result._funcs.append(lambda f: f.setFontWeight(other))
		return result

	def format(self, charFormat):
		for func in self._funcs:
			func(charFormat)

NF = Formatter()
ITAL = Formatter([lambda f: f.setFontItalic(True)])
UNDL = Formatter([lambda f: f.setFontUnderline(True)])

def FG(colorName):
	color = colorScheme[colorName]
	func = lambda f: f.setForeground(color)
	return Formatter([func])

def QString_length(text):
	# In QString, surrogate pairs are represented using multiple QChars,
	# so the length of QString is not always equal to the number of graphemes
	# in it (which is the case with Python strings).
	return sum(2 if ord(char) > 65535 else 1 for char in text)


class Markup(IntFlag):
	Mkd = auto()
	ReST = auto()
	Textile = auto()
	HTML = auto()


docTypesMapping = {
	'Markdown': Markup.Mkd,
	'reStructuredText': Markup.ReST,
	'Textile': Markup.Textile,
	'html': Markup.HTML,
}


class ReTextHighlighter(QSyntaxHighlighter):
	dictionary = None
	docType = None

	patterns = (
		# regex,         color,                                markups
		(reHtmlTags,     FG('htmlTags') | QFont.Bold,          Markup.Mkd | Markup.Textile | Markup.HTML),
		(reHtmlSymbols,  FG('htmlSymbols') | QFont.Bold,       Markup.Mkd | Markup.HTML),
		(reHtmlStrings,  FG('htmlStrings') | QFont.Bold,       Markup.Mkd | Markup.HTML),
		(reHtmlComments, FG('htmlComments'),                   Markup.Mkd | Markup.HTML),
		(reAsterisks,    ITAL,                                 Markup.Mkd | Markup.ReST),
		(reUnderline,    ITAL,                                 Markup.Mkd | Markup.Textile),
		(reDblAsterisks, NF | QFont.Bold,                      Markup.Mkd | Markup.ReST | Markup.Textile),
		(reDblUnderline, NF | QFont.Bold,                      Markup.Mkd),
		(reTrpAsterisks, ITAL | QFont.Bold,                    Markup.Mkd),
		(reTrpUnderline, ITAL | QFont.Bold,                    Markup.Mkd),
		(reMkdHeaders,   NF | QFont.Black,                     Markup.Mkd),
		(reMkdLinksImgs, FG('markdownLinks'),                  Markup.Mkd),
		(reMkdLinkRefs,  ITAL | UNDL,                          Markup.Mkd),
		(reBlockQuotes,  FG('blockquotes'),                    Markup.Mkd),
		(reReSTDirects,  FG('restDirectives') | QFont.Bold,    Markup.ReST),
		(reReSTRoles,    NF, FG('restRoles') | QFont.Bold, FG('htmlStrings'), Markup.ReST),
		(reTextileHdrs,  NF | QFont.Black,                     Markup.Textile),
		(reTextileQuot,  FG('blockquotes'),                    Markup.Textile),
		(reAsterisks,    NF | QFont.Bold,                      Markup.Textile),
		(reDblUnderline, ITAL,                                 Markup.Textile),
		(reMkdCodeSpans, FG('codeSpans'),                      Markup.Mkd),
		(reReSTCodeSpan, FG('codeSpans'),                      Markup.ReST),
		(reReSTLinks,    NF, NF, ITAL | UNDL, NF,              Markup.ReST),
		(reReSTLinkRefs, NF, FG('markdownLinks'), ITAL | UNDL, Markup.ReST),
		(reReSTFldLists, NF, FG('restDirectives'),             Markup.ReST),
		(reMkdMathSpans, FG('codeSpans'),                      Markup.Mkd),
	)

	def highlightBlock(self, text):
		# Syntax highlighter
		if self.docType in docTypesMapping:
			markup = docTypesMapping[self.docType]
			for pattern, *formatters, markups in self.patterns:
				if not (markup & markups):
					continue
				for match in pattern.finditer(text):
					for i, formatter in enumerate(formatters):
						charFormat = QTextCharFormat()
						formatter.format(charFormat)
						self.setFormat(QString_length(text[:match.start(i)]),
						               QString_length(match.group(i)),
						               charFormat)
		for match in reSpacesOnEnd.finditer(text):
			charFormat = QTextCharFormat()
			charFormat.setBackground(colorScheme['whitespaceOnEnd'])
			self.setFormat(QString_length(text[:match.start()]),
			               QString_length(match.group(0)),
			               charFormat)
		# Spell checker
		if self.dictionary:
			charFormat = QTextCharFormat()
			charFormat.setUnderlineColor(Qt.red)
			charFormat.setUnderlineStyle(QTextCharFormat.SpellCheckUnderline)
			for match in reWords.finditer(text):
				finalFormat = QTextCharFormat()
				finalFormat.merge(charFormat)
				finalFormat.merge(self.format(match.start()))
				if not self.dictionary.check(match.group(0)):
					self.setFormat(QString_length(text[:match.start()]),
					               QString_length(match.group(0)),
					               finalFormat)
