# -*- Mode:Python; indent-tabs-mode:nil; tab-width:4 -*-
#
# Copyright (C) 2015, 2016 Canonical Ltd
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import debian.debfile
import os
import shutil
import tempfile
import logging
import snapcraft
import subprocess

from . import errors
from ._base import FileBase

logger = logging.getLogger(__name__)

class Snap(FileBase):

    def __init__(self, source, source_dir, source_tag=None, source_commit=None,
                 source_branch=None, source_depth=None):
        super().__init__(source, source_dir, source_tag, source_commit,
                         source_branch, source_depth)
        if source_commit:
            raise errors.IncompatibleOptionsError(
                'can\'t specify a source-commit for a snap source')
        self.source_channel = self.source_branch or 'stable'
        self.snap_file = os.path.basename(self.source)

    def pull(self):
        logger.info("Pulling snap: %s" % self.source)
        if self.source.endswith('.snap'):
            super().pull()
            self.snap_file = os.path.join(self.source_dir, os.path.basename(self.source))
        else:
            self.snap_file = os.path.join(self.source_dir, '%s.snap' % self.source)
            self._download()
            self.provision(self.source_dir)

    def _download(self):
        logger.info("Downloading snap: %s" % self.snap_file)

        store = snapcraft.storeapi.StoreClient()
        try:
            arch = snapcraft.ProjectOptions().deb_arch
            package = store.cpi.get_package(self.source, self.source_channel, arch)
            store._download_snap(
                self.source, self.source_channel, arch, self.snap_file,
                package['anon_download_url'], package['download_sha512'])
        except snapcraft.storeapi.errors.SHAMismatchError:
            raise RuntimeError(
                'Failed to download {} at {} (mismatched SHA)'.format(
                    self.source, self.source_dir))
                
    def provision(self, dst, clean_target=True, keep_snap=False):
        logger.info("Provisioning snap: %s to %s" % (self.snap_file, dst))

        # Extract the source snap
        output = subprocess.check_output(['unsquashfs', '-d', dst, '-f', self.snap_file])

        # We don't want a part's snap.yaml conflicting with the parent snap's
        snap_meta = os.path.join(dst, 'meta', 'snap.yaml')
        if os.path.exists(snap_meta):
            os.remove(snap_meta)
        
        # Remove any previously generated snap command wrappers
        for cmd_file in os.listdir(dst):
            if cmd_file.startswith('command-') and cmd_file.endswith('.wrapper'):
                os.remove(os.path.join(dst, cmd_file))
                
        if not keep_snap:
            os.remove(os.path.join(dst, os.path.basename(self.snap_file)))
