# Copyright 2017 The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Utility methods to work with Zip archives."""

try:
    import itertools.izip as zip
except ImportError:
    pass

from operator import attrgetter
from zipfile import ZipFile, ZipInfo
import os


def ZipCompare(path_a, path_b):
  """Compares the contents of two Zip archives, returns True if equal."""

  if not os.path.isfile(path_a) or not os.path.isfile(path_b):
    return False

  with ZipFile(path_a, 'r') as zip_a:
    info_a = zip_a.infolist()

  with ZipFile(path_b, 'r') as zip_b:
    info_b = zip_b.infolist()

  if len(info_a) != len(info_b):
    return False

  info_a.sort(key=attrgetter('filename'))
  info_b.sort(key=attrgetter('filename'))

  return all(
      a.filename == b.filename and
      a.file_size == b.file_size and
      a.CRC == b.CRC
      for a, b in zip(info_a, info_b))


# Metadata to write instead of the metadata a build derives from its environment:
# the JDK's jar tool records the time of the build in every entry and names the
# JDK that built it in the manifest, so two builds of the same data differ.
_CANONICAL_DATE_TIME = (1980, 1, 1, 0, 0, 0)
_CANONICAL_MANIFEST = b'Manifest-Version: 1.0\r\nCreated-By: Android ICU\r\n\r\n'
_MANIFEST_NAME = 'META-INF/MANIFEST.MF'


def ReadZipEntries(path):
  """Returns the entries of a Zip archive as {name: (data, compress_type)}."""

  with ZipFile(path, 'r') as zip_file:
    return {info.filename: (zip_file.read(info), info.compress_type)
            for info in zip_file.infolist()}


def WriteZipCanonical(path, entries):
  """Writes {name: (data, compress_type)} in a form that depends only on data.

  Entries are written with the manifest first, then directories and files in
  name order, all with the same timestamp, file mode and manifest, so that the
  same entries always produce the same bytes.
  """

  def entry_order(name):
    if name == _MANIFEST_NAME:
      return (0, name)
    return (1 if name.endswith('/') else 2, name)

  # Written next to the destination and moved into place so that a failed run
  # cannot leave a truncated archive behind.
  temporary_path = '%s.tmp' % path
  with ZipFile(temporary_path, 'w') as zip_file:
    for name in sorted(entries, key=entry_order):
      data, compress_type = entries[name]
      if name == _MANIFEST_NAME:
        data = _CANONICAL_MANIFEST
      info = ZipInfo(name, date_time=_CANONICAL_DATE_TIME)
      info.compress_type = compress_type
      # ZipInfo would default to mode 0600, which is not what a jar carries.
      info.external_attr = (0o40755 if name.endswith('/') else 0o100644) << 16
      zip_file.writestr(info, data)
  os.replace(temporary_path, path)
