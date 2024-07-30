#!/usr/bin/env python3
#
#  salsa2lp-sync.py
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
import re
import shutil
import subprocess
import signal
import sys
import tarfile

def onSignal (pSignal, pFrame):

    print ("\nAborting...\n")
    sys.exit (0)

def cleanUp (pPath, lExclude):

    for pChild in pPath.iterdir ():

        if pChild not in lExclude:

            if pChild.is_dir ():

                shutil.rmtree (pChild)

            else:

                pChild.unlink ()

if __name__ == '__main__':

    signal.signal (signal.SIGINT, onSignal)
    lPackages = []
    lArgs = sys.argv[1:]
    sHome = pathlib.Path.home ()
    pTempPath = pathlib.Path (sHome, ".cache/salsa2lp-sync")
    pTempPath.mkdir (parents=True, exist_ok=True)
    pCredentials = Credentials ("salsa2lp-sync")
    pConfigDirPath = pathlib.Path (sHome, ".config/salsa2lp-sync")
    pConfigDirPath.mkdir (parents=True, exist_ok=True)
    pCredentialsPath = pathlib.Path (pConfigDirPath, "Credentials.txt")
    pPackagesPath = pathlib.Path (pConfigDirPath, "Packages.txt")

    if lArgs:

        if lArgs[0] in ["-h", "--help"]:

            print ("\nYou must call the script manually the first time. It will give you a Launchpad link, which you need to open in a browser to grant it access (not necessarily on the same system). Select 'Change Anything' for the access level.\n\nCalling the script without arguments will go through all projects on https://salsa.debian.org/ubports-team, as well as the ~/.config/salsa2lp-sync/Packages.txt file.\nCalling the script with a project argument will process only that particular project.\n")

            exit (0)

        else:

            sFile = pPackagesPath.read_text ()
            lLines = sFile.splitlines()
            sTeam = "ubports-team"

            for sLine in lLines:

                sLinePackage, sLineTeam = sLine.split (" ")

                if lArgs[0] == sLinePackage:

                    sTeam = sLineTeam

                    break

            lPackages.append ({"package": lArgs[0], "team": sTeam})

    else:

        # Get all projects from Salsa
        pGitlab = gitlab.Gitlab ("https://salsa.debian.org")
        pGroup = pGitlab.groups.get (id="ubports-team", lazy=True)
        lProjects = pGroup.projects.list (get_all=True, order_by="name", sort="asc")

        for pProject in lProjects:

            lPackages.append ({"package": pProject.name, "team": "ubports-team"})
        #~Get all projects from Salsa

        # Get all the projects from Packages.txt
        sFile = pPackagesPath.read_text ()
        lLines = sFile.splitlines()

        for sLine in lLines:

            sPackage, sTeam = sLine.split (" ")
            lPackages.append ({"package": sPackage, "team": sTeam})
        #~Get all the projects from Packages.txt

    if pCredentialsPath.is_file ():

        pFile = open (pCredentialsPath)
        pCredentials.load (pFile)
        pFile.close ()

    else:

        sToken = pCredentials.get_request_token (web_root="production")
        bComplete = False
        bUrlShown = False

        while not bComplete:

            try:
                pCredentials.exchange_request_token_for_access_token (web_root="production")
                pFile = open (pCredentialsPath, 'w')
                pCredentials.save (pFile)
                pFile.close ()
                bComplete = True

            except HTTPError:

                if not bUrlShown:

                    print ("\n{sToken}\n")
                    bUrlShown = True

                sleep (1)

    pLaunchpad = Launchpad.login_with ("salsa2lp-sync", "production", credentials_file=pCredentialsPath, version="devel")
    pGroup = pLaunchpad.people["lomiri"]

    for dPackage in lPackages:

        # Clean up
        cleanUp (pTempPath, [])
        #~Clean up

        # Get the Debian folder
        pSalsaPath = pathlib.Path (pTempPath, "salsa")

        try:

            Repo.clone_from (f"https://salsa.debian.org/{dPackage['team']}/{dPackage['package']}.git", pSalsaPath)

        except:

            print (f"\nPanic: {dPackage['package']} not found on Salsa\n")
            exit (1)
        #~Get the Debian folder

        # Download the tarball
        lDebianFiles = ["rules", "changelog", "control"]
        bMissing = False

        for sDebianFile in lDebianFiles:

            pDebianFilePath = pathlib.Path (pSalsaPath, "debian", sDebianFile)

            if not pDebianFilePath.is_file:

                print (f"\nPanic: {dPackage['package']} is missing 'debian/{pDebianFilePath}'\n")
                bMissing = True

        if bMissing:

            continue

        try:

            subprocess.run ("uscan --noconf --rename --download-current-version --destdir=. 1> /dev/null", shell=True, cwd=pSalsaPath, check=True)

        except subprocess.CalledProcessError as pException:

            print (f"\nPanic: Failed calling 'uscan' for {dPackage['package']}:\n{pException}\n")

            continue

        cleanUp (pTempPath, [pSalsaPath])
        #~Download the tarball

        # Get the package version
        pChangelogPath = pathlib.Path (pSalsaPath, "debian/changelog")
        sVersion = None
        pFile = pChangelogPath.open ()
        sLine = pFile.readline ()
        pFile.close ()
        pMatch = re.search (r"^[a-zA-Z0-9\-]+ \((?P<version>[a-zA-Z0-9_\~\+\-\.]+)\) (?P<distribution>unstable|UNRELEASED);", sLine)

        if (pMatch):

            sVersion = pMatch.group ("version")
            sDistribution = pMatch.group ("distribution")

            """
            if sDistribution == "UNRELEASED":

                sVersion += "~"

            else:

                sVersion += "+"
            """

            sVersion += "~"

        else:

            print (f"\nPanic: Failed parsing changelog for {dPackage['package']}: {sLine}\n")
            exit (1)
        #~Get the package version

        # Create a new repository or pull the code from Launchpad
        pRepository = pLaunchpad.git_repositories.getByPath (path=f"~lomiri/+git/{dPackage['package']}")
        bNewRepo = False

        if not pRepository:

            print (f"{dPackage['package']}: Creating repository")
            pRepository = pLaunchpad.git_repositories.new (name=dPackage["package"], owner=pGroup, target=pGroup)
            bNewRepo = True

        pNow = datetime.now (timezone.utc)
        pExpires = pNow + timedelta (seconds=3600)
        sExpires = pExpires.isoformat ()
        sAccessToken = pRepository.issueAccessToken (description=f"Access token for {pLaunchpad.me.name}", scopes=["repository:push", "repository:pull"], date_expires=sExpires)
        pRepo = Repo.init (pTempPath)
        pMain = pRepo.create_remote ("main", url=f"https://{pLaunchpad.me.name}:{sAccessToken}@git.launchpad.net/~lomiri/+git/{dPackage['package']}")

        if not bNewRepo:

            pMain.fetch ("main")
            pRepo.create_head ("main", pMain.refs.main)
            pRepo.heads.main.checkout ()
            pMain.pull ("main:main")
        #~Create a new repository or pull the code from Launchpad

        # Extract the tarball
        pGitPath = pathlib.Path (pTempPath, ".git")
        cleanUp (pTempPath, [pGitPath, pSalsaPath])
        lSuffixes = ["xz", "bz2", "gz"]
        sCompression = None
        sTarPath = None

        for sSuffix in lSuffixes:

            lTarPaths = list (pSalsaPath.glob (f"*.tar.{sSuffix}"))

            if lTarPaths:

                sTarPath = lTarPaths[0]
                sCompression = sSuffix

                break

        with tarfile.open (sTarPath, f"r:{sCompression}") as pTarFile:

            lMembers = pTarFile.getmembers ()
            pToplevelPath = pathlib.Path (lMembers[0].name).parts[0]

            for pMember in lMembers:

                pMemberPath = pathlib.Path (pMember.name)
                pMember.name = pMemberPath.relative_to (pToplevelPath)

                if sys.version_info >= (3, 12):

                    pTarFile.extract (pMember, pTempPath, filter="fully_trusted")

                else:

                    pTarFile.extract (pMember, pTempPath)
        #~Extract the tarball

        # Remove the Salsa folder
        cleanUp (pSalsaPath, [])
        pSalsaPath.rmdir ()
        #~Remove the Salsa folder

        # Push the changes to Launchpad
        if bNewRepo or pRepo.is_dirty ():

            print (f"{dPackage['package']}: Pushing changes to Launchpad")
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

                sRecipe = f"{dPackage['package']}-{pDistroseries.version}"
                pRecipe = pGroup.getRecipe (name=sRecipe)

                if not pRecipe:

                    print (f"{dPackage['package']}: Creating build recipe {sRecipe}")
                    pGroup.createRecipe (build_daily=True, daily_build_archive=pArchive, description=f"Daily build of {dPackage['package']}", distroseries=pDistroseries, name=sRecipe, recipe_text="# git-build-recipe format 0.4 deb-version {debversion}-{revtime}\nlp:~lomiri/+git/" + dPackage["package"] + " main")
        #~Create build recipes (multiple distro series)
        """

        # Create build recipe (one distro series)
        pRecipe = pGroup.getRecipe (name=dPackage["package"])

        if not pRecipe:

            print (f"{dPackage['package']}: Creating build recipe")
            pArchive = pGroup.getPPAByName (name="builds")
            pDistroseries = pLaunchpad.distributions["ubuntu"].getSeries (name_or_version="24.04")
            pGroup.createRecipe (build_daily=True, daily_build_archive=pArchive, description=f"Daily build of {dPackage['package']}", distroseries=pDistroseries, name=dPackage["package"], recipe_text="# git-build-recipe format 0.4 deb-version " + sVersion + "{revtime}\nlp:~lomiri/+git/" + dPackage["package"] + " main")
        #~Create build recipe (one distro series)

    # Clean up
    cleanUp (pTempPath, [])
    #~Clean up

    sys.exit (0)
