#!/usr/bin/env python3
#
#  LomiriForUbuntu.py
#
#  Copyright 2024 Robert Tari <robert@tari.in>
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#
#

TEMP_PATH = "/home/tari/Desktop/tmp/LomiriForUbuntu"
CREDENTIALS_PATH = "/home/tari/Desktop/.LomiriForUbuntu.txt"

from datetime import datetime, timedelta, timezone
from git import Repo
from launchpadlib.credentials import AccessToken
from launchpadlib.credentials import Consumer
from launchpadlib.credentials import Credentials
from launchpadlib.launchpad import Launchpad
from lazr.restfulclient.errors import HTTPError
from time import sleep
import gitlab
import pathlib
import shutil
import subprocess
import signal
import sys
import tarfile

def onSignal (pSignal, pFrame):

    print ("\nAborting...\n")
    sys.exit (0)

def cleanUp (pPath):

    for pChild in pPath.iterdir ():

        if pChild.is_dir ():

            shutil.rmtree (pChild)

        else:

            pChild.unlink ()

if __name__ == '__main__':

    signal.signal (signal.SIGINT, onSignal)
    lPackages = []

    if sys.argv[1:]:

        lPackages.append (sys.argv[1:][0])

    else:

        # Get all projects from Salsa
        pGitlab = gitlab.Gitlab ("https://salsa.debian.org")
        pGroup = pGitlab.groups.get (id="ubports-team", lazy=True)
        lProjects = pGroup.projects.list (get_all=True, order_by="name", sort="asc")

        for pProject in lProjects:

            lPackages.append (pProject.name)
        #~Get all projects from Salsa

    pTempPath = pathlib.Path (TEMP_PATH)
    pTempPath.mkdir (parents=True, exist_ok=True)
    pCredentials = Credentials ("LomiriForUbuntu")
    pCredentialsPath = pathlib.Path (CREDENTIALS_PATH)

    if pCredentialsPath.is_file ():

        pFile = open (CREDENTIALS_PATH)
        pCredentials.load (pFile)
        pFile.close ()

    else:

        sToken = pCredentials.get_request_token (web_root="production")
        bComplete = False
        bUrlShown = False

        while not bComplete:

            try:
                pCredentials.exchange_request_token_for_access_token (web_root="production")
                pFile = open (CREDENTIALS_PATH, 'w')
                pCredentials.save (pFile)
                pFile.close ()
                bComplete = True

            except HTTPError:

                if not bUrlShown:

                    print (sToken)
                    bUrlShown = True

                sleep (1)

    pLaunchpad = Launchpad.login_with ("LomiriForUbuntu", "production", credentials_file=CREDENTIALS_PATH, version="devel")
    pGroup = pLaunchpad.people["lomiri"]

    for sPackage in lPackages:

        # Clean up
        cleanUp (pTempPath)
        #~Clean up

        # Create a new repository or pull the code from Launchpad
        pRepository = pLaunchpad.git_repositories.getByPath (path=f"~lomiri/+git/{sPackage}")
        bNewRepo = False

        if not pRepository:

            print (f"{sPackage}: Creating repository")
            pRepository = pLaunchpad.git_repositories.new (name=sPackage, owner=pGroup, target=pGroup)
            bNewRepo = True

        pNow = datetime.now (timezone.utc)
        pExpires = pNow + timedelta (seconds=3600)
        sExpires = pExpires.isoformat ()
        sAccessToken = pRepository.issueAccessToken (description=f"Access token for {pLaunchpad.me.name}", scopes=["repository:push", "repository:pull"], date_expires=sExpires)
        pRepo = Repo.init (TEMP_PATH)
        pMain = pRepo.create_remote ("main", url=f"https://{pLaunchpad.me.name}:{sAccessToken}@git.launchpad.net/~lomiri/+git/{sPackage}")

        if not bNewRepo:

            pMain.fetch ("main")
            pRepo.create_head ("main", pMain.refs.main)
            pRepo.heads.main.checkout ()
            pMain.pull ("main:main")
        #~Create a new repository or pull the code from Launchpad

        # Get the Debian folder
        pSalsaPath = pathlib.Path (TEMP_PATH, "salsa")
        Repo.clone_from (f"https://salsa.debian.org/ubports-team/{sPackage}.git", pSalsaPath)
        #~Get the Debian folder

        # Download the tarball
        try:

            subprocess.run ("uscan --noconf --rename --download-current-version --destdir=. 1> /dev/null", shell=True, cwd=pSalsaPath, check=True)

        except subprocess.CalledProcessError as pException:

            print (pException)

            sys.exit (1)
        #~Download the tarball

        # Extract the tarball
        pTarPath = pSalsaPath.glob ("*.tar.bz2")
        sTarPath = list (pTarPath)[0]

        with tarfile.open (sTarPath, "r:bz2") as pTarFile:

            lMembers = pTarFile.getmembers ()
            pToplevelPath = pathlib.Path (lMembers[0].name).parts[0]

            for pMember in lMembers:

                pMemberPath = pathlib.Path (pMember.name)
                pMember.name = pMemberPath.relative_to (pToplevelPath)
                pTarFile.extract (pMember, TEMP_PATH, filter="fully_trusted")
        #~Extract the tarball

        # Remove the Salsa folder
        cleanUp (pSalsaPath)
        pSalsaPath.rmdir ()
        #~Remove the Salsa folder

        # Push the changes to Launchpad
        if bNewRepo or pRepo.is_dirty ():

            print (f"{sPackage}: Pushing changes to Launchpad")
            pRepo.git.add (A=True)
            pRepo.index.commit ("Synchronised with upstream")

            if bNewRepo:

                pRepo.create_head ("main")
                pRepo.heads.main.checkout ()

            pMain.push ("main:main").raise_if_error ()
        #~Push the changes to Launchpad

        """
        # Create build recipes (multiple distro series)
        pArchive = pGroup.getPPAByName (name="builds")

        for pDistroseries in pLaunchpad.distributions["ubuntu"].series:

            if float (pDistroseries.version) >= 24.04:

                sRecipe = f"{sPackage}-{pDistroseries.version}"
                pRecipe = pGroup.getRecipe (name=sRecipe)

                if not pRecipe:

                    print (f"{sPackage}: Creating build recipe {sRecipe}")
                    pGroup.createRecipe (build_daily=True, daily_build_archive=pArchive, description=f"Daily build of {sPackage}", distroseries=pDistroseries, name=sRecipe, recipe_text="# git-build-recipe format 0.4 deb-version {debupstream}-{revtime}\nlp:~lomiri/+git/" + sPackage + " main")
        #~Create build recipes (multiple distro series)
        """

        # Create build recipe (one distro series)
        pRecipe = pGroup.getRecipe (name=sPackage)

        if not pRecipe:

            print (f"{sPackage}: Creating build recipe")
            pArchive = pGroup.getPPAByName (name="builds")
            pDistroseries = pLaunchpad.distributions["ubuntu"].getSeries (name_or_version="24.04")
            pGroup.createRecipe (build_daily=True, daily_build_archive=pArchive, description=f"Daily build of {sPackage}", distroseries=pDistroseries, name=sPackage, recipe_text="# git-build-recipe format 0.4 deb-version {debupstream}-{revtime}\nlp:~lomiri/+git/" + sPackage + " main")
        #~Create build recipe (one distro series)

    # Clean up
    cleanUp (pTempPath)
    #~Clean up

    sys.exit (0)
