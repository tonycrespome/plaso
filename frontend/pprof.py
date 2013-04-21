#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright 2012 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Test run for a single file and a display of how many events are collected."""
import argparse
import collections
import cProfile
import logging
import os
import pstats
import sys
import time

from plaso.lib import engine
from plaso.lib import event
from plaso.lib import preprocess
from plaso.lib import putils
from plaso.lib import queue
from plaso.lib import worker

import pyevt
import pyevtx
import pylnk
import pymsiecf
import pyregf
import pytz
import pyvshadow


def Main():
  """Start the tool."""
  usage = """
Run this tool against a single file to see how many events are extracted
from it and which parsers recognize it.
  """
  arg_parser = argparse.ArgumentParser(description=usage)

  format_str = '[%(levelname)s] %(message)s'
  logging.basicConfig(level=logging.INFO, format=format_str)

  arg_parser.add_argument(
      '-v', '--verbose', dest='verbose', action='store_true', default=False,
      help='Be extra verbose in the information printed out.')

  arg_parser.add_argument(
      'file_to_parse', nargs='?', action='store', metavar='FILE_TO_PARSE',
      default=None, help='A path to the file that is to be parsed.')

  arg_parser.add_argument(
      'filter', action='store', metavar='FILTER', nargs='?', default=None,
      help=('A filter that can be used to filter the dataset before it '
            'is written into storage. More information about the filters'
            ' and it\'s usage can be found here: http://plaso.kiddaland.'
            'net/usage/filters'))

  options = arg_parser.parse_args()

  if not options.file_to_parse:
    arg_parser.print_help()
    print ''
    arg_parser.print_usage()
    print ''
    logging.error('Not able to run without a file to process.')
    sys.exit(1)

  if not os.path.isfile(options.file_to_parse):
    logging.error(
        u'File [%s] needs to exist.',
        options.file_to_parse)
    sys.exit(1)

  try:
    fh = putils.OpenOSFile(options.file_to_parse)
  except IOError as e:
    logging.error(u'Unable to open file: %s, error given %s',
                  options.file_to_parse, e)
    sys.exit(1)

  print '\n{:*^80}'.format(' File Parsed ')
  print u'{:>20s}'.format(options.file_to_parse)

  print '\n{:*^80}'.format(' Versions ')
  print u'{:>20s} : {}'.format('plaso engine', engine.__version__)
  print u'{:>20s} : {}'.format('pyevt', pyevt.get_version())
  print u'{:>20s} : {}'.format('pyevtx', pyevtx.get_version())
  print u'{:>20s} : {}'.format('pylnk', pylnk.get_version())
  print u'{:>20s} : {}'.format('pymsiecf', pymsiecf.get_version())
  print u'{:>20s} : {}'.format('pyregf', pyregf.get_version())
  print u'{:>20s} : {}'.format('pyvshadow', pyvshadow.get_version())

  pre_obj = preprocess.PlasoPreprocess()
  pre_obj.zone = pytz.UTC
  simple_queue = queue.SingleThreadedQueue()
  my_worker = worker.PlasoWorker('0', None, simple_queue, options, pre_obj)

  if options.verbose:
    profiler = cProfile.Profile()
    profiler.enable()
  else:
    time_start = time.time()
  my_worker.ParseFile(fh)

  if options.verbose:
    profiler.disable()
  else:
    time_end = time.time()

  fh.close()

  counter = collections.Counter()
  parsers = []
  for item in simple_queue.PopItems():
    event_object = event.EventObject()
    event_object.FromProtoString(item)
    parser = getattr(event_object, 'parser', 'N/A')
    if parser not in parsers:
      parsers.append(parser)
    counter[parser] += 1
    counter['Total'] += 1

  if not options.verbose:
    print '\n{:*^80}'.format(' Time Used ')
    print u'{:>20f}s'.format(time_end - time_start)

  print '\n{:*^80}'.format(' Parsers Used ')
  for parser in sorted(parsers):
    print u'{:>20s}'.format(parser)

  print '\n{:*^80}'.format(' Counter ')
  for key, value in counter.most_common():
    print u'{:>20s} : {}'.format(key, value)

  if options.verbose:
    stats = pstats.Stats(profiler, stream=sys.stdout)
    print '\n{:*^80}'.format(' Profiler ')

    print '\n{:-^20}'.format(' Top 5 Time Spent ')
    stats.sort_stats('cumulative')
    stats.print_stats(5)

    print '\n{:-^20}'.format(' Sorted By Function Calls ')
    stats.sort_stats('calls')
    stats.print_stats()


if __name__ == '__main__':
  Main()
