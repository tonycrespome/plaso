# -*- coding: utf-8 -*-
"""This file contains a parser for OXML files (i.e. MS Office 2007+)."""

import logging
import re
import struct
import zipfile

from xml.etree import ElementTree

from plaso.events import time_events
from plaso.lib import errors
from plaso.lib import eventdata
from plaso.lib import timelib
from plaso.parsers import interface
from plaso.parsers import manager


__author__ = 'David Nides (david.nides@gmail.com)'


class OpenXMLParserEvent(time_events.TimestampEvent):
  """Process timestamps from MS Office XML Events."""

  DATA_TYPE = u'metadata:openxml'

  def __init__(self, timestamp_string, usage, metadata):
    """Initializes the event object.

    Args:
      timestamp_string: An ISO 8601 representation of a timestamp.
      usage: The description of the usage of the time value.
      metadata: A dict object containing extracted metadata.
    """
    timestamp = timelib.Timestamp.FromTimeString(timestamp_string)
    super(OpenXMLParserEvent, self).__init__(timestamp, usage, self.DATA_TYPE)
    for key, value in metadata.iteritems():
      setattr(self, key, value)


class OpenXMLParser(interface.SingleFileBaseParser):
  """Parse metadata from OXML files."""

  NAME = u'openxml'
  DESCRIPTION = u'Parser for OpenXML (OXML) files.'

  _METAKEY_TRANSLATE = {
      u'creator': u'author',
      u'lastModifiedBy': u'last_saved_by',
      u'Total_Time': u'total_edit_time',
      u'Pages': u'number_of_pages',
      u'CharactersWithSpaces': u'number_of_characters_with_spaces',
      u'Paragraphs': u'number_of_paragraphs',
      u'Characters': u'number_of_characters',
      u'Lines': u'number_of_lines',
      u'revision': u'revision_number',
      u'Words': u'number_of_words',
      u'Application': u'creating_app',
      u'Shared_Doc': u'shared',
  }

  _FILES_REQUIRED = frozenset([
      u'[Content_Types].xml', u'_rels/.rels', u'docProps/core.xml'])

  def _FixString(self, key):
    """Convert CamelCase to lower_with_underscore."""
    # TODO: Add unicode support.
    fix_key = re.sub(r'(.)([A-Z][a-z]+)', r'\1_\2', key)
    return re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', fix_key).lower()

  def ParseFileObject(self, parser_mediator, file_object):
    """Parses an OXML file-like object.

    Args:
      parser_mediator: A parser mediator object (instance of ParserMediator).
      file_object: A file-like object.

    Raises:
      UnableToParseFile: when the file cannot be parsed.
    """
    file_name = parser_mediator.GetDisplayName()

    if not zipfile.is_zipfile(file_object):
      raise errors.UnableToParseFile(
          u'[{0:s}] unable to parse file: {1:s} with error: {2:s}'.format(
              self.NAME, file_name, u'Not a Zip file.'))

    try:
      zip_container = zipfile.ZipFile(file_object, 'r')
    except (zipfile.BadZipfile, struct.error, zipfile.LargeZipFile):
      raise errors.UnableToParseFile(
          u'[{0:s}] unable to parse file: {1:s} with error: {2:s}'.format(
              self.NAME, file_name, u'Bad Zip file.'))

    zip_name_list = set(zip_container.namelist())

    if not self._FILES_REQUIRED.issubset(zip_name_list):
      raise errors.UnableToParseFile(
          u'[{0:s}] unable to parse file: {1:s} with error: {2:s}'.format(
              self.NAME, file_name, u'OXML element(s) missing.'))

    metadata = {}
    timestamps = {}

    try:
      rels_xml = zip_container.read(u'_rels/.rels')
    except zipfile.BadZipfile as exception:
      parser_mediator.ProduceParseError(
          u'Unable to parse file with error: {0:s}'.format(exception))
      return

    rels_root = ElementTree.fromstring(rels_xml)

    for properties in rels_root.iter():
      if u'properties' in repr(properties.get(u'Type')):
        try:
          xml = zip_container.read(properties.get(u'Target'))
          root = ElementTree.fromstring(xml)
        except (
            OverflowError, IndexError, KeyError, ValueError,
            zipfile.BadZipfile) as exception:
          logging.warning(
              u'[{0:s}] unable to read property with error: {1:s}.'.format(
                  self.NAME, exception))
          continue

        for element in root.iter():
          if element.text:
            _, _, tag = element.tag.partition(u'}')
            # Not including the 'lpstr' attribute because it is
            # very verbose.
            if tag == u'lpstr':
              continue

            if tag in [u'created', u'modified', u'lastPrinted']:
              timestamps[tag] = element.text
            else:
              tag_name = self._METAKEY_TRANSLATE.get(tag, self._FixString(tag))
              metadata[tag_name] = element.text

    created = timestamps.get(u'created', None)
    if created:
      event_object = OpenXMLParserEvent(
          created, eventdata.EventTimestamp.CREATION_TIME, metadata)
      parser_mediator.ProduceEvent(event_object)

    modified = timestamps.get(u'modified', None)
    if modified:
      event_object = OpenXMLParserEvent(
          modified, eventdata.EventTimestamp.MODIFICATION_TIME, metadata)
      parser_mediator.ProduceEvent(event_object)

    last_printed = timestamps.get(u'lastPrinted', None)
    if last_printed:
      event_object = OpenXMLParserEvent(
          last_printed, eventdata.EventTimestamp.LAST_PRINTED, metadata)
      parser_mediator.ProduceEvent(event_object)


manager.ParsersManager.RegisterParser(OpenXMLParser)
